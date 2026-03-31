"""Python 执行工具 - 在子进程中执行 Python 代码"""

import subprocess
import sys
import time
import tempfile
import os


def run_python(code: str, timeout: int = 30) -> dict:
    """执行 Python 代码

    Args:
        code: 要执行的 Python 代码
        timeout: 超时时间（秒），默认 30

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
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            # 执行代码
            process = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            result["success"] = process.returncode == 0
            result["output"] = process.stdout
            if process.stderr:
                result["error"] = process.stderr

        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except:
                pass

    except subprocess.TimeoutExpired:
        result["error"] = f"代码执行超时（超过 {timeout} 秒）"
    except Exception as e:
        result["error"] = f"执行代码失败: {str(e)}"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return result
