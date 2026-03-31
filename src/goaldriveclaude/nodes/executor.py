"""执行节点 - 执行工具调用"""

from typing import Any

from goaldriveclaude.core.state import AgentState
from goaldriveclaude.tools import get_tool_by_name
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def executor(state: AgentState) -> dict[str, Any]:
    """执行工具调用

    Args:
        state: 当前状态

    Returns:
        更新后的状态字段
    """
    # 获取最近的计划
    if not state["tool_results"]:
        return {
            "consecutive_failures": state["consecutive_failures"] + 1,
            "messages": [("ai", "没有可执行的计划")],
        }

    last_result = state["tool_results"][-1]
    if last_result.get("tool") != "planner":
        return {
            "consecutive_failures": state["consecutive_failures"] + 1,
            "messages": [("ai", "上一个结果不是计划")],
        }

    plan = last_result.get("plan", {})
    tool_name = plan.get("tool_name")
    tool_input = plan.get("tool_input", {})

    if not tool_name:
        return {
            "consecutive_failures": state["consecutive_failures"] + 1,
            "messages": [("ai", "计划中没有工具名称")],
        }

    logger.info(f"执行工具: {tool_name}")

    try:
        # 获取工具
        tool = get_tool_by_name(tool_name)
        if tool is None:
            return {
                "consecutive_failures": state["consecutive_failures"] + 1,
                "messages": [("ai", f"未知工具: {tool_name}")],
                "tool_results": state["tool_results"] + [{
                    "tool": tool_name,
                    "success": False,
                    "error": f"未知工具: {tool_name}",
                }],
            }

        # 执行工具
        result = tool.invoke(tool_input)

        # 更新结果
        return {
            "iteration": state["iteration"] + 1,
            "phase": "evaluating",
            "tool_results": state["tool_results"] + [{
                "tool": tool_name,
                "input": tool_input,
                "result": result,
                "success": result.get("success", False) if isinstance(result, dict) else True,
            }],
            "messages": [("ai", f"执行工具: {tool_name}")],
        }

    except Exception as e:
        logger.error(f"工具执行失败: {e}")
        return {
            "consecutive_failures": state["consecutive_failures"] + 1,
            "messages": [("ai", f"工具执行失败: {str(e)}")],
            "tool_results": state["tool_results"] + [{
                "tool": tool_name,
                "success": False,
                "error": str(e),
            }],
        }
