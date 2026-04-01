"""Execution node: run pending actions and store tool results."""

from typing import Any

from goaldriveclaude.core.state import AgentState
from goaldriveclaude.tools import get_tool_by_name
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def executor(state: AgentState) -> dict[str, Any]:
    """Execute the action from planner and update state.

    Args:
        state: Current agent state.

    Returns:
        State updates after execution.
    """
    action = state.get("pending_action")
    if not action or not action.get("tool_name"):
        logger.info("No pending_action, skipping execution")
        # 如果当前已在 waiting_for_user，不要覆盖 phase
        phase = state.get("phase", "evaluating")
        if phase == "waiting_for_user":
            return {
                "iteration": state["iteration"] + 1,
                "consecutive_failures": 0,
                "phase": "waiting_for_user",
            }
        return {
            "iteration": state["iteration"] + 1,
            "consecutive_failures": 0,
            "phase": "evaluating",
        }

    tool_name = action["tool_name"]
    tool_input = action.get("tool_input", {})

    # Virtual action: planner produced a direct textual response (no tool needed).
    if tool_name == "_direct_response":
        content = str(tool_input.get("content", "")).strip()
        logger.info("Executing direct response action (no tool call)")
        return {
            "tool_results": [
                {
                    "tool": tool_name,
                    "input": tool_input,
                    "success": True,
                    "output": content[:3000],
                    "error": "",
                }
            ],
            "messages": [("ai", content)],
            "pending_action": None,
            "iteration": state["iteration"] + 1,
            "consecutive_failures": 0,
            "phase": "evaluating",
        }

    logger.info(f"Executing tool: {tool_name}")

    tool = get_tool_by_name(tool_name)
    if tool is None:
        error_msg = f"Unknown tool: {tool_name}"
        logger.error(error_msg)
        return {
            "tool_results": [{"tool": tool_name, "success": False, "error": error_msg}],
            "pending_action": None,
            "iteration": state["iteration"] + 1,
            "consecutive_failures": state["consecutive_failures"] + 1,
            "phase": "evaluating",
        }

    try:
        result = tool.invoke(tool_input)

        file_context = dict(state["file_context"])
        if tool_name == "read_file" and isinstance(result, dict) and result.get("success"):
            path = tool_input.get("path", "")
            file_context[path] = str(result.get("output", ""))[:5000]

        success = result.get("success", False) if isinstance(result, dict) else True
        output = result.get("output", str(result)) if isinstance(result, dict) else str(result)
        error = result.get("error", "") if isinstance(result, dict) else ""

        logger.info(f"Tool result: {'success' if success else 'failed'}")

        return {
            "tool_results": [
                {
                    "tool": tool_name,
                    "input": tool_input,
                    "success": success,
                    "output": str(output)[:3000],
                    "error": str(error)[:1000],
                }
            ],
            "file_context": file_context,
            "pending_action": None,
            "iteration": state["iteration"] + 1,
            "consecutive_failures": 0 if success else state["consecutive_failures"] + 1,
            "phase": "evaluating",
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Tool execution exception: {error_msg}")
        return {
            "tool_results": [{"tool": tool_name, "success": False, "error": error_msg[:1000]}],
            "pending_action": None,
            "iteration": state["iteration"] + 1,
            "consecutive_failures": state["consecutive_failures"] + 1,
            "phase": "evaluating",
        }
