"""评估节点 - 评估执行结果"""

import json
from typing import Any

from langchain_anthropic import ChatAnthropic

from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import AgentState
from goaldriveclaude.prompts.evaluation import EVALUATION_SYSTEM, EVALUATION_USER
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def evaluator(state: AgentState) -> dict[str, Any]:
    """评估执行结果

    Args:
        state: 当前状态

    Returns:
        更新后的状态字段
    """
    config = get_config()

    current_idx = state["current_subgoal_index"]
    if current_idx >= len(state["subgoals"]):
        return {"phase": "verifying"}

    current_subgoal = state["subgoals"][current_idx]

    # 初始化 LLM
    llm = ChatAnthropic(
        model=config.default_model,
        api_key=config.anthropic_api_key,
        temperature=0.2,
    )

    # 构建最近的执行结果
    tool_results = ""
    if state["tool_results"]:
        last_result = state["tool_results"][-1]
        if "result" in last_result:
            result = last_result["result"]
            if isinstance(result, dict):
                tool_results += f"成功: {result.get('success', False)}\n"
                tool_results += f"输出: {result.get('output', '')[:500]}\n"
                if result.get('error'):
                    tool_results += f"错误: {result.get('error', '')[:500]}\n"

    # 构建文件上下文
    file_context = ""
    for path, content in state["file_context"].items():
        file_context += f"\n{path}:\n{content[:200]}\n"

    # 构建消息
    system_msg = EVALUATION_SYSTEM.format(
        current_subgoal=current_subgoal["description"],
        verification_criteria=current_subgoal["verification_criteria"],
    )

    user_msg = EVALUATION_USER.format(
        tool_results=tool_results,
        file_context=file_context,
    )

    messages = [
        ("system", system_msg),
        ("human", user_msg),
    ]

    logger.info(f"评估子目标: {current_subgoal['description'][:50]}...")

    try:
        # 调用 LLM
        response = llm.invoke(messages)
        content = response.content

        # 解析 JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        evaluation = json.loads(content)

        # 更新子目标状态
        if evaluation.get("subgoal_completed", False):
            current_subgoal["status"] = "done"
            # 移动到下一个子目标
            next_idx = current_idx + 1
            if next_idx < len(state["subgoals"]):
                return {
                    "current_subgoal_index": next_idx,
                    "consecutive_failures": 0,
                    "phase": "planning",
                    "messages": [("ai", f"子目标完成: {current_subgoal['description']}")],
                }
            else:
                return {
                    "phase": "verifying",
                    "messages": [("ai", "所有子目标完成，进入验证阶段")],
                }
        else:
            # 未完成，继续规划
            return {
                "phase": "planning",
                "messages": [("ai", f"继续执行: {evaluation.get('next_action', '')}")],
            }

    except Exception as e:
        logger.error(f"评估失败: {e}")
        return {
            "consecutive_failures": state["consecutive_failures"] + 1,
            "messages": [("ai", f"评估失败: {str(e)}")],
        }
