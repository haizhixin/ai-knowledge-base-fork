---
name: tech-summary
description: 当需要对采集的技术内容进行深度分析总结时使用此技能
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebFetch
---

# Tech Summary 技能

## 使用场景

- 对采集的技术内容进行深度分析和质量评估
- 发现技术趋势和新兴概念
- 为知识库提供结构化的分析结果

## 执行步骤

### 1. 读取最新采集文件

从 `knowledge/raw/` 目录读取最新采集的数据文件：

- 按文件名日期排序，取最新
- 支持 JSON 格式
- 解析 items 数组

### 2. 逐条深度分析

对每个项目进行分析：

**摘要**（≤50 字）：
- 提炼核心价值
- 突出差异化特点

**技术亮点**（2-3 个）：
- 用事实说话，避免泛泛而谈
- 引用具体数据、特性、技术方案
- 示例：`支持 10 万 QPS`、`首次实现 X`、`比 Y 快 3 倍`

**评分**（1-10）+ 理由：
| 分数 | 含义 | 标准 |
|------|------|------|
| 9-10 | 改变格局 | 开创性突破、颠覆性创新、行业里程碑 |
| 7-8 | 直接有帮助 | 解决实际问题、提升效率、可落地应用 |
| 5-6 | 值得了解 | 新思路、技术储备、潜在价值 |
| 1-4 | 可略过 | 信息冗余、质量低下、价值有限 |

**标签建议**：
- 3-5 个精准标签
- 优先使用已有标签体系

### 3. 趋势发现

分析整体数据：

- **共同主题**：多个项目的共性方向
- **新概念**：首次出现的技术术语或模式
- **关联关系**：项目间的技术关联或竞争关系

### 4. 输出分析结果 JSON

保存到 `knowledge/processed/tech-summary-YYYY-MM-DD.json`

## 注意事项

- **评分约束**：15 个项目中，9-10 分不超过 2 个
- **客观公正**：避免主观臆断，评分理由需有依据
- **摘要原创**：AI 生成，不可复制原文
- **亮点具体**：用数据、事实、对比支撑
- **编码规范**：禁止裸 `print()`，使用 `logging` 模块

## 输出格式

```json
{
  "source": "github_trending",
  "skill": "tech-summary",
  "analyzed_at": "2024-05-15T09:00:00Z",
  "trends": {
    "common_themes": ["多模态 Agent", "RAG 优化"],
    "new_concepts": ["Model Context Protocol (MCP)"],
    "relationships": [
      {
        "type": "competition",
        "projects": ["langchain-ai/langchain", "run-llama/llama_index"],
        "note": "LLM 应用框架竞争"
      }
    ]
  },
  "items": [
    {
      "name": "langchain-ai/langchain",
      "url": "https://github.com/langchain-ai/langchain",
      "summary": "LLM 应用开发框架，提供链式调用和 Agent 编排能力。",
      "highlights": [
        "支持 100+ 模型集成",
        "LangGraph 实现 Agent 工作流编排",
        "RAG 组件开箱即用"
      ],
      "score": 8,
      "score_reason": "生态成熟，直接有助于 LLM 应用开发，但竞品增多",
      "suggested_tags": ["langchain", "agent", "rag", "framework"]
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source | string | 是 | 来源类型，与输入一致 |
| skill | string | 是 | 固定值 `tech-summary` |
| analyzed_at | string | 是 | 分析时间（ISO 8601） |
| trends | object | 是 | 趋势发现结果 |
| trends.common_themes | array | 是 | 共同主题列表 |
| trends.new_concepts | array | 是 | 新概念列表 |
| trends.relationships | array | 否 | 项目关联关系 |
| items | array | 是 | 分析结果列表 |
| items[].name | string | 是 | 项目名称 |
| items[].url | string | 是 | 项目链接 |
| items[].summary | string | 是 | 摘要（≤50 字） |
| items[].highlights | array | 是 | 技术亮点（2-3 个） |
| items[].score | integer | 是 | 评分（1-10） |
| items[].score_reason | string | 是 | 评分理由 |
| items[].suggested_tags | array | 是 | 标签建议（3-5 个） |
