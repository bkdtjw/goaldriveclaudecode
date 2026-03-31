"""代码分析工具 - Grep、符号查找"""

import os
import re
import time
from pathlib import Path


def grep_search(pattern: str, path: str = ".", file_type: str = "") -> dict:
    """搜索文件内容（跨平台实现）

    Args:
        pattern: 搜索模式
        path: 搜索路径
        file_type: 文件类型过滤（如 'py', 'js'）

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
        search_path = Path(path)
        if not search_path.exists():
            result["error"] = f"路径不存在: {path}"
            return result

        matches = []

        # 遍历目录
        for root, _, files in os.walk(search_path):
            for filename in files:
                # 文件类型过滤
                if file_type and not filename.endswith(f".{file_type}"):
                    continue

                file_path = Path(root) / filename

                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        for line_num, line in enumerate(f, 1):
                            if re.search(pattern, line):
                                matches.append(f"{file_path}:{line_num}:{line.rstrip()}")
                except Exception:
                    continue

        if matches:
            result["success"] = True
            result["output"] = "\n".join(matches[:50])
            if len(matches) > 50:
                result["output"] += f"\n\n... (还有 {len(matches) - 50} 个匹配)"
        else:
            result["success"] = True
            result["output"] = f"未找到匹配 '{pattern}' 的内容"

    except Exception as e:
        result["error"] = f"搜索失败: {str(e)}"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return result
