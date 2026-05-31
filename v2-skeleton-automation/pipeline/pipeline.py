#!/usr/bin/env python3
"""知识库自动化流水线。

四步流水线：
1. Collect - 从 GitHub Search API 和 RSS 源采集 AI 相关内容
2. Analyze - 调用 LLM 对每条内容进行摘要/评分/标签分析
3. Organize - 去重 + 格式标准化 + 校验
4. Save - 将文章保存为独立 JSON 文件到 knowledge/articles/

用法：
    python pipeline/pipeline.py --sources github,rss --limit 20
    python pipeline/pipeline.py --sources github --limit 5
    python pipeline/pipeline.py --sources rss --limit 10
    python pipeline/pipeline.py --sources github --limit 5 --dry-run
    python pipeline/pipeline.py --verbose
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

# 同目录下的 model_client
from model_client import LLMClient, LLMError, chat_with_retry

logger = logging.getLogger(__name__)


# ============================================================================
# 配置常量
# ============================================================================

GITHUB_API_URL = "https://api.github.com/search/repositories"
GITHUB_SEARCH_QUERY = "AI OR LLM OR agent OR langchain OR openai language:Python"
RSS_FEEDS = [
    "https://hnrss.org/frontpage",
    "https://feeds.feedburner.com/oreilly/radar",
]

DEFAULT_LIMIT = 20
REQUEST_TIMEOUT = 30.0
USER_AGENT = "AI-Knowledge-Base/1.0"

# 目录路径
PROJECT_ROOT = Path(__file__).parent.parent
KNOWLEDGE_RAW_DIR = PROJECT_ROOT / "knowledge" / "raw"
KNOWLEDGE_ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class RawArticle:
    """原始采集的文章数据。"""

    id: str
    title: str
    source_url: str
    source_type: str  # "github" or "rss"
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    collected_at: str = ""

    def __post_init__(self) -> None:
        if not self.collected_at:
            self.collected_at = datetime.now(timezone.utc).isoformat()


@dataclass
class AnalyzedArticle:
    """分析后的文章数据。"""

    id: str
    title: str
    source_url: str
    source_type: str
    summary: str
    content: str
    tags: list[str]
    category: str
    quality_score: int
    metadata: dict[str, Any]
    collected_at: str
    analyzed_at: str = ""

    def __post_init__(self) -> None:
        if not self.analyzed_at:
            self.analyzed_at = datetime.now(timezone.utc).isoformat()


# ============================================================================
# Step 1: 采集（Collect）
# ============================================================================

class Collector:
    """内容采集器，支持 GitHub Search API 和 RSS 源。"""

    def __init__(self, timeout: float = REQUEST_TIMEOUT) -> None:
        """初始化采集器。

        Args:
            timeout: HTTP 请求超时时间（秒）。
        """
        self.timeout = timeout
        self.headers = {"User-Agent": USER_AGENT}

    def collect_github(self, limit: int) -> list[RawArticle]:
        """从 GitHub Search API 采集 AI 相关项目。

        Args:
            limit: 采集数量上限。

        Returns:
            原始文章列表。
        """
        logger.info("开始采集 GitHub: limit=%d", limit)

        articles: list[RawArticle] = []
        params = {
            "q": GITHUB_SEARCH_QUERY,
            "sort": "stars",
            "order": "desc",
            "per_page": min(limit, 100),
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(GITHUB_API_URL, params=params, headers=self.headers)

                if response.status_code != 200:
                    logger.error("GitHub API 请求失败: status=%d", response.status_code)
                    return articles

                data = response.json()
                items = data.get("items", [])

                for item in items[:limit]:
                    article = RawArticle(
                        id=self._generate_id("gh", item.get("html_url", "")),
                        title=item.get("full_name", ""),
                        source_url=item.get("html_url", ""),
                        source_type="github",
                        description=item.get("description", "") or "",
                        metadata={
                            "stars": item.get("stargazers_count", 0),
                            "language": item.get("language", ""),
                            "forks": item.get("forks_count", 0),
                            "open_issues": item.get("open_issues_count", 0),
                        },
                    )
                    articles.append(article)

                logger.info("GitHub 采集完成: 共 %d 条", len(articles))

        except httpx.RequestError as e:
            logger.error("GitHub 请求错误: %s", e)

        return articles

    def collect_rss(self, limit: int) -> list[RawArticle]:
        """从 RSS 源采集内容。

        Args:
            limit: 采集数量上限。

        Returns:
            原始文章列表。
        """
        logger.info("开始采集 RSS: limit=%d", limit)

        articles: list[RawArticle] = []
        collected = 0

        for feed_url in RSS_FEEDS:
            if collected >= limit:
                break

            try:
                items = self._fetch_and_parse_rss(feed_url, limit - collected)
                articles.extend(items)
                collected += len(items)

            except httpx.RequestError as e:
                logger.error("RSS 请求错误: url=%s, error=%s", feed_url, e)

        logger.info("RSS 采集完成: 共 %d 条", len(articles))
        return articles

    def _fetch_and_parse_rss(self, feed_url: str, limit: int) -> list[RawArticle]:
        """获取并解析 RSS feed。

        使用简易正则解析，不依赖 XML 解析库。

        Args:
            feed_url: RSS feed URL。
            limit: 采集数量上限。

        Returns:
            原始文章列表。
        """
        articles: list[RawArticle] = []

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(feed_url, headers=self.headers)

            if response.status_code != 200:
                logger.warning("RSS 请求失败: url=%s, status=%d", feed_url, response.status_code)
                return articles

            content = response.text

            # 简易正则解析 <item> 元素
            item_pattern = r"<item>(.*?)</item>"
            items = re.findall(item_pattern, content, re.DOTALL)

            for item_content in items[:limit]:
                title = self._extract_rss_field(item_content, "title")
                link = self._extract_rss_field(item_content, "link")
                description = self._extract_rss_field(item_content, "description")

                if not title or not link:
                    continue

                article = RawArticle(
                    id=self._generate_id("rss", link),
                    title=title,
                    source_url=link,
                    source_type="rss",
                    description=description,
                    metadata={"feed_url": feed_url},
                )
                articles.append(article)

        return articles

    def _extract_rss_field(self, item_content: str, field_name: str) -> str:
        """从 RSS item 中提取字段值。

        Args:
            item_content: RSS item 内容。
            field_name: 字段名称。

        Returns:
            字段值（去除 CDATA 和 HTML 标签）。
        """
        # 匹配 <field>...</field> 或 <field><![CDATA[...]]></field>
        pattern = rf"<{field_name}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{field_name}>"
        match = re.search(pattern, item_content, re.DOTALL)

        if not match:
            return ""

        value = match.group(1)
        # 去除 HTML 标签
        value = re.sub(r"<[^>]+>", "", value)
        # 去除多余空白
        value = re.sub(r"\s+", " ", value).strip()

        return value

    def _generate_id(self, source_prefix: str, url: str) -> str:
        """生成唯一 ID。

        格式: {source}-{YYYYMMDD}-{NNN}

        Args:
            source_prefix: 来源前缀（gh/rss）。
            url: 文章 URL（用于去重，不参与 ID 生成）。

        Returns:
            唯一 ID。
        """
        date_str = datetime.now().strftime("%Y%m%d")

        # 获取当日该来源已有的文章数量，生成序号
        pattern = f"{source_prefix}-{date_str}-*.json"
        existing = list(KNOWLEDGE_ARTICLES_DIR.glob(pattern))
        seq = len(existing) + 1

        return f"{source_prefix}-{date_str}-{seq:03d}"


# ============================================================================
# Step 2: 分析（Analyze）
# ============================================================================

class Analyzer:
    """LLM 内容分析器。"""

    def __init__(self, client: LLMClient) -> None:
        """初始化分析器。

        Args:
            client: LLM 客户端。
        """
        self.client = client

    def analyze(self, article: RawArticle, dry_run: bool = False) -> AnalyzedArticle | None:
        """分析单篇文章。

        Args:
            article: 原始文章。
            dry_run: 是否干跑模式（不实际调用 LLM）。

        Returns:
            分析后的文章，失败返回 None。
        """
        logger.debug("分析文章: %s", article.title[:50])

        if dry_run:
            return self._create_mock_analyzed_article(article)

        prompt = self._build_analysis_prompt(article)

        try:
            response = chat_with_retry(
                self.client,
                [{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.3,
            )

            result = self._parse_llm_response(response.content)
            if not result:
                logger.warning("LLM 响应解析失败: %s", article.title[:30])
                return None

            return AnalyzedArticle(
                id=article.id,
                title=article.title,
                source_url=article.source_url,
                source_type=article.source_type,
                summary=result["summary"],
                content=result["content"],
                tags=result["tags"],
                category=result["category"],
                quality_score=result["quality_score"],
                metadata=article.metadata,
                collected_at=article.collected_at,
            )

        except LLMError as e:
            logger.error("LLM 调用失败: %s", e)
            return None

    def _build_analysis_prompt(self, article: RawArticle) -> str:
        """构建分析提示词。

        Args:
            article: 原始文章。

        Returns:
            提示词字符串。
        """
        return f"""请分析以下技术内容，生成结构化摘要。

