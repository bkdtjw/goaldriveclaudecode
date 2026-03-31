"""核心状态定义 - AgentState TypedDict"""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class SubGoal(TypedDict):
    """子目标定义"""

    id: str  # 如 "sg_001"
    description: str  # 子目标描述
    verification_criteria: list[str]  # 可执行的验证条件列表
    depends_on: list[str]  # 依赖的其他子目标 ID
    status: str  # "pending" | "in_progress" | "done" | "failed" | "verifying"


class ToolResult(TypedDict):
    """工具执行结果"""

    success: bool
    output: str  # 正常输出
    error: str  # 错误信息（如有）
    duration_ms: int  # 执行耗时


class VerificationGap(TypedDict):
    """验证差距分析"""

    subgoal_id: str
    criteria: str
    actual_result: str
    suggested_fix: str


class AgentState(TypedDict):
    """Agent 状态定义 - LangGraph 使用"""

    # ── 用户输入 ──
    original_goal: str
    messages: Annotated[list, add_messages]

    # ── 目标驱动核心 ⭐ ──
    subgoals: list[SubGoal]
    current_subgoal_index: int
    goal_verified: bool
    verification_report: str
    verification_attempts: int  # 验证尝试次数
    verification_gaps: list[VerificationGap]  # 验证差距

    # ── 执行上下文 ──
    working_directory: str
    tool_results: list[dict]  # 最近的工具执行结果
    file_context: dict[str, str]  # 缓存的文件内容

    # ── 控制流 ──
    iteration: int
    max_iterations: int  # 默认 50
    consecutive_failures: int  # 连续失败次数
    needs_human_input: bool
    should_abort: bool
    abort_reason: str
    phase: str  # "analyzing" | "planning" | "executing" | "evaluating" | "verifying" | "done" | "aborted"

    # ── 恢复上下文 ──
    session_id: str


def create_initial_state(goal: str, max_iterations: int = 50) -> AgentState:
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
        "working_directory": ".",
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
