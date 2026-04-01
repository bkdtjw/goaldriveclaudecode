"""核心状态定义 - 引入 pending_action 和 reducer"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


def _append_results(existing: list[dict], new: list[dict]) -> list[dict]:
    """tool_results 的 reducer：追加新结果，保留最近 30 条"""
    combined = existing + new
    return combined[-30:]  # 滑动窗口，防止无限增长


class SubGoal(TypedDict):
    """子目标定义"""

    id: str
    description: str
    verification_criteria: list[str]
    depends_on: list[str]
    status: str  # "pending" | "in_progress" | "done" | "failed"


class PendingAction(TypedDict, total=False):
    """Planner 输出的待执行动作"""

    tool_name: str
    tool_input: dict[str, Any]
    reasoning: str


class AgentState(TypedDict):
    """Agent 状态定义 - 带 reducer 的版本"""

    # ── 用户输入 ──
    original_goal: str
    messages: Annotated[list[AnyMessage], add_messages]

    # ── 目标驱动核心 ⭐ ──
    subgoals: list[SubGoal]
    current_subgoal_index: int
    goal_verified: bool
    verification_report: str
    verification_attempts: int
    verification_gaps: list[dict]

    # ── 执行上下文 ──
    working_directory: str
    pending_action: PendingAction | None  # ⭐ 新增：planner 的计划
    tool_results: Annotated[list[dict], _append_results]  # ⭐ 带 reducer
    file_context: dict[str, str]

    # ── 控制流 ──
    iteration: int
    max_iterations: int
    consecutive_failures: int
    needs_human_input: bool
    should_abort: bool
    abort_reason: str
    phase: str

    session_id: str


def create_initial_state(
    goal: str, working_dir: str = ".", max_iterations: int = 50
) -> AgentState:
    """创建初始状态"""
    return {
        "original_goal": goal,
        "messages": [],
        "subgoals": [],
        "current_subgoal_index": 0,
        "goal_verified": False,
        "verification_report": "",
        "verification_attempts": 0,
        "verification_gaps": [],
        "working_directory": working_dir,
        "pending_action": None,
        "tool_results": [],
        "file_context": {},
        "iteration": 0,
        "max_iterations": max_iterations,
        "consecutive_failures": 0,
        "needs_human_input": False,
        "should_abort": False,
        "abort_reason": "",
        "phase": "analyzing",
        "session_id": "",
    }
