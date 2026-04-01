"""测试图定义"""

import pytest
from goaldriveclaude.core.graph import build_graph
from goaldriveclaude.core.state import create_initial_state


class TestGraph:
    def test_build_graph(self):
        graph = build_graph()
        assert graph is not None

    def test_initial_state_valid(self):
        state = create_initial_state("test goal")
        # 确认所有必需字段都在
        required_fields = [
            "original_goal",
            "messages",
            "subgoals",
            "current_subgoal_index",
            "goal_verified",
            "verification_report",
            "verification_attempts",
            "verification_gaps",
            "working_directory",
            "pending_action",
            "tool_results",
            "file_context",
            "iteration",
            "max_iterations",
            "consecutive_failures",
            "needs_human_input",
            "should_abort",
            "abort_reason",
            "phase",
            "session_id",
        ]
        for field in required_fields:
            assert field in state, f"缺少字段: {field}"
