"""LangGraph 图定义 - 状态图和路由"""

from typing import Literal

from langgraph.graph import END, START, StateGraph

from goaldriveclaude.core.state import AgentState
from goaldriveclaude.nodes import (
    error_recovery,
    evaluator,
    executor,
    goal_analyzer,
    human_input,
    planner,
    verifier,
)
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def route_after_evaluation(state: AgentState) -> str:
    """评估后的路由决策"""
    # 1. 安全阀：超过最大迭代次数 → 中止
    if state["iteration"] >= state["max_iterations"]:
        logger.warning(f"超过最大迭代次数 {state['max_iterations']}")
        return "abort"

    # 2. 连续失败过多 → 错误恢复
    if state["consecutive_failures"] >= 3:
        logger.warning(f"连续失败 {state['consecutive_failures']} 次，进入错误恢复")
        return "error_recovery"

    # 3. 需要人工介入
    if state["needs_human_input"]:
        return "human_input"

    # 4. 当前子目标完成，检查是否所有子目标都完成
    current_idx = state["current_subgoal_index"]
    if current_idx < len(state["subgoals"]):
        current = state["subgoals"][current_idx]
        if current["status"] == "done":
            # 检查是否所有子目标都完成
            all_done = all(sg["status"] == "done" for sg in state["subgoals"])
            if all_done:
                logger.info("所有子目标完成，进入验证阶段")
                return "verifier"
            else:
                return "planner"

    # 5. 默认：继续规划执行当前子目标
    return "planner"


def route_after_verification(state: AgentState) -> str:
    """验证后的路由 —— 目标驱动的核心"""
    if state["goal_verified"]:
        logger.info("验证通过，任务完成！")
        return "end"

    if state["verification_attempts"] >= 3:
        logger.warning("多次验证失败，需要人工介入")
        return "human_input"

    logger.info("验证失败，带着差距分析重新规划")
    return "planner"


def route_after_error_recovery(state: AgentState) -> str:
    """错误恢复后的路由"""
    if state["should_abort"]:
        return "abort"

    if state["needs_human_input"]:
        return "human_input"

    return "planner"


def build_graph() -> StateGraph:
    """构建 LangGraph 状态图

    Returns:
        编译后的状态图
    """
    # 创建状态图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("goal_analyzer", goal_analyzer)
    workflow.add_node("planner", planner)
    workflow.add_node("executor", executor)
    workflow.add_node("evaluator", evaluator)
    workflow.add_node("verifier", verifier)
    workflow.add_node("error_recovery", error_recovery)
    workflow.add_node("human_input", human_input)

    # 添加边
    workflow.add_edge(START, "goal_analyzer")
    workflow.add_edge("goal_analyzer", "planner")
    workflow.add_edge("executor", "evaluator")
    workflow.add_edge("human_input", "planner")

    # 评估后的条件边
    workflow.add_conditional_edges(
        "evaluator",
        route_after_evaluation,
        {
            "planner": "planner",
            "verifier": "verifier",
            "error_recovery": "error_recovery",
            "human_input": "human_input",
            "abort": END,
        },
    )

    # 验证后的条件边
    workflow.add_conditional_edges(
        "verifier",
        route_after_verification,
        {
            "planner": "planner",
            "human_input": "human_input",
            "end": END,
        },
    )

    # 错误恢复后的条件边
    workflow.add_conditional_edges(
        "error_recovery",
        route_after_error_recovery,
        {
            "planner": "planner",
            "human_input": "human_input",
            "abort": END,
        },
    )

    # 规划后的边
    workflow.add_edge("planner", "executor")

    # 编译图
    return workflow.compile()
