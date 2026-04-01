"""人工介入节点 - 处理需要人工决策的情况"""

from typing import Any

from goaldriveclaude.core.state import AgentState
from goaldriveclaude.utils.display import Display
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)

# 全局 Display 实例
display = Display()


def human_input(state: AgentState) -> dict[str, Any]:
    """处理人工介入

    当系统遇到无法自动恢复的情况时，暂停执行并请求用户输入。

    Args:
        state: 当前状态

    Returns:
        更新后的状态字段
    """
    # 显示当前状态
    display.console.print("\n[bold yellow]需要人工介入[/bold yellow]")

    # 显示上下文
    if state["abort_reason"]:
        display.show_error(state["abort_reason"])

    if state["verification_gaps"]:
        display.console.print("\n[bold]验证差距:[/bold]")
        for gap in state["verification_gaps"]:
            display.console.print(f"- {gap.get('criteria', '')}")
            if gap.get('suggested_fix'):
                display.console.print(f"  建议: {gap['suggested_fix']}")

    # 提示用户选项
    display.console.print("\n[bold]选项:[/bold]")
    display.console.print("1. 继续执行 (c/continue)")
    display.console.print("2. 修改目标 (g/goal)")
    display.console.print("3. 跳过当前子目标 (s/skip)")
    display.console.print("4. 中止任务 (q/quit)")

    # 获取用户输入
    user_input = display.console.input("\n[bold cyan]你的选择: [/bold cyan]").strip().lower()

    if user_input in ("q", "quit", "exit"):
        logger.info("用户选择中止任务")
        return {
            "should_abort": True,
            "abort_reason": "用户中止",
            "phase": "aborted",
            "needs_human_input": False,
        }

    if user_input in ("g", "goal"):
        new_goal = display.console.input("[bold]请输入新的目标: [/bold]").strip()
        logger.info(f"用户修改目标: {new_goal[:50]}...")
        return {
            "original_goal": new_goal,
            "subgoals": [],  # 清空子目标，重新分析
            "current_subgoal_index": 0,
            "verification_attempts": 0,
            "consecutive_failures": 0,
            "needs_human_input": False,
            "phase": "analyzing",
        }

    if user_input in ("s", "skip"):
        logger.info("用户选择跳过当前子目标")
        # 标记当前子目标为完成，继续下一个
        current_idx = state["current_subgoal_index"]
        subgoals = list(state["subgoals"])
        if current_idx < len(subgoals):
            subgoals[current_idx] = {**subgoals[current_idx], "status": "done"}

        return {
            "subgoals": subgoals,
            "consecutive_failures": 0,
            "needs_human_input": False,
            "phase": "planning",
        }

    # 默认继续
    logger.info("用户选择继续执行")
    return {
        "consecutive_failures": 0,
        "needs_human_input": False,
        "phase": "planning",
    }
