# Memory 对代码生成的影响对比

## 对比表格

| 维度 | 有 Memory | 无 Memory |
|------|-----------|-----------|
| **命名风格** | `snake_case` 变量/函数，`PascalCase` 类名，如 `get_repo_info`、`GitHubAPIError` | 随意命名，可能使用 `getRepoInfo`、`github_api_error` 等混合风格 |
| **Docstring** | Google 风格，包含 Args、Returns、Raises 完整说明 | 简单描述或无 docstring，格式不统一（可能用 NumPy、Sphinx 风格） |
| **日志方式** | 使用 `logging` 模块，如 `logger.info()`、`logger.error()` | 直接使用 `print()` 语句，或无日志输出 |
| **错误处理** | 自定义异常类，完整捕获并记录日志，区分 HTTP 错误类型 | 简单 `try/except`，可能吞掉异常或使用通用 `Exception` |
| **文件位置** | 遵循项目结构，工具函数放 `utils/` 目录 | 随意放置，可能在根目录或与业务代码混合 |

## 结论

Memory 的存在使 AI 能够**持续遵循项目既定规范**，生成的代码在风格、质量和可维护性上保持一致。无 Memory 时，AI 仅依赖通用知识，输出风格随机性强，与项目现有代码形成割裂。

以本项目为例，有 Memory 的代码：
- 自动应用 PEP 8 和 Google docstring 规范
- 不会出现裸 `print()` 调试语句
- 异常处理符合项目定义的 `GitHubAPIError` 模式
- 文件自动归档到 `utils/` 目录

这种一致性降低了代码审查成本，也避免了因风格冲突导致的反复修改。
