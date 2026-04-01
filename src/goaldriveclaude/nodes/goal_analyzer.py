"""目标分析节点 - 将用户目标分解为子目标"""

import json
from typing import Any

from langchain_anthropic import ChatAnthropic

from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import AgentState
from goaldriveclaude.prompts.execution import GOAL_ANALYSIS_SYSTEM, GOAL_ANALYSIS_USER
from goaldriveclaude.utils.json_utils import clean_bom, parse_json_from_llm
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """验证错误"""

    pass


def _validate_and_build_subgoals(analysis: dict) -> list[dict]:
    """验证并构建子目标列表

    Args:
        analysis: LLM 返回的分析结果

    Returns:
        验证通过的子目标列表

    Raises:
        ValidationError: 验证失败
    """
    subgoals = []
    raw_subgoals = analysis.get("subgoals", [])

    if not raw_subgoals:
        raise ValidationError("未返回任何子目标")

    for i, sg in enumerate(raw_subgoals):
        # 验证必要字段
        if "description" not in sg:
            raise ValidationError(f"子目标 {i+1} 缺少 description")

        criteria = sg.get("verification_criteria", [])
        if not criteria or len(criteria) == 0:
            raise ValidationError(f"子目标 {i+1} ({sg.get('description', '')}) 缺少 verification_criteria")

        subgoals.append({
            "id": sg.get("id", f"sg_{i+1:03d}"),
            "description": sg["description"],
            "verification_criteria": criteria,
            "depends_on": sg.get("depends_on", []),
            "status": "pending",
        })

    return subgoals


def goal_analyzer(state: AgentState) -> dict[str, Any]:
    """分析目标并分解为子目标

    最多重试 2 次，确保 JSON 解析成功且格式正确。

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

    # 最多重试 2 次
    last_error = None
    for attempt in range(2):
        try:
            response = llm.invoke(messages)
            content = clean_bom(response.content)

            # 使用 json_utils 解析
            analysis = parse_json_from_llm(content)

            # 验证并构建子目标
            subgoals = _validate_and_build_subgoals(analysis)

            logger.info(f"目标分解完成，共 {len(subgoals)} 个子目标")

            return {
                "subgoals": subgoals,
                "current_subgoal_index": 0,
                "phase": "planning",
                "messages": [("ai", f"目标理解: {analysis.get('goal_understanding', '')}")],
            }

        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            logger.warning(f"第 {attempt + 1} 次尝试失败: {e}")
            if attempt == 0:
                # 第一次失败，添加提示重试
                messages.append(
                    ("ai", f"解析失败: {str(e)}。请严格输出 JSON 格式，包含 subgoals 数组，每个子目标必须有 description 和 verification_criteria。")
                )

    # 两次都失败，返回友好错误
    error_msg = f"无法解析目标分析结果。请检查提示词是否清晰，或手动分解目标。\n错误: {last_error}"
    logger.error(error_msg)

    return {
        "should_abort": True,
        "abort_reason": error_msg,
        "phase": "aborted",
        "messages": [("ai", error_msg)],
    }
