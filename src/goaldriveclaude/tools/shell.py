"""Shell 工具 - Bash 命令执行"""

import subprocess
import time
from pathlib import Path

# 危险命令黑名单
BLACKLISTED_COMMANDS = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf *",
    "format",
    "mkfs",
    "dd if=/dev/zero",
    ":(){:|:&};:",  # fork bomb
]

BLACKLISTED_PATTERNS = [
    "> /dev/sda",
    "curl *| *sh",
    "wget *| *sh",
]


def _is_command_blocked(command: str) -> tuple[bool, str]:
    """检查命令是否在黑名单中"""
    cmd_lower = command.lower()

    for blocked in BLACKLISTED_COMMANDS:
        if blocked in cmd_lower:
            return True, f"包含危险命令: {blocked}"

    # 简单模式匹配
    import re
    for pattern in BLACKLISTED_PATTERNS:
        try:
            if re.search(pattern, command, re.IGNORECASE):
                return True, f"匹配危险模式: {pattern}"
        except re.error:
            continue

    return False, ""


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
    is_blocked, reason = _is_command_blocked(command)
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
