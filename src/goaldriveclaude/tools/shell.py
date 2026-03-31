"""Shell 工具 - Bash 命令执行"""

import subprocess
import time
from pathlib import Path

from goaldriveclaude.core.models import CommandBlacklist


def run_bash(command: str, timeout: int = 30, working_dir: str = ".") -> dict:
    """执行 Bash 命令

    Args:
        command: 要执行的命令
        timeout: 超时时间（秒），默认 30
        working_dir: 工作目录

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

    # 安全检查 - 检查黑名单
    is_blocked, reason = CommandBlacklist.is_blocked(command)
    if is_blocked:
        result["error"] = f"命令被阻止: {reason}"
        result["duration_ms"] = int((time.time() - start_time) * 1000)
        return result

    try:
        # 执行命令
        process = subprocess.run(
            command,
            shell=True,
            cwd=Path(working_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        result["success"] = process.returncode == 0
        result["output"] = process.stdout
        if process.stderr:
            result["error"] = process.stderr

    except subprocess.TimeoutExpired:
        result["error"] = f"命令执行超时（超过 {timeout} 秒）"
    except Exception as e:
        result["error"] = f"执行命令失败: {str(e)}"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return result
