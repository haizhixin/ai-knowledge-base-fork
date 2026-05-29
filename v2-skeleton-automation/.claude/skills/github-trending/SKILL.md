---
name: github-trending
description: 当需要采集 GitHub 热门开源项目时使用此技能
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebFetch
---

# GitHub Trending 技能

## 使用场景

- 每日自动采集 AI/LLM/Agent 领域热门开源项目
- 发现新技术趋势和高 Star 增长项目
- 为知识库提供高质量的 GitHub 数据源

## 执行步骤

### 1. 搜索热门仓库

使用 GitHub API 获取热门仓库列表：

```
GET https://api.github.com/search/repositories
参数：
- q: topic:ai OR topic:llm OR topic:agent OR topic:machine-learning
- sort: stars
- order: desc
- per_page: 100
```

### 2. 提取信息

从 API 响应中提取关键字段：

- `full_name`: 完整项目名（owner/repo）
- `html_url`: 项目链接
- `description`: 项目描述
- `stargazers_count`: Star 数
- `language`: 主要编程语言
- `topics`: 主题标签

### 3. 过滤项目

**纳入条件**（满足任一）：
- topics 包含：`ai`, `llm`, `agent`, `machine-learning`, `deep-learning`, `nlp`, `transformer`, `langchain`, `openai`, `gpt`
- description 包含关键词：`AI`, `LLM`, `Agent`, `GPT`, `ChatGPT`, `LangChain`

**排除条件**（满足任一）：
- 项目名以 `awesome-` 开头（Awesome 列表）
- `stargazers_count < 100`
- 已归档（`archived: true`）
- 30 天内无更新

### 4. 去重处理

- 主键：`html_url`
- 检查 `knowledge/raw/github-trending-*.json` 已有记录
- 跳过已采集项目

### 5. 撰写中文摘要

摘要公式：**项目名 + 做什么 + 为什么值得关注**

示例：
> LangChain 是一个用于构建 LLM 应用的框架，提供链式调用、Agent 编排、RAG 等核心能力，适合快速开发 AI 应用原型。

要求：
- 长度：50-100 字
- 语言：中文
- 必须原创，不可直接复制 description

### 6. 排序取 Top 15

按 `stargazers_count` 降序排列，取前 15 条。

### 7. 输出 JSON

保存到 `knowledge/raw/github-trending-YYYY-MM-DD.json`

## 注意事项

- **频率限制**：GitHub API 未认证限制 60 次/小时，建议使用 Token
- **User-Agent**：请求头必须包含 `User-Agent`
- **错误处理**：遇到 403/429 时等待 Retry-After 后重试
- **编码规范**：禁止裸 `print()`，使用 `logging` 模块
- **合规**：摘要必须 AI 原创，长度 ≤ 原描述 50%

## 输出格式

```json
{
  "source": "github_trending",
  "skill": "github-trending",
  "collected_at": "2024-05-15T08:30:00Z",
  "items": [
    {
      "name": "langchain-ai/langchain",
      "url": "https://github.com/langchain-ai/langchain",
      "summary": "LangChain 是一个用于构建 LLM 应用的框架，提供链式调用、Agent 编排、RAG 等核心能力，适合快速开发 AI 应用原型。",
      "stars": 85000,
      "language": "Python",
      "topics": ["llm", "agent", "langchain", "nlp"]
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source | string | 是 | 固定值 `github_trending` |
| skill | string | 是 | 固定值 `github-trending` |
| collected_at | string | 是 | 采集时间（ISO 8601） |
| items | array | 是 | 项目列表（最多 15 条） |
| items[].name | string | 是 | 完整项目名（owner/repo） |
| items[].url | string | 是 | 项目链接 |
| items[].summary | string | 是 | 中文摘要（50-100 字） |
| items[].stars | integer | 是 | Star 数 |
| items[].language | string | 否 | 主要编程语言 |
| items[].topics | array | 否 | 主题标签列表 |
