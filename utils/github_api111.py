"""GitHub API 工具模块。

提供从 GitHub API 获取仓库信息的功能。
"""

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubAPIError(Exception):
    """GitHub API 请求异常。"""

    pass


def get_repo_info(owner: str, repo: str, timeout: int = 10) -> dict[str, Any]:
    """获取 GitHub 仓库基本信息。

    Args:
        owner: 仓库所有者用户名。
        repo: 仓库名称。
        timeout: 请求超时时间（秒），默认为 10。

    Returns:
        包含仓库信息的字典，包括以下字段：
            - name: 仓库名称
            - full_name: 完整名称（owner/repo）
            - description: 仓库描述
            - stars: Star 数量
            - forks: Fork 数量
            - language: 主要编程语言
            - url: 仓库 URL

    Raises:
        GitHubAPIError: API 请求失败或仓库不存在时抛出。
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"

    logger.info("正在获取仓库信息: %s/%s", owner, repo)

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("请求 GitHub API 超时: %s", url)
        raise GitHubAPIError(f"请求超时: {url}") from None
    except requests.exceptions.RequestException as e:
        logger.error("请求 GitHub API 失败: %s", str(e))
        raise GitHubAPIError(f"请求失败: {e}") from e

    data = response.json()

    result = {
        "name": data.get("name", ""),
        "full_name": data.get("full_name", ""),
        "description": data.get("description") or "",
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "language": data.get("language") or "",
        "url": data.get("html_url", ""),
    }

    logger.info(
        "成功获取仓库信息: %s, stars=%d, forks=%d",
        result["full_name"],
        result["stars"],
        result["forks"],
    )

    return result
