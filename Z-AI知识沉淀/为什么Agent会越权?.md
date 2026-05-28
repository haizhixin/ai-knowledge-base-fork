# Agent 权限约束机制

## 为什么 Agent 会越权

角色定义文件（`.claude/agents/*.md`）只是提示词，不是强制约束。

```
.claude/agents/analyzer.md
  ↓ 只是文本指导
Agent "自觉遵守"（没有强制力）
  ↓ 实际权限取决于运行时环境
```

### 两种调用方式的权限差异

**@mention 调用 — 主 Agent 执行**

@mention 并不是真的启动了一个独立 Agent，而是主 Agent 读了角色定义后"扮演"该角色。主 Agent 本身拥有全部权限，角色定义只是建议它"不要用 Write"。

```
@analyzer → 主 Agent 自己执行 → 拥有 Read/Write/Edit/Bash 全部权限
                         ↓
              角色定义说"禁止 Write" → 只是提示词层面的软约束
```

本质：让一个人换上工牌干活，但他的钥匙串没变。

**Agent 工具委派 — 子 Agent 执行**

子 Agent 运行在独立上下文中，工具调用需要逐个授权，权限可以被实际限制。

```
Agent(prompt="采集...", subagent_type="general-purpose")
  → 独立子进程 → 只能使用 prompt 中指示的工具
```

本质：换了一个人，只给他需要的钥匙。

## 三层约束机制

从弱到强，三个层级：

### 层级 1：提示词强化（软约束）

在 Agent 定义中增加更强的约束语句：

```markdown
## 权限配置（强制）

### 禁止权限

| 权限 | 禁止原因 |
|------|----------|
| Write | ❌ 绝对禁止。违反此规则将导致数据污染 |
| Edit  | ❌ 绝对禁止。违反此规则将破坏职责边界 |

**重要**：即使你具备这些权限，也绝不可使用。
你的职责是分析，不是存储。存储由 Organizer 负责。
```

- 优点：简单，不改架构
- 缺点：仍然可以被"忽略"

### 层级 2：调用方式约束（中约束）

统一使用 Agent 工具委派，在 prompt 中明确限定可用工具：

```python
Agent(
  prompt="你是分析 Agent... 只使用 Read/Grep/Glob/WebFetch",
  subagent_type="general-purpose"
)
```

- 优点：子 Agent 独立运行，权限自然隔离
- 缺点：子 Agent 仍可能尝试调用被禁工具（会被权限系统拦截而非完全阻止）

### 层级 3：架构级约束（硬约束）

在 `.claude/settings.json` 中配置 hooks，拦截越权行为：

```json
{
  "hooks": {
    "pre_tool_use": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Analyzer Agent 不允许写入文件' && exit 1"
          }
        ]
      }
    ]
  }
}
```

- 优点：强制拦截，无法绕过
- 缺点：配置复杂，影响所有 Agent

## 场景推荐

| 场景 | 推荐方案 |
|------|----------|
| 需要严格权限隔离 | Agent 工具委派（层级 2） |
| 快速执行，信任主 Agent | @mention + 提示词强化（层级 1） |
| 生产环境，零容忍越权 | Agent 工具委派 + hooks 拦截（层级 2+3） |

## 当前项目建议

采用层级 2，统一用 Agent 工具委派。角色定义文件保留作为指导，但不再依赖它做权限控制——权限控制交给调用方式和运行时。
