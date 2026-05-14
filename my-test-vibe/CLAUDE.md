# AI 知识库助手

## 编码规范

### Python 规范

#### 风格
- PEP 8，snake_case 变量/函数，PascalCase 类名
- Google 风格 docstring
- 禁止裸 `print()`，使用 `logging` 模块
- 类型注解：使用 `list[dict]` 而非 `List[Dict]`（Python 3.9+）

#### 示例

```python
def fetch_trending(topic: str, limit: int = 10) -> list[dict]:
    """从 GitHub Trending 获取指定主题的热门项目。

    Args:
        topic: 主题名称，如 'ai'、'llm'、'agent'。
        limit: 返回结果数量上限，默认为 10。

    Returns:
        包含项目信息的字典列表。

    Raises:
        NetworkError: 网络请求失败时抛出。
    """
    logger.info("开始采集 GitHub Trending: topic=%s", topic)
    ...
```

#### 工具链
- 格式化：`ruff format`
- Lint：`ruff check`
- 类型检查：`pyright` 或 `mypy --strict`

---

### TypeScript 规范

#### 风格
- camelCase 变量/函数，PascalCase 类/接口/类型/React 组件
- 文件名：kebab-case（工具模块）或 PascalCase（React 组件）
- 优先 `interface` 定义数据结构，`type` 定义联合/交叉类型
- 显式返回类型注解（公开函数）

#### 示例

```typescript
interface FetchOptions {
  topic: string;
  limit?: number;
}

interface TrendingItem {
  id: string;
  title: string;
  url: string;
  stars: number;
}

/**
 * 从 GitHub Trending 获取指定主题的热门项目
 */
export async function fetchTrending(options: FetchOptions): Promise<TrendingItem[]> {
  const { topic, limit = 10 } = options;
  logger.info('开始采集 GitHub Trending', { topic });
  // ...
}
```

#### React 组件

```tsx
interface ItemCardProps {
  item: TrendingItem;
  onSelect?: (id: string) => void;
}

export function ItemCard({ item, onSelect }: ItemCardProps): JSX.Element {
  return (
    <article className="item-card">
      <h3>{item.title}</h3>
      <span>{item.stars.toLocaleString()} stars</span>
    </article>
  );
}
```

#### 工具链
- 格式化：`prettier`
- Lint：`eslint` + `@typescript-eslint`
- 类型检查：`tsc --noEmit`

---

### 通用规范

#### 命名约定

| 类型 | Python | TypeScript |
|------|--------|------------|
| 变量/函数 | `snake_case` | `camelCase` |
| 类/类型 | `PascalCase` | `PascalCase` |
| 常量 | `UPPER_SNAKE_CASE` | `UPPER_SNAKE_CASE` |
| 私有成员 | `_prefix` | `#prefix` 或 `_prefix` |
| 文件名 | `snake_case.py` | `kebab-case.ts` / `PascalCase.tsx` |

#### 错误处理
- 禁止裸 `except` 或空 `catch`
- 自定义异常类继承基类（Python: `Exception`，TS: `Error`）
- 错误信息包含上下文，便于调试

#### 日志规范
- 结构化日志（JSON 格式）
- 禁止日志记录敏感信息（API Key、密码、Token）
- 统一日志级别：DEBUG < INFO < WARNING < ERROR < CRITICAL

#### 注释原则
- 代码即文档，避免冗余注释
- 复杂逻辑添加 "Why" 注释
- 公开 API 必须有 docstring/JSDoc

#### 禁止事项
| # | 禁止操作 | 后果 |
|---|----------|------|
| 1 | 硬编码配置/密钥 | 安全漏洞、维护困难 |
| 2 | `any` 类型滥用（TS） | 丧失类型安全 |
| 3 | 魔法数字/字符串 | 可读性差 |
| 4 | 深层嵌套（>3层） | 逻辑混乱 |
| 5 | 过长函数（>50行） | 难以测试维护 |
| 6 | 副作用函数无测试 | 隐患难排查 |
