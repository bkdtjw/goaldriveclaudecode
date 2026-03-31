"""验证节点 - 目标验证（核心差异）"""

import json
from typing import Any

from langchain_anthropic import ChatAnthropic

from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import AgentState
from goaldriveclaude.prompts.verification import VERIFICATION_SYSTEM, VERIFICATION_USER
from goaldriveclaude.tools.verification import (
    check_file_exists,
    check_syntax,
    compare_output,
    run_tests,
)
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def verifier(state: AgentState) -> dict[str, Any]:
    """验证目标是否真正达成

    Args:
        state: 当前状态

    Returns:
        更新后的状态字段
    """
    config = get_config()

    # 检查验证尝试次数
    if state["verification_attempts"] >= config.max_verification_attempts:
        return {
            "needs_human_input": True,
            "messages": [("ai", "多次验证失败，需要人工介入")],
        }

    # 初始化 LLM
    llm = ChatAnthropic(
        model=config.default_model,
        api_key=config.anthropic_api_key,
        temperature=0.2,
    )

    # 构建所有子目标及验证标准
    subgoals_with_criteria = ""
    for sg in state["subgoals"]:
        subgoals_with_criteria += f"\n子目标 {sg['id']}: {sg['description']}\n"
        for criteria in sg["verification_criteria"]:
            subgoals_with_criteria += f"  - {criteria}\n"

    # 先执行一些自动验证
    auto_results = []
    for sg in state["subgoals"]:
        for criteria in sg["verification_criteria"]:
            # 简单的自动验证逻辑
            if "文件" in criteria and "存在" in criteria:
                # 尝试提取文件名
                words = criteria.split()
                for word in words:
                    if "." in word:
                        result = check_file_exists(word)
                        auto_results.append({
                            "subgoal_id": sg["id"],
                            "criteria": criteria,
                            "result": result,
                        })
                        break

    # 构建消息
    system_msg = VERIFICATION_SYSTEM

    user_msg = VERIFICATION_USER.format(
        original_goal=state["original_goal"],
        subgoals_with_criteria=subgoals_with_criteria,
        working_directory=state["working_directory"],
    )

    messages = [
        ("system", system_msg),
        ("human", user_msg),
    ]

    logger.info(f"验证目标: {state['original_goal'][:50]}...")

    try:
        # 调用 LLM 进行验证规划
        response = llm.invoke(messages)
        content = response.content

        # 解析 JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        verification = json.loads(content)

        overall_passed = verification.get("overall_passed", False)

        # 构建验证报告
        report_lines = ["验证报告:", ""]
        for vr in verification.get("results", []):
            status = "✅" if vr.get("passed") else "❌"
            report_lines.append(f"{status} {vr.get('criteria', '')}")
            if not vr.get("passed") and vr.get("fix_suggestion"):
                report_lines.append(f"   建议: {vr.get('fix_suggestion')}")
        report_lines.append("")
        report_lines.append(f"总结: {verification.get('summary', '')}")

        verification_report = "\n".join(report_lines)

        if overall_passed:
            logger.info("目标验证通过！")
            return {
                "goal_verified": True,
                "verification_report": verification_report,
                "phase": "done",
                "messages": [("ai", verification_report)],
            }
        else:
            logger.warning("目标验证失败，需要重新规划")
            # 构建验证差距
            gaps = []
            for vr in verification.get("results", []):
                if not vr.get("passed"):
                    gaps.append({
                        "subgoal_id": "unknown",  # 需要从 criteria 推断
                        "criteria": vr.get("criteria", ""),
                        "actual_result": vr.get("evidence", ""),
                        "suggested_fix": vr.get("fix_suggestion", ""),
                    })

            return {
                "goal_verified": False,
                "verification_report": verification_report,
                "verification_attempts": state["verification_attempts"] + 1,
                "verification_gaps": gaps,
                "phase": "planning",
                "current_subgoal_index": 0,  # 从头开始
                "messages": [("ai", verification_report)],
            }

    except Exception as e:
        logger.error(f"验证失败: {e}")
        return {
            "verification_attempts": state["verification_attempts"] + 1,
            "messages": [("ai", f"验证过程出错: {str(e)}")],
        }
