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
        required_fields = [
            "original_goal",
            "messages",
            "goal_understanding",
            "task_cards",
            "current_task_index",
            "phase",
            "iteration",
            "max_iterations",
            "working_directory",
            "tool_results",
            "file_context",
            "should_abort",
            "abort_reason",
            "session_id",
        ]
        for field in required_fields:
            assert field in state, f"缺少字段: {field}"
