"""文件系统工具 - 文件读写、搜索"""

import os
import time
from pathlib import Path
from typing import Optional

from goaldriveclaude.core.models import ToolResultModel


def read_file(path: str, limit: int = 100, offset: int = 0) -> dict:
    """读取文件内容

    Args:
        path: 文件路径
        limit: 读取的最大行数，默认 100
        offset: 起始行偏移量，默认 0

    Returns:
        工具执行结果字典
    """
    start_time = time.time()
    result = {
        "success": False,
        "output": "",
        "error": "",
        "duration_ms": 0,
    }

    try:
        file_path = Path(path)
        if not file_path.exists():
            result["error"] = f"文件不存在: {path}"
            return result

        if not file_path.is_file():
            result["error"] = f"路径不是文件: {path}"
            return result

        # 读取文件
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # 应用偏移和限制
        total_lines = len(lines)
        start_line = offset
        end_line = min(offset + limit, total_lines)
        selected_lines = lines[start_line:end_line]

        content = "".join(selected_lines)
        result["success"] = True
        result["output"] = content
        if end_line < total_lines:
            result["output"] += f"\n\n... (还有 {total_lines - end_line} 行)"

    except Exception as e:
        result["error"] = f"读取文件失败: {str(e)}"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return result


def write_file(path: str, content: str) -> dict:
    """写入文件内容（覆盖）

    Args:
        path: 文件路径
        content: 文件内容

    Returns:
        工具执行结果字典
    """
    start_time = time.time()
    result = {
        "success": False,
        "output": "",
        "error": "",
        "duration_ms": 0,
    }

    try:
        file_path = Path(path)

        # 确保父目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        result["success"] = True
        result["output"] = f"文件已写入: {path}"

    except Exception as e:
        result["error"] = f"写入文件失败: {str(e)}"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return result


def edit_file(path: str, old_text: str, new_text: str) -> dict:
    """精确编辑文件 - 替换指定文本

    Args:
        path: 文件路径
        old_text: 要替换的旧文本
        new_text: 新文本

    Returns:
        工具执行结果字典
    """
    start_time = time.time()
    result = {
        "success": False,
        "output": "",
        "error": "",
        "duration_ms": 0,
    }

    try:
        file_path = Path(path)
        if not file_path.exists():
            result["error"] = f"文件不存在: {path}"
            return result

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # 检查 old_text 是否存在
        if old_text not in content:
            result["error"] = f"未找到要替换的文本，请检查 old_text 是否准确"
            return result

        # 替换文本
        new_content = content.replace(old_text, new_text, 1)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        result["success"] = True
        result["output"] = f"文件已编辑: {path}"

    except Exception as e:
        result["error"] = f"编辑文件失败: {str(e)}"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return result


def list_directory(path: str = ".", max_depth: int = 1) -> dict:
    """列出目录内容

    Args:
        path: 目录路径
        max_depth: 最大递归深度，默认 1

    Returns:
        工具执行结果字典
    """
    start_time = time.time()
    result = {
        "success": False,
        "output": "",
        "error": "",
        "duration_ms": 0,
    }

    try:
        dir_path = Path(path)
        if not dir_path.exists():
            result["error"] = f"目录不存在: {path}"
            return result

        if not dir_path.is_dir():
            result["error"] = f"路径不是目录: {path}"
            return result

        lines = []
        lines.append(f"目录: {dir_path.absolute()}")
        lines.append("")

        def list_recursive(current_path: Path, current_depth: int, prefix: str = ""):
            if current_depth > max_depth:
                return

            try:
                items = sorted(current_path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError:
                lines.append(f"{prefix}[权限拒绝]")
                return

            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "

                if item.is_dir():
                    lines.append(f"{prefix}{connector}{item.name}/")
                    if current_depth < max_depth:
                        extension = "    " if is_last else "│   "
                        list_recursive(item, current_depth + 1, prefix + extension)
                else:
                    lines.append(f"{prefix}{connector}{item.name}")

        list_recursive(dir_path, 1)
        result["success"] = True
        result["output"] = "\n".join(lines)

    except Exception as e:
        result["error"] = f"列出目录失败: {str(e)}"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return result


def find_files(pattern: str, directory: str = ".") -> dict:
    """查找匹配的文件

    Args:
        pattern: 文件名模式（支持通配符 * 和 ?）
        directory: 搜索目录

    Returns:
        工具执行结果字典
    """
    start_time = time.time()
    result = {
        "success": False,
        "output": "",
        "error": "",
        "duration_ms": 0,
    }

    try:
        import fnmatch

        dir_path = Path(directory)
        if not dir_path.exists():
            result["error"] = f"目录不存在: {directory}"
            return result

        matches = []
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if fnmatch.fnmatch(filename, pattern):
                    matches.append(Path(root) / filename)

        if matches:
            result["success"] = True
            result["output"] = "\n".join(str(m) for m in matches[:50])  # 限制输出数量
            if len(matches) > 50:
                result["output"] += f"\n\n... (还有 {len(matches) - 50} 个匹配)"
        else:
            result["success"] = True
            result["output"] = f"未找到匹配 '{pattern}' 的文件"

    except Exception as e:
        result["error"] = f"查找文件失败: {str(e)}"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return result
