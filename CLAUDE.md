# AI 知识库助手

## 项目概述

自动化技术动态采集与分析系统。每日从 GitHub Trending 和 Hacker News 抓取 AI/LLM/Agent 领域的前沿动态，AI 分析后结构化存储，支持飞书分发 + 本地文件预览。

## 技术栈

- **语言**: Python 3.12
- **AI 引擎**: 默认连接的模型
- **Agent 框架**: LangGraph
- **数据采集**: OpenClaw
- **存储**: SQLite（主）+ JSON（辅）
- **分发**: 飞书开放平台

## 编码规范

### 命名

- 变量/函数：`snake_case`
- 类名：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`
- 模块级私有：`_leading_underscore`
- 文件名：`snake_case.py`

### 格式化

- 缩进：4 空格，禁止 Tab
- 行宽：120 字符
- 工具：black + ruff + mypy（strict）

### 类型注解

- 公开 API 必须标注参数和返回类型
- 优先使用 `X | Y` 而非 `Optional[X]`

### Docstring

Google 风格，公开 API 必须标注。示例：

```python
def fetch_trending(topic: str, limit: int = 10) -> list[dict]:
    """从 GitHub Trending 获取指定主题的热门项目。

    Args:
        topic: 主题名称，如 'ai'、'llm'、'agent'。
        limit: 返回结果数量上限，默认为 10。

    Returns:
        项目信息字典列表，每个字典包含：
        - name: 项目名称
        - url: 项目链接
        - stars: Star 数
        - description: 项目描述

    Raises:
        NetworkError: 网络请求失败。
        RateLimitError: 触发 GitHub 限流。
        ValueError: topic 参数非法。
    """
    logger.info("开始采集 GitHub Trending: topic=%s", topic)
    ...
```

### 日志

禁止裸 `print()`，使用 `logging` 模块。

| 级别 | 用途 |
|------|------|
| DEBUG | 详细内部状态，仅开发时启用 |
| INFO | 关键业务节点 |
| WARNING | 可恢复的异常情况 |
| ERROR | 单条记录处理失败 |
| CRITICAL | 流程中断，需人工介入 |

格式：`%(asctime)s | %(levelname)-8s | %(name)s | %(message)s`

例外：CLI 面向用户输出、临时调试（必须标注 `# TODO: remove`）

## 项目结构

```
ai-knowledge-base/
├── .claude/
│   ├── agents/              # Agent 定义（有状态、工作流编排）
│   │   ├── collector.py     # 采集 Agent
│   │   ├── analyzer.py      # 分析 Agent
│   │   └── organizer.py     # 整理 Agent
│   ├── skills/              # 可复用技能（无状态、单一职责）
│   │   ├── web_fetch.py     # 网页抓取
│   │   ├── summarize.py     # 内容摘要
│   │   └── distribute.py    # 消息分发
│   └── settings.json        # Claude Code 运行时配置
├── knowledge/
│   ├── raw/                 # 原始数据（保留 7 天）
│   ├── processed/           # 处理后数据（保留 30 天）
│   ├── archive/             # 归档（保留 12 个月）
│   └── kb.db                # SQLite 主数据库
├── config/
│   └── config.yaml          # 业务配置
├── logs/
├── tests/
├── pyproject.toml
└── CLAUDE.md
```

### 入口点

```bash
python -m ai_knowledge_base.cli [command]
# collect | analyze | distribute | run-all | preview | cleanup | health-check
```

## 知识条目格式

```json
{
  "id": "kb_20240515_gh_001",
  "title": "LangChain v0.2 发布",
  "source_url": "https://github.com/langchain-ai/langchain",
  "source_type": "github_trending",
  "summary": "新增多模态 Agent 支持，优化链式调用性能。",
  "content": "AI 生成的结构化摘要（500-1000字）",
  "tags": ["langchain", "agent", "multimodal"],
  "category": "framework",
  "status": "draft",
  "quality_score": 85,
  "version": 1,
  "collected_at": "2024-05-15T08:30:00Z",
  "analyzed_at": "2024-05-15T09:00:00Z",
  "published_at": null,
  "publish_status": {
    "feishu": {"status": "success", "sent_at": "..."}
  },
  "metadata": {
    "stars": 85000,
    "language": "Python"
  }
}
```

