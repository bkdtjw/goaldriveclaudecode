"""目标分析节点 - 将用户目标分解为子目标"""

import json
from typing import Any

from langchain_anthropic import ChatAnthropic

from goaldriveclaude.config import get_config
from goaldriveclaude.core.models import GoalAnalysisResult, SubGoalModel
from goaldriveclaude.core.state import AgentState
from goaldriveclaude.prompts.goal_analysis import GOAL_ANALYSIS_SYSTEM, GOAL_ANALYSIS_USER
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def goal_analyzer(state: AgentState) -> dict[str, Any]:
    """分析目标并分解为子目标

    Args:
        state: 当前状态

    Returns:
        更新后的状态字段
    """
    config = get_config()

    # 初始化 LLM
    llm = ChatAnthropic(
        model=config.default_model,
        api_key=config.anthropic_api_key,
        temperature=0.2,
    )

    # 构建消息
    system_msg = GOAL_ANALYSIS_SYSTEM
    user_msg = GOAL_ANALYSIS_USER.format(
        goal=state["original_goal"],
        working_directory=state["working_directory"],
    )

    messages = [
        ("system", system_msg),
        ("human", user_msg),
    ]

    logger.info(f"分析目标: {state['original_goal'][:50]}...")

    try:
        # 调用 LLM
        response = llm.invoke(messages)
        content = response.content

        # 解析 JSON
        # 处理可能的 markdown 代码块
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        analysis = json.loads(content)

        # 验证结果格式
        subgoals = []
        for sg in analysis.get("subgoals", []):
            subgoal = SubGoalModel(**sg)
            subgoals.append({
                "id": subgoal.id,
                "description": subgoal.description,
                "verification_criteria": subgoal.verification_criteria,
                "depends_on": subgoal.depends_on,
                "status": "pending",
            })

        logger.info(f"目标分解完成，共 {len(subgoals)} 个子目标")

        return {
            "subgoals": subgoals,
            "current_subgoal_index": 0,
            "phase": "planning",
            "messages": [("ai", f"目标理解: {analysis.get('goal_understanding', '')}")],
        }

    except Exception as e:
        logger.error(f"目标分析失败: {e}")
        return {
            "should_abort": True,
            "abort_reason": f"目标分析失败: {str(e)}",
            "phase": "aborted",
        }
