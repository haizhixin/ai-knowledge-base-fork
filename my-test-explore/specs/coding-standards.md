# AI 知识库 · 编码规范 v1.0

## 项目概述

自动化技术动态采集与分析系统。每日从 GitHub Trending 和 Hacker News 抓取 AI/LLM/Agent 领域的前沿动态，AI 分析后结构化存储，支持飞书分发。

## 技术栈

- **语言**: Python 3.12
- **AI 引擎**: 默认连接的模型
- **Agent 框架**: LangGraph
- **数据采集**: OpenClaw
- **存储**: SQLite（主）+ JSON（辅）
- **分发**: 飞书开放平台 + 本地文件预览

---

## 编码风格

### 命名规范

- 变量/函数：`snake_case`
- 类名：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`（如 `MAX_RETRY_COUNT`）
- 模块级私有：`_leading_underscore`（如 `_internal_cache`）
- 文件名：`snake_case.py`（如 `collector_agent.py`）

### 格式化

- 缩进：4 空格，禁止 Tab
- 行宽：120 字符
- 导入顺序：标准库 → 第三方库 → 本地模块，每组之间空一行

### 工具链

```toml
# pyproject.toml
[tool.black]
line-length = 120

[tool.ruff]
line-length = 120
select = ["E", "F", "W", "I", "N", "UP", "B"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
```

---

## 文档规范

### Docstring

使用 Google 风格 docstring，公开 API 必须标注。

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
        RateLimitError: 触发 GitHub 限流（需等待冷却）。
        ValueError: topic 参数非法。
    """
```

### 边界规则

- 公开 API（非 `_` 前缀）必须有 docstring
- 简单 getter/setter 可省略
- 类 docstring 说明职责和用法示例
- 模块 docstring 说明模块功能和导出内容

---

## 类型注解

- 所有公开 API 必须标注参数和返回类型
- 返回类型尽量精确，如 `list[dict[str, Any]]`
- 优先使用 Python 3.10+ 联合语法（`X | Y` 而非 `Optional[X]`）
- 第三方库无类型注解时，用 `Any` 并在 docstring 中补充说明
- 私有函数（`_` 前缀）类型注解可选，但建议保留

---

## 日志规范

### 格式

```
%(asctime)s | %(levelname)-8s | %(name)s | %(message)s
```

示例：
```
2024-05-15 08:30:00 | INFO     | collector | 开始采集 GitHub Trending: topic=ai
```

### 级别规范

| 级别 | 用途 |
|------|------|
| DEBUG | 详细的内部状态，仅开发时启用 |
| INFO | 关键业务节点（采集开始/完成、分析完成等） |
| WARNING | 可恢复的异常情况（重试中、配置缺失使用默认值） |
| ERROR | 影响单条记录处理失败，记录异常堆栈 |
| CRITICAL | 影响整个流程中断，需人工介入 |

### 输出策略

- 控制台：INFO 及以上
- 文件：DEBUG 及以上
- 文件路径：`logs/ai_kb_YYYYMMDD.log`

### 轮转策略

- 按天轮转，保留 30 天
- 单文件超过 100MB 强制轮转

### 敏感信息脱敏

```python
SENSITIVE_KEYS = {"password", "token", "api_key", "secret", "secret_key"}

def sanitize_for_log(data: dict) -> dict:
    """移除或脱敏敏感字段"""
    return {
        k: "***REDACTED***" if k.lower() in SENSITIVE_KEYS else v
        for k, v in data.items()
    }
```

### 禁止裸 print()

禁止裸 `print()`，但以下情况例外：

1. CLI 工具的面向用户输出（应封装为独立的 output 模块）
2. 临时调试必须以 `# TODO: remove` 标注，并在 PR 前删除

---

## 项目结构

```
ai-knowledge-base/
├── .claude/
│   ├── agents/              # Agent 定义
│   │   ├── collector.py     # 采集 Agent
│   │   ├── analyzer.py      # 分析 Agent
│   │   └── organizer.py     # 整理 Agent
│   ├── skills/              # 可复用技能
│   │   ├── web_fetch.py     # 网页抓取
│   │   ├── summarize.py     # 内容摘要
│   │   └── distribute.py    # 消息分发
│   └── settings.json        # Claude Code 运行时配置
├── knowledge/
│   ├── raw/                 # 原始数据（保留 7 天）
│   ├── processed/           # 处理后数据（保留 30 天）
│   └── archive/             # 归档（保留 12 个月）
├── config/
│   └── config.yaml          # 业务配置
├── logs/
├── tests/
├── pyproject.toml
└── CLAUDE.md
```

### agents vs skills 边界

- **Agent**：有状态、有工作流编排能力、独立运行
- **Skill**：无状态、单一职责、被 Agent 调用

### 入口点

```bash
python -m ai_knowledge_base.cli [command]
# 支持: collect, analyze, distribute, run-all, preview, cleanup, health-check
```

### 数据生命周期

| 目录 | 保留期限 | 清理方式 |
|------|----------|----------|
| raw/ | 7 天 | 自动清理 |
| processed/ | 30 天 | 自动清理 |
| archive/ | 12 个月 | 自动清理 |

---

## 知识条目格式

```json
{
  "id": "kb_20240515_gh_001",
  "title": "LangChain v0.2 发布",
  "source_url": "https://github.com/langchain-ai/langchain",
  "source_type": "github_trending",
  "summary": "新增多模态 Agent 支持，优化链式调用性能。",
  "content": "AI 生成的结构化摘要（500-1000 字）",
  "tags": ["langchain", "agent", "multimodal"],
  "category": "framework",
  "status": "draft",
  "quality_score": 85,
  "version": 1,
  "collected_at": "2024-05-15T08:30:00Z",
  "analyzed_at": "2024-05-15T09:00:00Z",
  "published_at": null,
  "publish_channels": [],
  "publish_status": {},
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
| content | AI 生成的结构化摘要（500-1000字） |
| tags | 标签（3-5个） |
| category | `framework` / `paper` / `tool` / `news` |
| status | `draft` / `reviewed` / `published` / `archived` |
| quality_score | 质量分数（0-100） |
| collected_at | 采集时间（ISO 8601） |

### quality_score 标准

| 分数段 | 含义 | 处理方式 |
|--------|------|----------|
| 80-100 | 高质量 | 可直接发布（需人工审核） |
| 60-79 | 中等质量 | 需人工审核 |
| 0-59 | 低质量 | 不发布 |

### status 状态机

```
draft → (analyze完成) → reviewed → (人工通过) → published
                              ↓
                         (人工拒绝) → archived
                              ↓
                         (过期) → archived
```

---

## Agent 角色与工作流

| Agent | 职责 | 输入 → 输出 |
|-------|------|-------------|
| Collector | 抓取原始内容 | 数据源配置 → 原始 JSON |
| Analyzer | AI 分析、摘要、分类 | 原始 JSON → 结构化条目 |
| Organizer | 去重、格式化分发内容、执行分发 | 审核后条目 → 分发内容 |

### 工作流

```
数据源 → Collector → [raw/]
              ↓
           Analyzer → [待审核队列]
              ↓
          人工审核 → [reviewed/]
              ↓
          Organizer → [待发布队列]
              ↓
         Distributor → 飞书 + 本地预览
```

### 并行策略

- 每个数据源独立 Collector 实例，并行采集
- Analyzer 单实例顺序处理（避免 API 并发限流）
- Organizer 批量处理，每批 10 条

### 去重规则

- 主键：`source_url`（同一 URL 视为同一条目）
- 辅助：`title` 模糊匹配（相似度 > 0.85 需人工确认）
- 跨数据源：优先保留 GitHub Trending 来源（更完整元数据）

### 调度

- 内置调度器（APScheduler），每日 8:00 自动运行
- 支持手动触发：`python -m ai_knowledge_base.cli run-all`

---

## 存储方案

### 职责划分

- **SQLite**：主数据库（`knowledge/kb.db`），存储所有条目和状态
- **JSON**：原始数据（`knowledge/raw/`）、配置文件、单条导出

### SQLite Schema

```sql
CREATE TABLE entries (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_url TEXT UNIQUE,
    source_type TEXT NOT NULL,
    summary TEXT,
    content TEXT,
    tags TEXT,  -- JSON array
    category TEXT,
    status TEXT NOT NULL,
    quality_score INTEGER,
    collected_at TEXT NOT NULL,
    analyzed_at TEXT,
    published_at TEXT,
    publish_channels TEXT,  -- JSON array
    publish_status TEXT,  -- JSON object
    metadata TEXT,  -- JSON object
    version INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_status ON entries(status);
CREATE INDEX idx_collected_at ON entries(collected_at);
CREATE INDEX idx_source_type ON entries(source_type);
```

### 并发写入

- SQLite 使用 WAL 模式支持并发读
- 写入通过队列串行化，单进程负责写入

---

## AI 配置

```yaml
# config/config.yaml
ai:
  max_retries: 3
  timeout: 30
  temperature: 0.7
```

模型连接由运行环境配置，项目代码不感知具体模型。

---

## 分发配置

```yaml
# config/config.yaml
distribute:
  channels:
    - feishu
  preview_dir: knowledge/preview/
```

### 飞书格式

富文本卡片：标题 + 摘要 + 标签 + 来源链接

### 限流

- 飞书：每分钟最多 150 条消息
- 批量发送时自动排队，遵守限流

### 预览

```bash
python -m ai_knowledge_base.cli preview <id>
# 输出到 knowledge/preview/<id>.md
```

---

## 异常处理

### 重试策略

| 场景 | 处理方式 |
|------|----------|
| 网络超时 | 重试 3 次，指数退避（1s, 2s, 4s） |
| 429 限流 | 等待 Retry-After 头指定时间，无头则等待 60 秒 |
| 5xx 服务器错误 | 重试 3 次，间隔 10 秒 |
| 4xx 客户端错误 | 不重试，记录日志后跳过 |
| 解析失败 | 记录原始数据到 raw/，标记 status=error |

### 熔断机制

- 连续失败 5 次：暂停该数据源 10 分钟
- 连续失败 10 次：暂停该数据源 1 小时
- 恢复后首次成功：重置失败计数

---

## 采集频率限制

| 数据源 | 限制 |
|--------|------|
| GitHub Trending | 每 5 分钟最多 1 次 |
| Hacker News API | 每秒最多 10 次请求 |
| 通用网页 | 每 60 秒最多 1 次，随机 jitter 5-15 秒 |

---

## 测试规范

### 框架

pytest + pytest-cov

### 覆盖率要求

| 模块类型 | 最低覆盖率 |
|----------|------------|
| 核心模块（agents/、skills/） | 80% |
| 配置和工具模块 | 60% |
| 整体 | 70% |

### 测试分类

```
tests/
├── unit/           # 单元测试，mock 外部依赖
├── integration/    # 集成测试，使用真实 API（需配置）
└── conftest.py     # 共享 fixtures
```

### Mock 策略

- 外部 HTTP 请求：使用 pytest-httpx 或 responses
- AI 模型调用：使用固定返回值的 mock
- 文件系统：使用 tmp_path fixture

### CI 配置

- 每次提交运行：lint + 单元测试
- 每日定时运行：集成测试
- 覆盖率报告上传到 codecov

---

## 密钥管理

### 环境变量

所有敏感配置通过环境变量注入。

### 本地开发

```bash
# .env.example（提交到 Git，作为模板）
FEISHU_APP_ID=
FEISHU_APP_SECRET=
GITHUB_TOKEN=
```

### .gitignore 补充

```
.env
*.pem
secrets/
```

### 配置加载

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    feishu_app_id: str
    feishu_app_secret: str
    github_token: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 清理策略

### 自动清理

每日运行结束后执行清理。

### 清理命令

```bash
python -m ai_knowledge_base.cli cleanup [--dry-run]
# --dry-run：仅显示将要删除的文件，不实际删除
```

### archive 上限

- 按月归档，单月文件超过 100MB 压缩为 .zip
- 保留最近 12 个月的归档

---

## 合规

- 遵守目标网站 ToS 和 robots.txt
- 摘要需 AI 原创，禁止复制原文
- 不采集/存储用户个人信息（公开用户名除外）
- 遵守各平台 API 限制

### robots.txt 检测

- Collector 启动时自动检查目标域名 robots.txt
- 解析 User-Agent 和 Disallow 规则
- 违规时拒绝采集并记录告警日志

### 原创性保障

- 摘要长度限制为原文的 20% 以内
- 分发时强制附带 source_url 作为来源声明

---

## 红线

| # | 禁止操作 | 后果 |
|---|----------|------|
| 1 | 爬取需登录页面 | 账号封禁 |
| 2 | 绕过 robots.txt | 法律风险 |
| 3 | 采集频率超标 | IP 被封 |
| 4 | 存储敏感信息（API Key、密码） | 安全漏洞 |
| 5 | 发布未审核内容 | 质量失控 |
| 6 | 忽略异常处理 | 系统不稳定 |
| 7 | 日志记录敏感数据 | 隐私泄露 |
| 8 | 硬编码配置 | 维护困难 |

---

## 规范修订

| 日期 | 版本 | 改动 |
|------|------|------|
| 2026-05-14 | v1.0 | 初始版本 |
