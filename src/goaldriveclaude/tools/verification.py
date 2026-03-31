"""验证工具 - 测试运行、语法检查、输出比对"""

import subprocess
import py_compile
import sys
import time
from pathlib import Path


def run_tests(path: str = ".", test_filter: str = "") -> dict:
    """运行测试

    Args:
        path: 测试路径
        test_filter: 测试过滤条件

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
        test_path = Path(path)

        # 检查是否有 pytest
        pytest_check = subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            capture_output=True,
            timeout=10,
        )

        if pytest_check.returncode == 0:
            # 使用 pytest
            cmd = [sys.executable, "-m", "pytest", str(test_path), "-v"]
            if test_filter:
                cmd.extend(["-k", test_filter])
        else:
            # 使用 unittest
            cmd = [sys.executable, "-m", "unittest", "discover", str(test_path), "-v"]

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        result["success"] = process.returncode == 0
        result["output"] = process.stdout
        if process.stderr:
            result["error"] = process.stderr

    except subprocess.TimeoutExpired:
        result["error"] = "测试运行超时"
    except Exception as e:
        result["error"] = f"运行测试失败: {str(e)}"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return result


def check_syntax(path: str) -> dict:
    """检查文件语法

    Args:
        path: 文件路径

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

        suffix = file_path.suffix.lower()

        if suffix == ".py":
            # Python 语法检查
            try:
                py_compile.compile(str(file_path), doraise=True)
                result["success"] = True
                result["output"] = "Python 语法检查通过"
            except py_compile.PyCompileError as e:
                result["error"] = f"Python 语法错误: {str(e)}"

        elif suffix in [".js", ".mjs"]:
            # JavaScript 语法检查
            process = subprocess.run(
                ["node", "--check", str(file_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            result["success"] = process.returncode == 0
            if result["success"]:
                result["output"] = "JavaScript 语法检查通过"
            else:
                result["error"] = process.stderr

        else:
            result["output"] = f"暂不支持 {suffix} 文件的语法检查"
            result["success"] = True

    except Exception as e:
        result["error"] = f"语法检查失败: {str(e)}"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return result


def check_file_exists(path: str) -> dict:
    """检查文件是否存在

    Args:
        path: 文件路径

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
        if file_path.exists():
            result["success"] = True
            if file_path.is_file():
                result["output"] = f"文件存在: {path}"
            elif file_path.is_dir():
                result["output"] = f"目录存在: {path}"
            else:
                result["output"] = f"路径存在: {path}"
        else:
            result["error"] = f"路径不存在: {path}"

    except Exception as e:
        result["error"] = f"检查失败: {str(e)}"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return result


def compare_output(command: str, expected_contains: list[str]) -> dict:
    """执行命令并检查输出是否包含预期内容

    Args:
        command: 要执行的命令
        expected_contains: 预期输出应包含的字符串列表

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
        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = process.stdout + process.stderr
        result["output"] = output[:2000]  # 限制输出长度

        missing = []
        for expected in expected_contains:
            if expected not in output:
                missing.append(expected)

        if missing:
            result["error"] = f"输出中未找到以下内容: {missing}"
        else:
            result["success"] = True

    except subprocess.TimeoutExpired:
        result["error"] = "命令执行超时"
    except Exception as e:
        result["error"] = f"执行失败: {str(e)}"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return result
