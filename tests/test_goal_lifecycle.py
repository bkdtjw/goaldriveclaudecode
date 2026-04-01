"""测试目标生命周期"""

import pytest

from goaldriveclaude.core.state import create_initial_state


class TestGoalLifecycle:
    """测试目标生命周期"""

    def test_goal_initial_state(self):
        state = create_initial_state("创建一个 Flask 应用")
        assert state["phase"] == "coordinating"

    def test_task_progression(self):
        state = create_initial_state("测试目标")

        state["task_cards"] = [
            {
                "id": "tc_001",
                "description": "初始化项目",
                "expected_outputs": ["目录结构"],
                "verification_criteria": ["存在 src 目录"],
                "priority": 1,
                "status": "passed",
            },
            {
                "id": "tc_002",
                "description": "实现功能",
                "expected_outputs": ["代码文件"],
                "verification_criteria": ["测试通过"],
                "priority": 2,
                "status": "in_progress",
            },
        ]
        state["current_task_index"] = 1

        assert len(state["task_cards"]) == 2
        assert state["task_cards"][0]["status"] == "passed"
