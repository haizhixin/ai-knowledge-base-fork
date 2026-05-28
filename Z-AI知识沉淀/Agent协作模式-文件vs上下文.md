# Agent 协作模式：文件协作 vs 上下文共享

## 两种模式对比

| 维度 | 上下文共享 | 文件协作 |
|------|-----------|----------|
| 数据传递 | 对话历史自动传递 | 读写文件显式传递 |
| 耦合性 | 强耦合，上游失败下游无法运行 | 完全解耦，可独立运行 |
| 可追溯 | 对话历史可能被压缩丢失 | 文件持久化，可审计 |
| 恢复能力 | 需从头重跑 | 可从任意步骤恢复 |
| 上下文占用 | 累积消耗 token | 不占用上下文 |

## 本项目正确架构

```
Collector ──写入──► knowledge/raw/
                          │
Analyzer ◄──读取──────────┤
    │
    └──写入──► knowledge/processed/
                      │
Organizer ◄──读取─────┤
    │
    └──写入──► knowledge/articles/
```

## 刚才测试的问题

角色定义禁止 Collector/Analyzer 写文件，导致：
- 它们只能返回数据给主 Agent
- 主 Agent 手动在上下文中传递数据
- 变成了「上下文共享」模式，而非预期的「文件协作」

## 解决方案

**方案 1（推荐）**：放宽写入权限，限定目录
```markdown
# Collector: Write 仅限 knowledge/raw/
# Analyzer: Write 仅限 knowledge/processed/
```

**方案 2**：保持无写入权限，由调度层负责文件写入（增加主 Agent 职责）

## 结论

- 文件协作 = Agent 解耦 + 可独立调度 + 可恢复
- 上下文共享 = Agent 耦合 + 依赖对话历史 + 不可恢复
- 本项目应采用文件协作，需调整 Collector/Analyzer 的 Write 权限

---

## 实际案例分析：2026-05-23 测试

### 实际执行的是「方案 2」

```
我（主 Agent/调度层）
  │
  ├─► Collector Agent（禁止 Write）
  │       └─ 返回 JSON → 我在上下文中保存
  │
  ├─► 我把数据传给 Analyzer Agent（禁止 Write）
  │       └─ 返回 JSON → 我在上下文中保存
  │
  └─► 我把数据传给 Organizer Agent（允许 Write）
          └─ 写入 knowledge/articles/
```

### 与预期的差距

| 阶段 | 预期（文件协作） | 实际（上下文共享） |
|------|------------------|-------------------|
| Collector | 写入 `knowledge/raw/` | 返回数据，未写文件 |
| Analyzer | 写入 `knowledge/processed/` | 返回数据，未写文件 |
| Organizer | 写入 `knowledge/articles/` | 写入 `knowledge/articles/` ✓ |

### 根因

角色定义中 Collector 和 Analyzer 禁止 Write 权限，导致：
1. 无法参与文件协作
2. 只能依赖主 Agent 在上下文中传递数据
3. 整个流程退化为「上下文共享」模式

### 修正建议

采用方案 1，修改角色定义：

```markdown
# Collector Agent
## 允许权限
| Write | 仅限 knowledge/raw/ 目录 |

# Analyzer Agent  
## 允许权限
| Write | 仅限 knowledge/processed/ 目录 |
```

这样才能实现真正的文件协作架构。