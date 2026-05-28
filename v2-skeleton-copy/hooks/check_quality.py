#!/usr/bin/env python3
"""知识条目质量评分脚本。

对知识条目进行 5 维度质量评分，输出可视化进度条和等级。

评分维度（总分 100 分）：
    - 摘要质量 (25 分)：字数和技术关键词检测
    - 技术深度 (25 分)：基于 score 字段
    - 格式规范 (20 分)：必填字段和时间戳校验
    - 标签精度 (15 分)：标签数量和合法性
    - 空洞词检测 (15 分)：中英空洞词黑名单

用法：
    python hooks/check_quality.py <json_file>
    python hooks/check_quality.py "knowledge/articles/*.json"

退出码：
    0: 无 C 级条目
    1: 存在 C 级条目
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# 技术关键词列表（用于摘要质量加分）
TECH_KEYWORDS = {
    # AI/ML 基础
    "ai", "ml", "机器学习", "深度学习", "神经网络",
    "模型", "训练", "推理", "微调", "fine-tune",
    # LLM 相关
    "llm", "gpt", "bert", "transformer", "注意力机制",
    "大模型", "语言模型", "生成式", "generative",
    # Agent 相关
    "agent", "agents", "智能体", "agent工作流",
    "langchain", "langgraph", "rag", "retrieval",
    "工具调用", "tool", "function calling",
    # 架构/工程
    "api", "sdk", "框架", "framework", "库", "library",
    "微服务", "分布式", "pipeline", "工作流", "workflow",
    "状态管理", "编排", "orchestration",
    # 技术动词
    "实现", "优化", "集成", "部署", "架构",
    "支持", "提供", "包含", "采用", "基于",
}

# 空洞词黑名单 - 中文
BUZZWORDS_CN = {
    "赋能", "抓手", "闭环", "打通", "全链路",
    "底层逻辑", "颗粒度", "对齐", "拉通", "沉淀",
    "强大的", "革命性的", "颠覆性", "极致",
    "一站式", "全方位", "多层次", "端到端",
}

# 空洞词黑名单 - 英文
BUZZWORDS_EN = {
    "groundbreaking", "revolutionary", "game-changing",
    "cutting-edge", "state-of-the-art", "best-in-class",
    "industry-leading", "world-class", "best-practice",
    "game-changer", "paradigm-shift", "disruptive",
}

# 标准标签白名单
VALID_TAGS = {
    # AI/ML 基础
    "ai", "ml", "machine-learning", "deep-learning", "neural-network",
    # LLM 相关
    "llm", "gpt", "bert", "transformer", "nlp",
    "large-language-model", "language-model",
    # Agent 相关
    "agent", "agents", "langchain", "langgraph", "rag",
    "autonomous-agent", "multi-agent",
    # 框架/工具
    "framework", "library", "tool", "sdk", "api",
    "python", "typescript", "javascript", "go", "rust",
    # 应用场景
    "chatbot", "assistant", "automation", "workflow",
    "code-generation", "text-generation",
    # 其他
    "open-source", "github", "trending",
}


@dataclass
class DimensionScore:
    """单个维度的评分结果。"""

    name: str
    score: float
    max_score: float
    details: list[str] = field(default_factory=list)

    @property
    def percentage(self) -> float:
        """计算得分百分比。"""
        if self.max_score == 0:
            return 0.0
        return min(100.0, (self.score / self.max_score) * 100)


@dataclass
class QualityReport:
    """知识条目的质量评分报告。"""

    file_path: str
    item_id: str
    dimensions: list[DimensionScore] = field(default_factory=list)

    @property
    def total_score(self) -> float:
        """计算总分。"""
        return sum(d.score for d in self.dimensions)

    @property
    def max_score(self) -> float:
        """计算满分。"""
        return sum(d.max_score for d in self.dimensions)

    @property
    def grade(self) -> str:
        """计算等级。"""
        percentage = self.total_score
        if percentage >= 80:
            return "A"
        elif percentage >= 60:
            return "B"
        else:
            return "C"


def score_summary(summary: str) -> DimensionScore:
    """评分摘要质量。

    规则：
        - >= 50 字：满分
        - >= 20 字：基本分 (15 分)
        - < 20 字：低分 (5 分)
        - 含技术关键词：每个加 2 分，最多加 10 分

    Args:
        summary: 摘要文本。

    Returns:
        摘要质量评分结果。
    """
    score = 0.0
    details = []
    length = len(summary)

    # 字数评分
    if length >= 50:
        score += 15.0
        details.append(f"字数 {length} >= 50，得满分")
    elif length >= 20:
        score += 10.0
        details.append(f"字数 {length} >= 20，得基本分")
    else:
        score += max(2.0, length * 0.5)
        details.append(f"字数 {length} < 20，得低分")

    # 技术关键词检测
    summary_lower = summary.lower()
    matched_keywords = set()
    for kw in TECH_KEYWORDS:
        if kw.lower() in summary_lower:
            matched_keywords.add(kw)

    if matched_keywords:
        bonus = min(10.0, len(matched_keywords) * 2.0)
        score += bonus
        details.append(f"含技术关键词 {len(matched_keywords)} 个：+{bonus:.0f} 分")

    return DimensionScore(
        name="摘要质量",
        score=score,
        max_score=25.0,
        details=details,
    )


def score_technical_depth(metadata: dict) -> DimensionScore:
    """评分技术深度。

    规则：基于 score 字段（1-10 映射到 0-25）

    Args:
        metadata: 元数据字典，可能包含 score 字段。

    Returns:
        技术深度评分结果。
    """
    score_value = metadata.get("score", 5)
    if not isinstance(score_value, (int, float)):
        score_value = 5

    # 1-10 映射到 0-25
    normalized = max(1, min(10, score_value))
    final_score = (normalized / 10) * 25

    details = [f"score 字段值: {score_value}，映射得分: {final_score:.1f}/25"]

    return DimensionScore(
        name="技术深度",
        score=final_score,
        max_score=25.0,
        details=details,
    )


def score_format(item: dict) -> DimensionScore:
    """评分格式规范。

    规则：id、title、source_url、status、时间戳五项各 4 分

    Args:
        item: 知识条目字典。

    Returns:
        格式规范评分结果。
    """
    score = 0.0
    details = []

    # 1. ID 格式检查
    id_value = item.get("id", "")
    id_pattern = re.compile(r"^kb_\d{8}_[a-z]{2,}_\d{3}$")
    if id_pattern.match(str(id_value)):
        score += 4.0
        details.append("ID 格式正确: +4 分")
    else:
        details.append(f"ID 格式有误: '{id_value}'")

    # 2. title 非空检查
    title = item.get("title", "")
    if isinstance(title, str) and len(title) >= 3:
        score += 4.0
        details.append(f"标题有效: +4 分")
    else:
        details.append(f"标题无效或过短")

    # 3. source_url 格式检查
    url = item.get("source_url", "")
    if isinstance(url, str) and re.match(r"^https?://", url):
        score += 4.0
        details.append("URL 格式正确: +4 分")
    else:
        details.append(f"URL 格式有误")

    # 4. status 有效性检查
    status = item.get("status", "")
    valid_statuses = {"draft", "review", "published", "archived"}
    if status in valid_statuses:
        score += 4.0
        details.append(f"status 有效: +4 分")
    else:
        details.append(f"status 无效: '{status}'")

    # 5. 时间戳检查
    has_timestamp = False
    for ts_field in ["collected_at", "created_at", "published_at"]:
        ts_value = item.get(ts_field)
        if ts_value and isinstance(ts_value, str):
            # ISO 8601 格式检查
            if re.match(r"\d{4}-\d{2}-\d{2}", ts_value):
                has_timestamp = True
                break

    if has_timestamp:
        score += 4.0
        details.append("时间戳有效: +4 分")
    else:
        details.append("缺少有效时间戳")

    return DimensionScore(
        name="格式规范",
        score=score,
        max_score=20.0,
        details=details,
    )


def score_tags(tags: list) -> DimensionScore:
    """评分标签精度。

    规则：
        - 1-3 个标签：满分
        - 0 个或 > 5 个：扣分
        - 含非法标签：每个扣 2 分

    Args:
        tags: 标签列表。

    Returns:
        标签精度评分结果。
    """
    score = 15.0
    details = []

    if not isinstance(tags, list):
        tags = []

    tag_count = len(tags)

    # 数量评分
    if tag_count == 0:
        score -= 10.0
        details.append("无标签: -10 分")
    elif tag_count <= 3:
        details.append(f"标签数量 {tag_count} 最佳: 满分")
    elif tag_count <= 5:
        score -= 3.0
        details.append(f"标签数量 {tag_count} 偏多: -3 分")
    else:
        score -= 8.0
        details.append(f"标签数量 {tag_count} 过多: -8 分")

    # 合法性检查
    invalid_tags = []
    for tag in tags:
        if not isinstance(tag, str):
            continue
        tag_lower = tag.lower()
        # 检查是否在白名单或符合基本格式
        is_valid = tag_lower in VALID_TAGS or re.match(r"^[a-z][a-z0-9-]{1,20}$", tag_lower)
        if not is_valid:
            invalid_tags.append(tag)

    if invalid_tags:
        penalty = min(10.0, len(invalid_tags) * 2.0)
        score -= penalty
        details.append(f"含非法标签 {len(invalid_tags)} 个: -{penalty:.0f} 分")

    score = max(0.0, score)

    return DimensionScore(
        name="标签精度",
        score=score,
        max_score=15.0,
        details=details,
    )


def score_buzzword_detection(text: str) -> DimensionScore:
    """评分空洞词检测。

    规则：
        - 不含空洞词：满分
        - 每含一个空洞词：扣 3 分

    Args:
        text: 待检测文本（通常是 content 或 summary）。

    Returns:
        空洞词检测评分结果。
    """
    score = 15.0
    details = []
    text_lower = text.lower()

    found_words = []

    # 检测中文空洞词
    for word in BUZZWORDS_CN:
        if word in text:
            found_words.append(word)

    # 检测英文空洞词
    for word in BUZZWORDS_EN:
        if word in text_lower:
            found_words.append(word)

    if found_words:
        penalty = min(15.0, len(found_words) * 3.0)
        score -= penalty
        details.append(f"含空洞词 {len(found_words)} 个: -{penalty:.0f} 分")
        details.append(f"空洞词: {', '.join(found_words[:5])}")
    else:
        details.append("无空洞词: 满分")

    return DimensionScore(
        name="空洞词检测",
        score=score,
        max_score=15.0,
        details=details,
    )


def evaluate_item(item: dict, file_path: Path) -> QualityReport:
    """评估单个知识条目的质量。

    Args:
        item: 知识条目字典。
        file_path: 文件路径。

    Returns:
        质量评分报告。
    """
    dimensions = []

    # 1. 摘要质量 (25 分)
    summary = item.get("summary", "")
    if not isinstance(summary, str):
        summary = str(summary)
    dimensions.append(score_summary(summary))

    # 2. 技术深度 (25 分)
    metadata = item.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    dimensions.append(score_technical_depth(metadata))

    # 3. 格式规范 (20 分)
    dimensions.append(score_format(item))

    # 4. 标签精度 (15 分)
    tags = item.get("tags", [])
    dimensions.append(score_tags(tags))

    # 5. 空洞词检测 (15 分) - 检查 summary 和 content
    full_text = summary
    content = item.get("content", "")
    if isinstance(content, str):
        full_text = f"{summary} {content}"
    dimensions.append(score_buzzword_detection(full_text))

    return QualityReport(
        file_path=str(file_path),
        item_id=item.get("id", "unknown"),
        dimensions=dimensions,
    )


def draw_progress_bar(score: float, max_score: float, width: int = 20) -> str:
    """绘制进度条。

    Args:
        score: 得分。
        max_score: 满分。
        width: 进度条宽度。

    Returns:
        进度条字符串。
    """
    if max_score == 0:
        percentage = 0
    else:
        percentage = min(100, (score / max_score) * 100)

    filled = int(width * percentage / 100)
    empty = width - filled

    # 根据得分选择颜色符号
    if percentage >= 80:
        bar_char = "█"
    elif percentage >= 60:
        bar_char = "▓"
    else:
        bar_char = "░"

    return f"[{bar_char * filled}{' ' * empty}] {percentage:5.1f}%"


def print_report(report: QualityReport, verbose: bool = False) -> None:
    """打印质量评分报告。

    Args:
        report: 质量评分报告。
        verbose: 是否打印详细信息。
    """
    # 等级颜色标记
    grade_color = {
        "A": "\033[92m",  # 绿色
        "B": "\033[93m",  # 黄色
        "C": "\033[91m",  # 红色
    }
    reset_color = "\033[0m"

    color = grade_color.get(report.grade, "")

    print(f"\n{'=' * 60}")
    print(f"文件: {report.file_path}")
    print(f"ID: {report.item_id}")
    print(f"{'=' * 60}")

    # 打印各维度得分
    for dim in report.dimensions:
        progress_bar = draw_progress_bar(dim.score, dim.max_score)
        print(f"\n{dim.name:12} {progress_bar}  {dim.score:5.1f}/{dim.max_score:.0f}")

        if verbose and dim.details:
            for detail in dim.details:
                print(f"              └─ {detail}")

    # 打印总分和等级
    print(f"\n{'-' * 60}")
    print(f"总分: {report.total_score:.1f}/{report.max_score:.0f}")
    print(f"等级: {color}{report.grade}{reset_color}")

    if report.grade == "A":
        print("评价: 优秀，可直接发布")
    elif report.grade == "B":
        print("评价: 合格，建议审核后发布")
    else:
        print("评价: 不合格，需要改进")


def check_file(file_path: Path, verbose: bool = False) -> QualityReport | None:
    """检查单个文件。

    Args:
        file_path: JSON 文件路径。
        verbose: 是否打印详细信息。

    Returns:
        质量评分报告，如果文件无法解析则返回 None。
    """
    if not file_path.exists():
        print(f"错误: 文件不存在 - {file_path}", file=sys.stderr)
        return None

    try:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败 - {file_path}: {e}", file=sys.stderr)
        return None

    # 支持单个对象或数组
    items = data if isinstance(data, list) else [data]

    # 只检查第一个条目（通常一个文件一个条目）
    item = items[0]
    if not isinstance(item, dict):
        print(f"错误: 无效的数据结构 - {file_path}", file=sys.stderr)
        return None

    report = evaluate_item(item, file_path)
    print_report(report, verbose)

    return report


def main() -> int:
    """主函数。

    Returns:
        退出码：0 表示无 C 级，1 表示存在 C 级。
    """
    if len(sys.argv) < 2:
        print("用法: python hooks/check_quality.py <json_file> [--verbose]")
        print("      python hooks/check_quality.py 'knowledge/articles/*.json'")
        return 1

    # 解析参数
    args = sys.argv[1:]
    verbose = "--verbose" in args or "-v" in args
    json_args = [a for a in args if not a.startswith("-")]

    # 收集所有文件路径（支持通配符）
    file_paths: list[Path] = []
    for arg in json_args:
        path = Path(arg)
        if "*" in arg:
            parent = path.parent if path.parent.exists() else Path(".")
            file_paths.extend(sorted(parent.glob(path.name)))
        else:
            file_paths.append(path)

    if not file_paths:
        print("错误: 未找到匹配的文件", file=sys.stderr)
        return 1

    # 检查所有文件
    reports: list[QualityReport] = []
    for file_path in file_paths:
        report = check_file(file_path, verbose)
        if report:
            reports.append(report)

    # 统计结果
    if not reports:
        return 1

    grade_counts = {"A": 0, "B": 0, "C": 0}
    for r in reports:
        grade_counts[r.grade] += 1

    print(f"\n{'=' * 60}")
    print(f"检查完成: {len(reports)} 个条目")
    print(f"等级分布: A={grade_counts['A']} | B={grade_counts['B']} | C={grade_counts['C']}")
    print(f"{'=' * 60}")

    # 存在 C 级返回 1
    return 1 if grade_counts["C"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())