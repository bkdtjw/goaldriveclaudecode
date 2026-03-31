"""测试节点"""

import pytest

from goaldriveclaude.core.state import AgentState, create_initial_state


class TestState:
    """测试状态"""

    def test_create_initial_state(self):
        state = create_initial_state("测试目标")
        assert state["original_goal"] == "测试目标"
        assert state["phase"] == "analyzing"
        assert state["iteration"] == 0
        assert state["subgoals"] == []

    def test_state_structure(self):
        state = create_initial_state("测试目标", max_iterations=100)
        assert state["max_iterations"] == 100
        assert "messages" in state
        assert "goal_verified" in state
