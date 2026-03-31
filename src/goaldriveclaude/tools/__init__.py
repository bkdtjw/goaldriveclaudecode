"""工具注册表 - 管理和导出所有工具"""

from typing import Callable, Dict, List, Type

from langchain_core.tools import BaseTool, StructuredTool

from goaldriveclaude.tools.code_analysis import grep_search
from goaldriveclaude.tools.filesystem import (
    edit_file,
    find_files,
    list_directory,
    read_file,
    write_file,
)
from goaldriveclaude.tools.python_exec import run_python
from goaldriveclaude.tools.shell import run_bash
from goaldriveclaude.tools.verification import (
    check_file_exists,
    check_syntax,
    compare_output,
    run_tests,
)

# 工具函数列表
TOOL_FUNCTIONS: List[Callable] = [
    # 文件系统工具
    read_file,
    write_file,
    edit_file,
    list_directory,
    find_files,
    # Shell 工具
    run_bash,
    # Python 执行工具
    run_python,
    # 代码分析工具
    grep_search,
    # 验证工具
    run_tests,
    check_syntax,
    check_file_exists,
    compare_output,
]


def get_all_tools() -> List[StructuredTool]:
    """获取所有工具"""
    tools = []
    for func in TOOL_FUNCTIONS:
        tool = StructuredTool.from_function(
            func=func,
            name=func.__name__,
            description=func.__doc__ or "",
        )
        tools.append(tool)
    return tools


def get_tool_by_name(name: str) -> StructuredTool | None:
    """根据名称获取工具"""
    for tool in get_all_tools():
        if tool.name == name:
            return tool
    return None


def get_tool_names() -> List[str]:
    """获取所有工具名称"""
    return [tool.name for tool in get_all_tools()]
