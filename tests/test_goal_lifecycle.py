"""测试目标生命周期"""

import pytest

from goaldriveclaude.core.state import create_initial_state


class TestGoalLifecycle:
    """测试目标生命周期"""

    def test_goal_initial_state(self):
        state = create_initial_state("创建一个 Flask 应用")
        assert state["goal_verified"] is False
        assert state["phase"] == "analyzing"

    def test_subgoal_progression(self):
        state = create_initial_state("测试目标")

        # 模拟添加子目标
        state["subgoals"] = [
            {"id": "sg_001", "description": "初始化项目", "status": "done"},
            {"id": "sg_002", "description": "实现功能", "status": "in_progress"},
        ]
        state["current_subgoal_index"] = 1

        assert len(state["subgoals"]) == 2
        assert state["subgoals"][0]["status"] == "done"