标题: {article.title}
来源: {article.source_url}
描述: {article.description}
元数据: {json.dumps(article.metadata, ensure_ascii=False)}

请按以下 JSON 格式输出（不要输出其他内容）：
{{
    "summary": "100-200字的简洁摘要",
    "content": "500-800字的详细分析，包括技术亮点、应用场景、局限性",
    "tags": ["标签1", "标签2", "标签3"],
    "category": "framework/paper/tool/news 之一",
    "quality_score": 0-100的整数评分
}}

评分标准：
- 80-100: 高质量，技术深度好，有实用价值
- 60-79: 中等质量，有一定参考价值
- 0-59: 低质量，信息量少或相关性弱"""

    def _parse_llm_response(self, response: str) -> dict[str, Any] | None:
        """解析 LLM 响应。

        Args:
            response: LLM 响应文本。

        Returns:
            解析后的字典，失败返回 None。
        """
        # 尝试提取 JSON
        json_match = re.search(r"\{[\s\S]*\}", response)
        if not json_match:
            return None

        try:
            data = json.loads(json_match.group())

            # 校验必填字段
            required = ["summary", "content", "tags", "category", "quality_score"]
            if not all(k in data for k in required):
                return None

            # 校验类型
            if not isinstance(data["tags"], list):
                data["tags"] = [data["tags"]]
            if not isinstance(data["quality_score"], int):
                data["quality_score"] = int(data["quality_score"])

            # 校验范围
            data["quality_score"] = max(0, min(100, data["quality_score"]))
            data["category"] = data["category"] if data["category"] in [
                "framework", "paper", "tool", "news"
            ] else "news"

            return data

        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    def _create_mock_analyzed_article(self, article: RawArticle) -> AnalyzedArticle:
        """创建模拟的分析结果（用于 dry-run 模式）。

        Args:
            article: 原始文章。

        Returns:
            模拟的分析后文章。
        """
        return AnalyzedArticle(
            id=article.id,
            title=article.title,
            source_url=article.source_url,
            source_type=article.source_type,
            summary="[DRY-RUN] 模拟摘要内容",
            content="[DRY-RUN] 模拟详细分析内容",
            tags=["ai", "dry-run"],
            category="news",
            quality_score=75,
            metadata=article.metadata,
            collected_at=article.collected_at,
        )


# ============================================================================
# Step 3: 整理（Organize）
# ============================================================================

class Organizer:
    """内容整理器：去重 + 格式标准化 + 校验。"""

    def __init__(self) -> None:
        """初始化整理器。"""
        self._seen_urls: set[str] = set()
        self._seen_titles: dict[str, str] = {}  # title_lower -> id

    def organize(self, articles: list[AnalyzedArticle]) -> list[AnalyzedArticle]:
        """整理文章列表。

        Args:
            articles: 待整理的文章列表。

        Returns:
            整理后的文章列表。
        """
        logger.info("开始整理: 输入 %d 条", len(articles))

        organized: list[AnalyzedArticle] = []

        for article in articles:
            # 去重
            if self._is_duplicate(article):
                logger.debug("跳过重复: %s", article.title[:30])
                continue

            # 格式标准化
            normalized = self._normalize(article)

            # 校验
            if self._validate(normalized):
                organized.append(normalized)
                self._record_article(normalized)

        logger.info("整理完成: 输出 %d 条", len(organized))
        return organized

    def _is_duplicate(self, article: AnalyzedArticle) -> bool:
        """检查是否重复。

        Args:
            article: 待检查的文章。

        Returns:
            是否重复。
        """
        # URL 去重
        if article.source_url in self._seen_urls:
            return True

        # 标题相似度去重（简化版：完全匹配小写）
        title_lower = article.title.lower()
        if title_lower in self._seen_titles:
            return True

        return False

    def _record_article(self, article: AnalyzedArticle) -> None:
        """记录已处理的文章。

        Args:
            article: 已处理的文章。
        """
        self._seen_urls.add(article.source_url)
        self._seen_titles[article.title.lower()] = article.id

    def _normalize(self, article: AnalyzedArticle) -> AnalyzedArticle:
        """格式标准化。

        Args:
            article: 待标准化的文章。

        Returns:
            标准化后的文章。
        """
        # 清理标题
        article.title = article.title.strip()

        # 清理摘要和内容
        article.summary = article.summary.strip()
        article.content = article.content.strip()

        # 标签去重和统一小写
        article.tags = list(set(tag.lower().strip() for tag in article.tags if tag.strip()))

        # 确保 3-5 个标签
        if len(article.tags) < 3:
            article.tags.append("ai")
        if len(article.tags) > 5:
            article.tags = article.tags[:5]

        return article

    def _validate(self, article: AnalyzedArticle) -> bool:
        """校验文章数据。

        Args:
            article: 待校验的文章。

        Returns:
            是否有效。
        """
        # 必填字段
        if not article.title:
            logger.warning("校验失败: 标题为空")
            return False
        if not article.source_url:
            logger.warning("校验失败: URL 为空")
            return False
        if not article.summary:
            logger.warning("校验失败: 摘要为空")
            return False

        # 长度校验
        if len(article.summary) < 50:
            logger.warning("校验失败: 摘要过短 (%d 字)", len(article.summary))
            return False
        if len(article.content) < 100:
            logger.warning("校验失败: 内容过短 (%d 字)", len(article.content))
            return False

        # 分数范围
        if not (0 <= article.quality_score <= 100):
            logger.warning("校验失败: 分数越界 %d", article.quality_score)
            return False

        return True


# ============================================================================
# Step 4: 保存（Save）
# ============================================================================

class Saver:
    """文章保存器。"""

    def __init__(
        self,
        raw_dir: Path = KNOWLEDGE_RAW_DIR,
        articles_dir: Path = KNOWLEDGE_ARTICLES_DIR,
    ) -> None:
        """初始化保存器。

        Args:
            raw_dir: 原始数据目录。
            articles_dir: 文章目录。
        """
        self.raw_dir = raw_dir
        self.articles_dir = articles_dir

    def ensure_dirs(self) -> None:
        """确保目录存在。"""
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.articles_dir.mkdir(parents=True, exist_ok=True)

    def save_raw(self, articles: list[RawArticle]) -> int:
        """保存原始数据。

        Args:
            articles: 原始文章列表。

        Returns:
            成功保存的数量。
        """
        self.ensure_dirs()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"raw_{timestamp}.json"
        filepath = self.raw_dir / filename

        data = [asdict(a) for a in articles]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("保存原始数据: %s (%d 条)", filepath, len(articles))
        return len(articles)

    def save_articles(self, articles: list[AnalyzedArticle]) -> int:
        """保存文章到独立 JSON 文件。

        Args:
            articles: 分析后的文章列表。

        Returns:
            成功保存的数量。
        """
        self.ensure_dirs()

        saved = 0
        for article in articles:
            filename = f"{article.id}.json"
            filepath = self.articles_dir / filename

            data = asdict(article)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            saved += 1

        logger.info("保存文章: %d 条到 %s", saved, self.articles_dir)
        return saved


# ============================================================================
# 流水线编排
# ============================================================================

class Pipeline:
    """知识库自动化流水线。"""

    def __init__(
        self,
        sources: list[str],
        limit: int = DEFAULT_LIMIT,
        dry_run: bool = False,
    ) -> None:
        """初始化流水线。

        Args:
            sources: 数据源列表（github, rss）。
            limit: 每个源采集数量上限。
            dry_run: 是否干跑模式。
        """
        self.sources = sources
        self.limit = limit
        self.dry_run = dry_run

        self.collector = Collector()
        self.analyzer = Analyzer(LLMClient.from_env()) if not dry_run else Analyzer(LLMClient.from_env())
        self.organizer = Organizer()
        self.saver = Saver()

    def run(self) -> dict[str, Any]:
        """运行完整流水线。

        Returns:
            运行统计信息。
        """
        logger.info("=" * 60)
        logger.info("知识库流水线启动")
        logger.info("数据源: %s, 限制: %d, 干跑: %s", self.sources, self.limit, self.dry_run)
        logger.info("=" * 60)

        stats = {
            "collected": 0,
            "analyzed": 0,
            "organized": 0,
            "saved": 0,
            "errors": [],
        }

        # Step 1: 采集
        raw_articles: list[RawArticle] = []

        if "github" in self.sources:
            github_articles = self.collector.collect_github(self.limit)
            raw_articles.extend(github_articles)

        if "rss" in self.sources:
            rss_articles = self.collector.collect_rss(self.limit)
            raw_articles.extend(rss_articles)

        stats["collected"] = len(raw_articles)

        if not raw_articles:
            logger.warning("未采集到任何内容")
            return stats

        # 保存原始数据
        self.saver.save_raw(raw_articles)

        # Step 2: 分析
        analyzed_articles: list[AnalyzedArticle] = []

        for article in raw_articles:
            result = self.analyzer.analyze(article, dry_run=self.dry_run)
            if result:
                analyzed_articles.append(result)

        stats["analyzed"] = len(analyzed_articles)

        if not analyzed_articles:
            logger.warning("所有文章分析失败")
            return stats

        # Step 3: 整理
        organized_articles = self.organizer.organize(analyzed_articles)
        stats["organized"] = len(organized_articles)

        # Step 4: 保存
        saved_count = self.saver.save_articles(organized_articles)
        stats["saved"] = saved_count

        logger.info("=" * 60)
        logger.info("流水线完成: 采集=%d, 分析=%d, 整理=%d, 保存=%d",
                    stats["collected"], stats["analyzed"],
                    stats["organized"], stats["saved"])
        logger.info("=" * 60)

        return stats


# ============================================================================
# CLI 入口
# ============================================================================

def parse_args() -> argparse.Namespace:
    """解析命令行参数。

    Returns:
        解析后的参数。
    """
    parser = argparse.ArgumentParser(
        description="知识库自动化流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pipeline/pipeline.py --sources github,rss --limit 20
  python pipeline/pipeline.py --sources github --limit 5
  python pipeline/pipeline.py --sources rss --limit 10
  python pipeline/pipeline.py --sources github --limit 5 --dry-run
  python pipeline/pipeline.py --verbose
        """,
    )

    parser.add_argument(
        "--sources",
        type=str,
        default="github,rss",
        help="数据源，逗号分隔，可选: github, rss (默认: github,rss)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"每个数据源采集数量上限 (默认: {DEFAULT_LIMIT})",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干跑模式，不实际调用 LLM",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细日志输出",
    )

    return parser.parse_args()


def main() -> int:
    """主入口函数。

    Returns:
        退出码。
    """
    args = parse_args()

    # 配置日志
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    # 解析数据源
    sources = [s.strip().lower() for s in args.sources.split(",")]
    valid_sources = {"github", "rss"}
    sources = [s for s in sources if s in valid_sources]

    if not sources:
        logger.error("无效的数据源: %s", args.sources)
        return 1

    try:
        pipeline = Pipeline(
            sources=sources,
            limit=args.limit,
            dry_run=args.dry_run,
        )

        stats = pipeline.run()

        # 返回码
        if stats["saved"] > 0:
            return 0
        elif stats["collected"] > 0:
            return 2  # 有采集但无保存
        else:
            return 1  # 无采集

    except LLMError as e:
        logger.error("LLM 错误: %s", e)
        return 1
    except Exception as e:
        logger.exception("未知错误: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
