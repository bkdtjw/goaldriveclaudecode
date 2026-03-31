"""规划节点 - 动态规划下一步操作"""

import json
from typing import Any

from langchain_anthropic import ChatAnthropic

from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import AgentState
from goaldriveclaude.prompts.planning import PLANNING_SYSTEM, PLANNING_USER
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def planner(state: AgentState) -> dict[str, Any]:
    """规划下一步操作

    Args:
        state: 当前状态

    Returns:
        更新后的状态字段
    """
    config = get_config()

    # 安全检查
    if state["iteration"] >= state["max_iterations"]:
        return {
            "should_abort": True,
            "abort_reason": "超过最大迭代次数",
            "phase": "aborted",
        }

    # 获取当前子目标
    if not state["subgoals"]:
        return {"should_abort": True, "abort_reason": "没有子目标", "phase": "aborted"}

    current_idx = state["current_subgoal_index"]
    if current_idx >= len(state["subgoals"]):
        return {"phase": "verifying"}

    current_subgoal = state["subgoals"][current_idx]

    # 更新子目标状态
    if current_subgoal["status"] == "pending":
        current_subgoal["status"] = "in_progress"

    # 初始化 LLM
    llm = ChatAnthropic(
        model=config.default_model,
        api_key=config.anthropic_api_key,
        temperature=0.2,
    )

    # 构建已完成的子目标列表
    completed_subgoals = [
        sg["description"]
        for sg in state["subgoals"][:current_idx]
        if sg["status"] == "done"
    ]

    # 构建最近的执行结果
    recent_results = ""
    if state["tool_results"]:
        for tr in state["tool_results"][-3:]:
            recent_results += f"\n工具: {tr.get('tool', 'unknown')}\n"
            recent_results += f"成功: {tr.get('success', False)}\n"
            recent_results += f"输出: {tr.get('output', '')[:200]}\n"

    # 构建失败信息
    failure_info = ""
    if state["consecutive_failures"] > 0:
        failure_info = f"连续失败 {state['consecutive_failures']} 次"

    # 构建验证差距信息
    verification_gap = ""
    if state["verification_gaps"]:
        for gap in state["verification_gaps"]:
            verification_gap += f"\n子目标 {gap['subgoal_id']}: {gap['criteria']}\n"
            verification_gap += f"实际结果: {gap['actual_result']}\n"
            verification_gap += f"建议修复: {gap['suggested_fix']}\n"

    # 构建消息
    system_msg = PLANNING_SYSTEM.format(
        original_goal=state["original_goal"],
        current_subgoal=current_subgoal["description"],
        phase=state["phase"],
        completed_subgoals=completed_subgoals,
        recent_results=recent_results,
        failure_info=failure_info,
        verification_gap=verification_gap,
    )

    user_msg = PLANNING_USER.format(
        iteration=state["iteration"],
        max_iterations=state["max_iterations"],
        consecutive_failures=state["consecutive_failures"],
    )

    messages = [
        ("system", system_msg),
        ("human", user_msg),
    ]

    logger.info(f"规划子目标: {current_subgoal['description'][:50]}...")

    try:
        # 调用 LLM
        response = llm.invoke(messages)
        content = response.content

        # 解析 JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        plan = json.loads(content)

        # 存储计划
        return {
            "phase": "executing",
            "messages": [("ai", f"计划: {plan.get('reasoning', '')}")],
            "tool_results": state["tool_results"] + [{
                "tool": "planner",
                "plan": plan,
                "success": True,
            }],
        }

    except Exception as e:
        logger.error(f"规划失败: {e}")
        return {
            "consecutive_failures": state["consecutive_failures"] + 1,
            "messages": [("ai", f"规划失败: {str(e)}")],
        }
