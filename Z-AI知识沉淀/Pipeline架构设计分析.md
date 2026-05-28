# Pipeline 架构设计分析

> 来源：`pipeline/pipeline.py` 代码分析
> 日期：2026-05-27

## 概述

`pipeline/pipeline.py` 实现了一个清晰的四步流水线架构，每步职责单一、数据单向流动。

## 四步流水线概览

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Collector  │───▶│  Analyzer   │───▶│  Organizer  │───▶│    Saver    │
│   (采集)    │    │   (分析)    │    │   (整理)    │    │   (保存)    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                  │                  │                  │
      ▼                  ▼                  ▼                  ▼
  RawArticle      AnalyzedArticle    AnalyzedArticle     JSON 文件
```

## 数据模型

| 阶段 | 数据类 | 核心字段 |
|------|--------|----------|
| 采集 | `RawArticle` | id, title, source_url, description, metadata |
| 分析 | `AnalyzedArticle` | 继承上方 + summary, content, tags, category, quality_score |

---

## Step 1: Collector（采集）

**职责**：从外部数据源抓取原始内容

**输入**：配置常量（GitHub API URL、RSS Feeds）

**输出**：`list[RawArticle]`

```
GitHub Search API ──┐
                    ├──▶ Collector.collect() ──▶ RawArticle[]
RSS Feeds ──────────┘
```

**关键实现**：
- GitHub：调用 Search API，查询 AI/LLM/Agent 相关项目，按 stars 排序
- RSS：简易正则解析 `<item>` 元素，不依赖 XML 库
- ID 生成：`kb_YYYYMMDD_来源_URL哈希前8位`

**核心代码位置**：`pipeline/pipeline.py:108-289`

---

## Step 2: Analyzer（分析）

**职责**：调用 LLM 进行摘要、分类、评分

**输入**：`RawArticle`

**输出**：`AnalyzedArticle | None`

```
RawArticle ──▶ 构建提示词 ──▶ LLM 调用 ──▶ 解析 JSON 响应 ──▶ AnalyzedArticle
```

**提示词设计**（`_build_analysis_prompt`）：
- 要求输出纯 JSON
- summary: 100-200 字简洁摘要
- content: 500-800 字详细分析
- tags: 3-5 个标签
- category: framework/paper/tool/news
- quality_score: 0-100 评分

**容错机制**：
- JSON 解析失败返回 None
- 字段缺失/类型错误时做默认处理
- `dry_run` 模式返回 mock 数据

**核心代码位置**：`pipeline/pipeline.py:295-444`

---

## Step 3: Organizer（整理）

**职责**：去重、格式标准化、数据校验

**输入**：`list[AnalyzedArticle]`

**输出**：`list[AnalyzedArticle]`（过滤后）

```
AnalyzedArticle[] ──▶ 去重 ──▶ 标准化 ──▶ 校验 ──▶ 有效文章[]
```

**去重规则**：
1. URL 去重（主键）
2. 标题小写完全匹配去重

**标准化处理**：
- 标题/摘要/内容 strip
- 标签去重 + 小写统一
- 强制 3-5 个标签

**校验规则**：
- 必填字段非空
- summary ≥ 50 字
- content ≥ 100 字
- quality_score 在 0-100 范围

**核心代码位置**：`pipeline/pipeline.py:451-578`

---

## Step 4: Saver（保存）

**职责**：持久化到文件系统

**输入**：`list[AnalyzedArticle]`

**输出**：保存数量

```
AnalyzedArticle[] ──▶ 序列化为 JSON ──▶ 写入文件
```

**存储策略**：
- 原始数据：`knowledge/raw/raw_YYYYMMDD_HHMMSS.json`（批量）
- 文章数据：`knowledge/articles/{id}.json`（每条独立文件）

**核心代码位置**：`pipeline/pipeline.py:585-654`

---

## Pipeline 编排（`Pipeline.run()`）

```python
def run(self) -> dict[str, Any]:
    # Step 1: 采集
    raw_articles = []
    if "github" in sources:
        raw_articles.extend(collector.collect_github(limit))
    if "rss" in sources:
        raw_articles.extend(collector.collect_rss(limit))

    # Step 2: 分析（顺序处理）
    analyzed_articles = [
        analyzer.analyze(article)
        for article in raw_articles
        if analyzer.analyze(article)
    ]

    # Step 3: 整理
    organized_articles = organizer.organize(analyzed_articles)

    # Step 4: 保存
    saver.save_articles(organized_articles)
```

**统计返回**：
```python
{
    "collected": 20,   # 采集数量
    "analyzed": 18,    # 分析成功数量
    "organized": 15,   # 整理后数量
    "saved": 15,       # 保存数量
    "errors": []
}
```

**核心代码位置**：`pipeline/pipeline.py:661-753`

---

## 设计特点总结

| 特点 | 说明 |
|------|------|
| 单向数据流 | RawArticle → AnalyzedArticle，无回溯 |
| 阶段独立 | 每个类职责单一，可单独测试 |
| 失败隔离 | 某条记录分析失败不影响其他 |
| 可观测性 | 每阶段有日志 + 统计 |
| dry-run 支持 | 跳过 LLM 调用，便于测试 |

---

## 命令行用法

```bash
# 完整运行
python pipeline/pipeline.py --sources github,rss --limit 20

# 仅 GitHub
python pipeline/pipeline.py --sources github --limit 5

# 干跑模式（不调用 LLM）
python pipeline/pipeline.py --sources github --limit 5 --dry-run

# 详细日志
python pipeline/pipeline.py --verbose
```

---

## 扩展方向

1. **并行化**：Analyzer 阶段可并行处理多篇文章
2. **增量采集**：记录已采集 URL，避免重复
3. **错误重试**：对失败的分析任务支持重试队列
4. **监控告警**：集成 Prometheus 指标导出
