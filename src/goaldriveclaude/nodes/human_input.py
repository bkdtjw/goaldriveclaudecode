"""人机交互节点 - 请求用户输入"""

from typing import Any

from goaldriveclaude.core.state import AgentState
from goaldriveclaude.utils.display import Display
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def human_input(state: AgentState) -> dict[str, Any]:
    """请求用户输入

    Args:
        state: 当前状态

    Returns:
        更新后的状态字段
    """
    display = Display()

    # 显示当前状态
    display.show_error("需要人工介入")

    if state["abort_reason"]:
        display.show_error(f"原因: {state['abort_reason']}")

    # 询问用户
    question = "请提供指导或输入命令（输入 'continue' 继续，'abort' 中止）："
    user_input = display.prompt_user(question)

    logger.info(f"用户输入: {user_input}")

    if user_input.lower() in ["abort", "quit", "exit", "停止", "中止"]:
        return {
            "should_abort": True,
            "abort_reason": "用户中止",
            "phase": "aborted",
            "messages": [("human", user_input)],
        }

    # 重置状态
    return {
        "needs_human_input": False,
        "consecutive_failures": 0,
        "phase": "planning",
        "messages": [("human", user_input)],
    }
