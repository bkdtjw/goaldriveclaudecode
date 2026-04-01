"""核心状态定义 - GoalDriveClaude 多 Agent 投票架构"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


def _append_results(existing: list[dict], new: list[dict]) -> list[dict]:
    """工具结果的 reducer：追加新结果，保留最近 30 条"""
    combined = existing + new
    return combined[-30:]


class TaskCard(TypedDict):
    """Coordinator 生成的任务卡"""

    id: str
    description: str
    expected_outputs: list[str]
    verification_criteria: list[str]
    priority: int
    worker_report: str
    review_feedback: list[str]
    review_votes: dict[str, str]
    retry_count: int
    status: str  # pending | in_progress | reviewing | rejected | passed | failed


class GoalState(TypedDict):
    """外层 Goal Loop 的状态"""

    # ── 用户输入 ──
    original_goal: str
    messages: Annotated[list[AnyMessage], add_messages]

    # ── Coordinator 输出 ──
    goal_understanding: str
    task_cards: list[TaskCard]
    current_task_index: int

    # ── 全局控制 ──
    phase: str  # coordinating | working | reviewing | global_reviewing | done | aborted
    iteration: int
    max_iterations: int

    # ── 执行上下文 ──
    working_directory: str
    tool_results: Annotated[list[dict], _append_results]
    file_context: dict[str, str]

    # ── 终止控制 ──
    should_abort: bool
    abort_reason: str

    session_id: str


def create_initial_state(
    goal: str, working_dir: str = ".", max_iterations: int = 50
) -> GoalState:
    """创建初始状态"""
    return {
        "original_goal": goal,
        "messages": [],
        "goal_understanding": "",
        "task_cards": [],
        "current_task_index": 0,
        "phase": "coordinating",
        "iteration": 0,
        "max_iterations": max_iterations,
        "working_directory": working_dir,
        "tool_results": [],
        "file_context": {},
        "should_abort": False,
        "abort_reason": "",
        "session_id": "",
    }
