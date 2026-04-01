"""Tests for planner subgoal classification heuristics."""

from goaldriveclaude.nodes.planner import _is_explanation_subgoal


def test_explanation_subgoal_identity_question():
    subgoal = {
        "description": "Explain identity as an AI assistant created by Anthropic",
        "verification_criteria": ["mention AI", "mention Anthropic"],
    }

    assert _is_explanation_subgoal(subgoal) is True


def test_explanation_subgoal_working_directory_context():
    subgoal = {
        "description": "Respond about working directory context and confirm it is unrelated",
        "verification_criteria": ["context only", "no filesystem operation required"],
    }

    assert _is_explanation_subgoal(subgoal) is True


def test_actionable_subgoal_file_write_is_not_explanation():
    subgoal = {
        "description": "Create file identity.md and write identity summary",
        "verification_criteria": ["file exists", "content contains heading"],
    }

    assert _is_explanation_subgoal(subgoal) is False
