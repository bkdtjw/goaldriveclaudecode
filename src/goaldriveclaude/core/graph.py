"""LangGraph 图定义 - 目标驱动状态图

架构:
    START -> goal_analyzer
         -> planner -> executor -> evaluator (循环直到子目标完成)
         -> verifier (所有子目标完成后)
         -> END

状态路由:
    - phase 字段控制流程: analyzing -> planning -> executing -> evaluating -> verifying -> done
    - route_after_evaluation 是核心路由函数
"""

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
    """评估后的路由决策

    这是核心的路由函数，决定执行流程走向。
    """
    # abort 条件 - 最高优先级
    if state.get("should_abort"):
        logger.warning(f"任务中止: {state.get('abort_reason', '未知原因')}")
        return "end"

    # 安全阀：超过最大迭代次数
    if state["iteration"] >= state["max_iterations"]:
        logger.warning("超过最大迭代次数")
        return "end"

    # 错误恢复
    if state["consecutive_failures"] >= 3:
        logger.warning(f"连续失败 {state['consecutive_failures']} 次，进入错误恢复")
        return "error_recovery"

    # 人工介入
    if state.get("needs_human_input"):
        return "human_input"

    # 根据 phase 路由（evaluator 已设置 phase）
    phase = state.get("phase", "planning")

    if phase == "verifying":
        # 所有子目标完成，进入验证
        return "verifier"

    if phase == "done":
        # 任务完成
        return "end"

    if phase == "aborted":
        # 任务中止
        return "end"

    if phase == "waiting_for_user":
        # 等待用户输入，退出 graph
        return "end"

    # 默认回到 planner 继续执行
    return "planner"


def route_after_verifier(state: AgentState) -> str:
    """验证后的路由"""
    if state.get("should_abort"):
        return "end"

    if state.get("needs_human_input"):
        return "human_input"

    # 验证通过
    if state.get("goal_verified"):
        return "end"

    # 验证失败，回到 planner 重新规划
    return "planner"


def route_after_error_recovery(state: AgentState) -> str:
    """错误恢复后的路由"""
    if state.get("should_abort"):
        return "end"

    if state.get("needs_human_input"):
        return "human_input"

    # 回到 planner 继续
    return "planner"


def route_after_human_input(state: AgentState) -> str:
    """人工介入后的路由"""
    if state.get("should_abort"):
        return "end"

    # 回到 planner
    return "planner"


def build_graph():
    """构建目标驱动的状态图

    Returns:
        编译后的状态图 (CompiledStateGraph)
    """
    workflow = StateGraph(AgentState)

    # 添加所有节点
    workflow.add_node("goal_analyzer", goal_analyzer)
    workflow.add_node("planner", planner)
    workflow.add_node("executor", executor)
    workflow.add_node("evaluator", evaluator)
    workflow.add_node("verifier", verifier)
    workflow.add_node("error_recovery", error_recovery)
    workflow.add_node("human_input", human_input)

    # 入口点
    workflow.set_entry_point("goal_analyzer")

    # 添加边
    workflow.add_edge("goal_analyzer", "planner")

    # planner -> executor -> evaluator 形成执行循环
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "evaluator")

    # evaluator 后的条件路由 - 核心路由
    workflow.add_conditional_edges(
        "evaluator",
        route_after_evaluation,
        {
            "planner": "planner",
            "verifier": "verifier",
            "error_recovery": "error_recovery",
            "human_input": "human_input",
            "end": END,
        },
    )

    # verifier 后的条件路由
    workflow.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {
            "planner": "planner",
            "human_input": "human_input",
            "end": END,
        },
    )

    # error_recovery 后的路由
    workflow.add_conditional_edges(
        "error_recovery",
        route_after_error_recovery,
        {
            "planner": "planner",
            "human_input": "human_input",
            "end": END,
        },
    )

    # human_input 后的路由
    workflow.add_conditional_edges(
        "human_input",
        route_after_human_input,
        {
            "planner": "planner",
            "end": END,
        },
    )

    # 编译并返回编译后的图
    compiled = workflow.compile()
    return compiled