### 必填字段

| 字段 | 说明 |
|------|------|
| id | 唯一标识，格式 `kb_YYYYMMDD_来源_序号` |
| title | 标题 |
| source_url | 原始链接 |
| source_type | `github_trending` / `hacker_news` |
| summary | AI 摘要（100-300字） |
| content | AI 结构化摘要（500-1000字） |
| tags | 标签（3-5个） |
| category | `framework` / `paper` / `tool` / `news` |
| status | `draft` / `reviewed` / `published` / `archived` |
| quality_score | 质量分数（0-100） |
| collected_at | 采集时间（ISO 8601） |

### 质量评分

| 分数 | 处理 |
|------|------|
| 80-100 | 可发布（需人工审核） |
| 60-79 | 需人工审核 |
| 0-59 | 不发布 |

### 状态机

```
draft → reviewed → published
           ↓
       archived
```

## Agent 角色

| Agent | 职责 | 输入 → 输出 |
|-------|------|-------------|
| Collector | 抓取原始内容 | 数据源配置 → 原始 JSON |
| Analyzer | AI 分析、摘要、分类 | 原始 JSON → 结构化条目 |
| Organizer | 去重、格式化、分发 | 审核后条目 → 分发内容 |

### 工作流

```
GitHub Trending ─┐
                 ├─→ Collector ─→ Analyzer ─→ 人工审核 ─→ Organizer ─→ 飞书
Hacker News ─────┘
```

### 并行策略

- Collector：每数据源独立实例，并行采集
- Analyzer：单实例顺序处理
- Organizer：批量处理，每批 10 条

### 去重规则

- 主键：`source_url`
- 辅助：`title` 相似度 > 0.85 需人工确认

### 调度

APScheduler，每日 8:00 自动运行。

## 异常处理

| 场景 | 处理 |
|------|------|
| 网络超时 | 重试 3 次，指数退避（1s, 2s, 4s） |
| 429 限流 | 等待 Retry-After 或 60 秒 |
| 5xx 错误 | 重试 3 次，间隔 10 秒 |
| 4xx 错误 | 不重试，记录日志跳过 |

### 熔断

- 连续失败 5 次：暂停 10 分钟
- 连续失败 10 次：暂停 1 小时

## 采集频率

| 数据源 | 限制 |
|--------|------|
| GitHub Trending | 5 分钟/次 |
| Hacker News | 10 次/秒 |
| 通用网页 | 60 秒/次 + jitter 5-15 秒 |

## 测试

- 框架：pytest + pytest-cov
- 覆盖率：核心模块 ≥80%，整体 ≥70%
- CI：每次提交跑 lint + 单测，每日跑集成测试

## 红线

| # | 禁止操作 | 后果 |
|---|----------|------|
| 1 | 爬取需登录页面 | 账号封禁 |
| 2 | 绕过 robots.txt | 法律风险 |
| 3 | 采集频率超标 | IP 被封 |
| 4 | 存储敏感信息 | 安全漏洞 |
| 5 | 发布未审核内容 | 质量失控 |
| 6 | 忽略异常处理 | 系统不稳定 |
| 7 | 日志记录敏感数据 | 隐私泄露 |
| 8 | 硬编码配置 | 维护困难 |

## 合规

- 遵守目标网站 ToS 和 robots.txt（启动时自动检测）
- 摘要 AI 原创，长度 ≤ 原文 20%
- 不采集/存储用户个人信息（公开用户名除外）
- 分发时附带 source_url 来源声明

## 规范修订

| 日期 | 版本 | 改动 |
|------|------|------|
| 2026-05-14 | v1.0 | 初始版本 |
