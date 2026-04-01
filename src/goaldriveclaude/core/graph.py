"""LangGraph 图定义 - GoalDriveClaude 多 Agent 投票架构

架构:
    START -> coordinator
         -> worker -> supervisor -> (通过/打回/全局验证/结束)
"""

from langgraph.graph import END, START, StateGraph

from goaldriveclaude.agents.worker import invoke_worker
from goaldriveclaude.core.state import GoalState
from goaldriveclaude.nodes.coordinator import coordinator
from goaldriveclaude.nodes.global_verifier import global_verifier
from goaldriveclaude.nodes.supervisor import supervisor
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def _set_task_in_progress(state: GoalState) -> dict:
    """在 Worker 执行前，把当前任务标记为 in_progress。"""
    idx = state["current_task_index"]
    task_cards = list(state["task_cards"])
    if idx < len(task_cards):
        task_cards[idx] = {**task_cards[idx], "status": "in_progress"}
    return {"task_cards": task_cards}


def next_task(state: GoalState) -> dict:
    """推进到下一个待执行的任务。"""
    current_idx = state["current_task_index"]
    task_cards = state["task_cards"]

    for i in range(current_idx + 1, len(task_cards)):
        if task_cards[i]["status"] in ("pending", "in_progress"):
            logger.info(f"推进到下一个任务: {task_cards[i]['id']}")
            return {"current_task_index": i, "phase": "working"}

    # 如果没有下一个，但可能全部通过了（理论上 supervisor 会直接送全局验证）
    if all(t["status"] == "passed" for t in task_cards):
        return {"phase": "global_reviewing"}

    logger.warning("没有找到下一个任务，但也不是全部通过")
    return {"phase": "working"}


def route_after_coordinator(state: GoalState) -> str:
    if state.get("should_abort"):
        logger.warning(f"任务中止: {state.get('abort_reason', '未知原因')}")
        return "end"
    return "worker"


def route_after_worker(state: GoalState) -> str:
    return "supervisor"


def route_after_supervisor(state: GoalState) -> str:
    if state.get("should_abort"):
        logger.warning(f"任务中止: {state.get('abort_reason', '未知原因')}")
        return "end"

    current_idx = state["current_task_index"]
    if current_idx >= len(state["task_cards"]):
        return "global_verifier"

    current = state["task_cards"][current_idx]

    if current["status"] == "rejected":
        if current.get("retry_count", 0) >= 3:
            return "end"
        logger.info(f"任务 {current['id']} 被打回，返回 Worker 重做")
        return "worker"

    if current["status"] == "passed":
        if all(t["status"] == "passed" for t in state["task_cards"]):
            return "global_verifier"
        return "next_task"

    return "end"


def route_after_next_task(state: GoalState) -> str:
    if state.get("should_abort"):
        return "end"
    return "worker"


def route_after_global_verifier(state: GoalState) -> str:
    if state.get("should_abort"):
        return "end"
    if state.get("phase") == "done":
        return "end"
    return "worker"


def build_graph():
    """构建多 Agent 投票驱动的状态图。"""
    workflow = StateGraph(GoalState)

    # 添加节点
    workflow.add_node("coordinator", coordinator)
    workflow.add_node("prepare_worker", _set_task_in_progress)
    workflow.add_node("worker", invoke_worker)
    workflow.add_node("supervisor", supervisor)
    workflow.add_node("next_task", next_task)
    workflow.add_node("global_verifier", global_verifier)

    # 入口
    workflow.set_entry_point("coordinator")

    # coordinator -> conditional -> worker / end
    workflow.add_conditional_edges(
        "coordinator",
        route_after_coordinator,
        {"worker": "prepare_worker", "end": END},
    )

    # prepare_worker -> worker -> supervisor
    workflow.add_edge("prepare_worker", "worker")
    workflow.add_edge("worker", "supervisor")

    # supervisor -> conditional
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "worker": "prepare_worker",
            "next_task": "next_task",
            "global_verifier": "global_verifier",
            "end": END,
        },
    )

    # next_task -> conditional -> worker / end
    workflow.add_conditional_edges(
        "next_task",
        route_after_next_task,
        {"worker": "prepare_worker", "end": END},
    )

    # global_verifier -> conditional -> worker / end
    workflow.add_conditional_edges(
        "global_verifier",
        route_after_global_verifier,
        {"worker": "prepare_worker", "end": END},
    )

    compiled = workflow.compile()
    return compiled
