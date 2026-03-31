"""Prompt 模板模块"""

from goaldriveclaude.prompts.evaluation import EVALUATION_SYSTEM, EVALUATION_USER
from goaldriveclaude.prompts.goal_analysis import GOAL_ANALYSIS_SYSTEM, GOAL_ANALYSIS_USER
from goaldriveclaude.prompts.planning import PLANNING_SYSTEM, PLANNING_USER
from goaldriveclaude.prompts.verification import VERIFICATION_SYSTEM, VERIFICATION_USER

__all__ = [
    "GOAL_ANALYSIS_SYSTEM",
    "GOAL_ANALYSIS_USER",
    "PLANNING_SYSTEM",
    "PLANNING_USER",
    "EVALUATION_SYSTEM",
    "EVALUATION_USER",
    "VERIFICATION_SYSTEM",
    "VERIFICATION_USER",
]
