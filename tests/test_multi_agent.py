"""测试多 Agent 架构核心逻辑"""

import pytest

from goaldriveclaude.core.state import create_initial_state
from goaldriveclaude.nodes.supervisor import _apply_voting_result
from goaldriveclaude.nodes.global_verifier import _identify_faulty_tasks


class TestSupervisorVoting:
    """测试 Supervisor 投票逻辑"""

    def _build_state_with_votes(self, votes: dict[str, str], retry: int = 0) -> dict:
        """辅助函数：构建一个带投票结果的任务状态"""
        state = create_initial_state("测试目标")
        state["task_cards"] = [
            {
                "id": "tc_001",
                "description": "测试任务",
                "expected_outputs": [],
                "verification_criteria": [],
                "priority": 1,
                "worker_report": "done",
                "review_feedback": [],
                "review_votes": votes,
                "retry_count": retry,
                "status": "reviewing",
            }
        ]
        state["current_task_index"] = 0
        return state

    def test_voting_3_pass(self):
        """3 票全过"""
        state = self._build_state_with_votes(
            {"code_quality": "pass", "functional": "pass", "verification": "pass"}
        )
        result = _apply_voting_result(state, state["task_cards"][0]["review_votes"], [])
        assert result["task_cards"][0]["status"] == "passed"
        assert result["phase"] == "working"

    def test_voting_2_pass_1_reject(self):
        """2 票过，1 票拒绝 - 应该通过"""
        state = self._build_state_with_votes(
            {"code_quality": "pass", "functional": "pass", "verification": "reject"}
        )
        result = _apply_voting_result(state, state["task_cards"][0]["review_votes"], [])
        assert result["task_cards"][0]["status"] == "passed"

    def test_voting_1_pass_2_reject(self):
        """1 票过，2 票拒绝 - 应该打回"""
        state = self._build_state_with_votes(
            {"code_quality": "pass", "functional": "reject", "verification": "reject"}
        )
        result = _apply_voting_result(
            state, state["task_cards"][0]["review_votes"], ["fb1", "fb2"]
        )
        tc = result["task_cards"][0]
        assert tc["status"] == "rejected"
        assert tc["retry_count"] == 1
        assert len(tc["review_feedback"]) == 2
        assert result["phase"] == "working"

    def test_voting_0_pass_3_reject(self):
        """0 票过，3 票拒绝 - 应该打回"""
        state = self._build_state_with_votes(
            {"code_quality": "reject", "functional": "reject", "verification": "reject"}
        )
        result = _apply_voting_result(
            state, state["task_cards"][0]["review_votes"], ["fb1", "fb2", "fb3"]
        )
        assert result["task_cards"][0]["status"] == "rejected"

    def test_retry_exceed_limit_aborts(self):
        """连续 3 次拒绝后应该中止"""
        state = self._build_state_with_votes(
            {"code_quality": "reject", "functional": "reject", "verification": "pass"},
            retry=2,
        )
        result = _apply_voting_result(state, state["task_cards"][0]["review_votes"], ["fb"])
        assert result["should_abort"] is True
        assert result["phase"] == "aborted"
        assert result["task_cards"][0]["retry_count"] == 3


class TestGlobalVerifier:
    """测试全局验证器逻辑"""

    def test_identify_faulty_tasks_by_id(self):
        task_cards = [
            {"id": "tc_001", "description": "任务1"},
            {"id": "tc_002", "description": "任务2"},
        ]
        feedback = ["tc_002 has integration issue"]
        indices = _identify_faulty_tasks(feedback, task_cards)
        assert indices == [1]

    def test_identify_faulty_tasks_fallback(self):
        task_cards = [
            {"id": "tc_001", "description": "任务1"},
            {"id": "tc_002", "description": "任务2"},
        ]
        feedback = ["some vague error"]
        indices = _identify_faulty_tasks(feedback, task_cards)
        # fallback 到最后一项
        assert indices == [1]


class TestCoordinatorTaskCard:
    """测试 Coordinator 生成的任务卡结构"""

    def test_coordinator_validate_task_cards(self):
        from goaldriveclaude.nodes.coordinator import _validate_task_cards

        data = {
            "task_cards": [
                {
                    "id": "tc_001",
                    "description": "创建文件",
                    "expected_outputs": ["main.py"],
                    "verification_criteria": ["文件存在"],
                    "priority": 1,
                    "depends_on": [],
                }
            ]
        }
        cards = _validate_task_cards(data)
        assert len(cards) == 1
        assert cards[0]["id"] == "tc_001"
        assert cards[0]["expected_outputs"] == ["main.py"]
        assert cards[0]["retry_count"] == 0
        assert cards[0]["status"] == "pending"
