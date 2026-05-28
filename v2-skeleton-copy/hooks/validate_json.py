#!/usr/bin/env python3
"""知识条目 JSON 校验脚本。

校验规则：
1. JSON 格式正确
2. 必填字段存在且类型正确
3. ID 格式：{source}-{YYYYMMDD}-{NNN}
4. status 枚举值
5. URL 格式
6. 摘要长度、标签数量
7. 可选字段范围校验

用法：
    python hooks/validate_json.py <json_file> [json_file2 ...]

退出码：
    0: 全部校验通过
    1: 存在校验错误
"""

import json
import re
import sys
from pathlib import Path


# 必填字段及其类型
REQUIRED_FIELDS: dict[str, type] = {
    "id": str,
    "title": str,
    "source_url": str,
    "summary": str,
    "tags": list,
    "status": str,
}

# status 允许的值
VALID_STATUS = {"draft", "review", "published", "archived"}

# audience 允许的值
VALID_AUDIENCE = {"beginner", "intermediate", "advanced"}

# ID 格式正则：{source}-{YYYYMMDD}-{NNN}
ID_PATTERN = re.compile(r"^[a-z0-9_]+-\d{8}-\d{3}$")

# URL 格式正则
URL_PATTERN = re.compile(r"^https?://.+")


def validate_id(value: str) -> list[str]:
    """校验 ID 格式。

    Args:
        value: ID 字段值。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors = []
    if not ID_PATTERN.match(value):
        errors.append(f"ID 格式错误: '{value}'，应为 {{source}}-{{YYYYMMDD}}-{{NNN}}")
    return errors


def validate_status(value: str) -> list[str]:
    """校验 status 值。

    Args:
        value: status 字段值。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors = []
    if value not in VALID_STATUS:
        errors.append(f"status 值错误: '{value}'，应为 {VALID_STATUS}")
    return errors


def validate_url(value: str) -> list[str]:
    """校验 URL 格式。

    Args:
        value: URL 字段值。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors = []
    if not URL_PATTERN.match(value):
        errors.append(f"URL 格式错误: '{value}'，应以 http:// 或 https:// 开头")
    return errors


def validate_summary(value: str) -> list[str]:
    """校验摘要长度。

    Args:
        value: summary 字段值。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors = []
    if len(value) < 20:
        errors.append(f"摘要过短: {len(value)} 字，最少 20 字")
    return errors


def validate_tags(value: list) -> list[str]:
    """校验标签数量。

    Args:
        value: tags 字段值。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors = []
    if len(value) < 1:
        errors.append("标签数量不足: 至少需要 1 个标签")
    return errors


def validate_score(value: int | float) -> list[str]:
    """校验 score 范围。

    Args:
        value: score 字段值。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors = []
    if not (1 <= value <= 10):
        errors.append(f"score 范围错误: {value}，应在 1-10 之间")
    return errors


def validate_audience(value: str) -> list[str]:
    """校验 audience 值。

    Args:
        value: audience 字段值。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors = []
    if value not in VALID_AUDIENCE:
        errors.append(f"audience 值错误: '{value}'，应为 {VALID_AUDIENCE}")
    return errors


def validate_item(item: dict, file_path: Path) -> list[str]:
    """校验单个知识条目。

    Args:
        item: 知识条目字典。
        file_path: 文件路径，用于错误信息。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors = []

    # 校验必填字段存在性和类型
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in item:
            errors.append(f"缺少必填字段: {field}")
        elif not isinstance(item[field], expected_type):
            actual_type = type(item[field]).__name__
            errors.append(
                f"字段类型错误: {field} 应为 {expected_type.__name__}，实际为 {actual_type}"
            )

    # 如果必填字段有缺失或类型错误，后续校验可能失败，直接返回
    if errors:
        return errors

    # 校验 ID 格式
    errors.extend(validate_id(item["id"]))

    # 校验 status 值
    errors.extend(validate_status(item["status"]))

    # 校验 URL 格式
    errors.extend(validate_url(item["source_url"]))

    # 校验摘要长度
    errors.extend(validate_summary(item["summary"]))

    # 校验标签数量
    errors.extend(validate_tags(item["tags"]))

    # 校验可选字段 score
    if "score" in item:
        if not isinstance(item["score"], (int, float)):
            errors.append(f"score 类型错误: 应为数字，实际为 {type(item['score']).__name__}")
        else:
            errors.extend(validate_score(item["score"]))

    # 校验可选字段 audience
    if "audience" in item:
        if not isinstance(item["audience"], str):
            errors.append(f"audience 类型错误: 应为 str，实际为 {type(item['audience']).__name__}")
        else:
            errors.extend(validate_audience(item["audience"]))

    return errors


def validate_file(file_path: Path) -> tuple[bool, list[str]]:
    """校验单个 JSON 文件。

    Args:
        file_path: JSON 文件路径。

    Returns:
        (是否通过, 错误信息列表)
    """
    errors = []

    # 检查文件是否存在
    if not file_path.exists():
        return False, [f"文件不存在: {file_path}"]

    # 检查文件是否为 JSON
    try:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return False, [f"JSON 解析错误: {e}"]

    # 支持单个对象或数组
    items = data if isinstance(data, list) else [data]

    # 校验每个条目
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"条目 {i + 1} 不是有效的 JSON 对象")
            continue

        item_errors = validate_item(item, file_path)
        if item_errors:
            prefix = f"[条目 {i + 1}]" if len(items) > 1 else ""
            for err in item_errors:
                errors.append(f"{prefix} {err}")

    return len(errors) == 0, errors


def main() -> int:
    """主函数。

    Returns:
        退出码：0 表示通过，1 表示失败。
    """
    if len(sys.argv) < 2:
        print("用法: python hooks/validate_json.py <json_file> [json_file2 ...]")
        return 1

    # 收集所有文件路径（支持通配符）
    file_paths: list[Path] = []
    for arg in sys.argv[1:]:
        path = Path(arg)
        if "*" in arg:
            # 通配符模式
            parent = path.parent if path.parent.exists() else Path(".")
            pattern = path.name
            file_paths.extend(sorted(parent.glob(pattern)))
        else:
            file_paths.append(path)

    if not file_paths:
        print("错误: 未找到匹配的文件")
        return 1

    # 校验所有文件
    all_passed = True
    total_files = len(file_paths)
    passed_files = 0
    total_errors = 0

    for file_path in file_paths:
        passed, errors = validate_file(file_path)
        if passed:
            print(f"✓ {file_path}")
            passed_files += 1
        else:
            print(f"✗ {file_path}")
            for err in errors:
                print(f"    - {err}")
            total_errors += len(errors)
            all_passed = False

    # 汇总统计
    print()
    print("=" * 50)
    print(f"校验完成: {passed_files}/{total_files} 文件通过")
    if total_errors > 0:
        print(f"共发现 {total_errors} 个错误")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())