#!/usr/bin/env python3
"""MCP Server for local knowledge base search.

提供 3 个工具：
- search_articles: 按关键词搜索文章
- get_article: 按 ID 获取文章详情
- knowledge_stats: 返回知识库统计

协议：JSON-RPC 2.0 over stdio
"""

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# 知识库文章目录
ARTICLES_DIR = Path(__file__).parent / "knowledge" / "articles"

# MCP 工具定义
TOOLS = [
    {
        "name": "search_articles",
        "description": "按关键词搜索知识库文章（搜索标题和摘要）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量上限，默认 5",
                    "default": 5,
                },
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "get_article",
        "description": "根据文章 ID 获取完整内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "article_id": {
                    "type": "string",
                    "description": "文章 ID，如 kb_20260527_gh_2f5b9452",
                },
            },
            "required": ["article_id"],
        },
    },
    {
        "name": "knowledge_stats",
        "description": "获取知识库统计信息（文章总数、来源分布、热门标签）",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def load_all_articles() -> list[dict[str, Any]]:
    """加载所有文章 JSON 文件。"""
    articles = []
    if not ARTICLES_DIR.exists():
        return articles

    for json_file in ARTICLES_DIR.glob("*.json"):
        try:
            with open(json_file, encoding="utf-8") as f:
                article = json.load(f)
                articles.append(article)
        except (json.JSONDecodeError, OSError) as e:
            # 记录错误但继续处理其他文件
            sys.stderr.write(f"Error loading {json_file}: {e}\n")

    return articles


def search_articles(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    """搜索文章标题和摘要中包含关键词的文章。"""
    articles = load_all_articles()
    keyword_lower = keyword.lower()

    results = []
    for article in articles:
        title = article.get("title", "").lower()
        summary = article.get("summary", "").lower()
        tags = " ".join(article.get("tags", [])).lower()

        # 搜索标题、摘要和标签
        if keyword_lower in title or keyword_lower in summary or keyword_lower in tags:
            results.append({
                "id": article.get("id"),
                "title": article.get("title"),
                "source": article.get("source_type", "unknown"),
                "summary": article.get("summary", "")[:200] + "..." if len(article.get("summary", "")) > 200 else article.get("summary", ""),
                "tags": article.get("tags", []),
                "quality_score": article.get("quality_score", 0),
            })

    # 按质量分数排序
    results.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
    return results[:limit]


def get_article(article_id: str) -> dict[str, Any] | None:
    """根据 ID 获取文章完整内容。"""
    articles = load_all_articles()
    for article in articles:
        if article.get("id") == article_id:
            return article
    return None


def knowledge_stats() -> dict[str, Any]:
    """获取知识库统计信息。"""
    articles = load_all_articles()

    # 来源分布
    source_counter = Counter(article.get("source_type", "unknown") for article in articles)

    # 标签统计
    all_tags: list[str] = []
    for article in articles:
        all_tags.extend(article.get("tags", []))
    tag_counter = Counter(all_tags)

    # 分类统计
    category_counter = Counter(article.get("category", "unknown") for article in articles)

    return {
        "total_articles": len(articles),
        "source_distribution": dict(source_counter.most_common(10)),
        "top_tags": [tag for tag, _ in tag_counter.most_common(20)],
        "category_distribution": dict(category_counter),
    }


# JSON-RPC 处理


def create_response(request_id: Any, result: Any = None, error: dict | None = None) -> str:
    """创建 JSON-RPC 响应。"""
    response = {"jsonrpc": "2.0", "id": request_id}
    if error:
        response["error"] = error
    else:
        response["result"] = result
    return json.dumps(response)


def handle_initialize(params: dict) -> dict:
    """处理 initialize 请求。"""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "knowledge-base-server", "version": "1.0.0"},
    }


def handle_tools_list() -> dict:
    """处理 tools/list 请求。"""
    return {"tools": TOOLS}


def handle_tools_call(params: dict) -> Any:
    """处理 tools/call 请求。"""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    if tool_name == "search_articles":
        keyword = arguments.get("keyword", "")
        limit = arguments.get("limit", 5)
        results = search_articles(keyword, limit)
        return {"content": [{"type": "text", "text": json.dumps(results, ensure_ascii=False, indent=2)}]}

    elif tool_name == "get_article":
        article_id = arguments.get("article_id", "")
        article = get_article(article_id)
        if article:
            return {"content": [{"type": "text", "text": json.dumps(article, ensure_ascii=False, indent=2)}]}
        else:
            return {"content": [{"type": "text", "text": json.dumps({"error": f"Article not found: {article_id}"})}]}

    elif tool_name == "knowledge_stats":
        stats = knowledge_stats()
        return {"content": [{"type": "text", "text": json.dumps(stats, ensure_ascii=False, indent=2)}]}

    else:
        raise ValueError(f"Unknown tool: {tool_name}")


def process_request(request: dict) -> str:
    """处理单个 JSON-RPC 请求。"""
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    try:
        if method == "initialize":
            result = handle_initialize(params)
            return create_response(request_id, result=result)

        elif method == "tools/list":
            result = handle_tools_list()
            return create_response(request_id, result=result)

        elif method == "tools/call":
            result = handle_tools_call(params)
            return create_response(request_id, result=result)

        elif method == "notifications/initialized":
            # 无需响应
            return ""

        else:
            return create_response(
                request_id,
                error={"code": -32601, "message": f"Method not found: {method}"},
            )

    except Exception as e:
        return create_response(
            request_id,
            error={"code": -32603, "message": f"Internal error: {str(e)}"},
        )


def main():
    """主循环：从 stdin 读取请求，处理并输出响应。"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = process_request(request)
            if response:
                sys.stdout.write(response + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError as e:
            error_response = create_response(
                None,
                error={"code": -32700, "message": f"Parse error: {str(e)}"},
            )
            sys.stdout.write(error_response + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
