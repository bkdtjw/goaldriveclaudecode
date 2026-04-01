"""Global Verifier - 全局集成验证节点。"""

from typing import Any

from langchain_anthropic import ChatAnthropic

from goaldriveclaude.agents.reviewer_verification import invoke_reviewer_verification
from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import GoalState
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def _build_global_task(task_cards: list[dict]) -> dict[str, Any]:
    """构建一个 synthetic 的全局验证任务卡。"""
    reports = []
    for tc in task_cards:
        reports.append(
            f"任务 {tc['id']}: {tc['description']}\n"
            f"  产出物: {', '.join(tc.get('expected_outputs', []))}\n"
            f"  报告: {tc.get('worker_report', '')[:300]}"
        )
    full_report = "\n\n".join(reports)

    return {
        "id": "global_verify",
        "description": "全局集成验证：检查所有子任务的产出物组合在一起是否能正常工作",
        "expected_outputs": ["所有产出物无冲突、可组合运行"],
        "verification_criteria": [
            "所有文件之间无命名冲突或接口不兼容",
            "关键功能链能端到端运行",
            "没有重复实现或逻辑矛盾",
        ],
        "worker_report": full_report,
    }


def _global_code_quality_review(llm, global_task: dict, working_dir: str) -> dict[str, str]:
    prompt = f"""你是一位全局架构审查员。请审查以下所有 Worker 产出物组合在一起的整体代码质量。

## 全局上下文
工作目录: {working_dir}

## 所有 Worker 的报告摘要
{global_task['worker_report'][:2500]}

## 审查维度
- 各模块之间是否存在接口不匹配或重复代码
- 整体代码风格是否一致
- 是否存在跨模块的设计缺陷

请输出投票和理由。最后一行必须是：
投票：PASS
或
投票：REJECT
"""
    try:
        response = llm.invoke([("human", prompt)])
        content = str(response.content)
        vote = "pass" if "投票：PASS" in content or "投票: PASS" in content else "reject"
        return {"vote": vote, "reasoning": content}
    except Exception as e:
        return {"vote": "reject", "reasoning": f"审查异常: {e}"}


def _global_functional_review(llm, task_cards: list[dict]) -> dict[str, str]:
    descriptions = "\n".join(f"- {tc['id']}: {tc['description']}" for tc in task_cards)
    prompt = f"""你是一位全局功能审查员。请判断以下所有子任务组合在一起是否形成了完整且一致的目标实现。

## 子任务列表
{descriptions}

## 审查维度
- 合在一起是否完整覆盖了原始目标
- 各子任务产出物之间是否存在功能冲突或空白
- 边界情况是否被整体考虑

请输出投票和理由。最后一行必须是：
投票：PASS
或
投票：REJECT
"""
    try:
        response = llm.invoke([("human", prompt)])
        content = str(response.content)
        vote = "pass" if "投票：PASS" in content or "投票: PASS" in content else "reject"
        return {"vote": vote, "reasoning": content}
    except Exception as e:
        return {"vote": "reject", "reasoning": f"审查异常: {e}"}


def _identify_faulty_tasks(feedback_list: list[str], task_cards: list[dict]) -> list[int]:
    """根据全局反馈，定位需要重新激活的任务索引。"""
    # 启发式：如果反馈中提到了任务 ID，就激活对应的任务
    indices = set()
    full_feedback = " ".join(feedback_list).lower()
    for i, tc in enumerate(task_cards):
        if tc["id"].lower() in full_feedback:
            indices.add(i)
    # 如果没有命中任何任务，默认激活最后一个（通常是最复杂的集成点）
    if not indices and task_cards:
        indices.add(len(task_cards) - 1)
    return sorted(indices)


def global_verifier(state: GoalState) -> dict[str, Any]:
    """全局集成验证：所有任务独立通过后，再整体投票一次。"""
    config = get_config()
    task_cards = list(state["task_cards"])
    llm = ChatAnthropic(
        model=config.default_model,
        api_key=config.anthropic_api_key,
        temperature=0.1,
    )

    logger.info("开始全局集成验证...")

    global_task = _build_global_task(task_cards)

    # Reviewer 1 & 2 针对全局做 LLM 审查
    r1 = _global_code_quality_review(llm, global_task, state["working_directory"])
    r2 = _global_functional_review(llm, task_cards)

    # Reviewer 3 用工具验证全局产出物
    r3 = invoke_reviewer_verification(global_task, state["working_directory"])

    logger.info(f"全局验证投票: 代码质量={r1['vote']}, 功能完整={r2['vote']}, 验证执行={r3['vote']}")

    votes = {
        "global_code_quality": r1["vote"],
        "global_functional": r2["vote"],
        "global_verification": r3["vote"],
    }

    pass_count = sum(1 for v in votes.values() if v == "pass")
    reject_count = len(votes) - pass_count

    if pass_count >= 2:
        logger.info("全局集成验证通过")
        return {
            "phase": "done",
            "messages": [("ai", f"🎉 全局验证通过 ({pass_count}/3)！目标达成。")],
        }

    feedback = []
    if r1["vote"] == "reject":
        feedback.append(f"[全局代码质量] {r1['reasoning'][:300]}")
    if r2["vote"] == "reject":
        feedback.append(f"[全局功能] {r2['reasoning'][:300]}")
    if r3["vote"] == "reject":
        feedback.append(f"[全局验证] {r3['reasoning'][:300]}")

    logger.warning(f"全局集成验证未通过 ({reject_count}/3 REJECT)")

    # 定位并重新激活相关任务
    faulty_indices = _identify_faulty_tasks(feedback, task_cards)
    for idx in faulty_indices:
        task_cards[idx] = {**task_cards[idx], "status": "in_progress", "review_feedback": feedback}

    # 把 current_task_index 指向第一个需要修复的任务
    restart_idx = faulty_indices[0] if faulty_indices else 0

    return {
        "task_cards": task_cards,
        "current_task_index": restart_idx,
        "phase": "working",
        "messages": [("ai", f"全局验证未通过 ({reject_count}/3)，需要修复相关任务。反馈：{feedback}")],
    }
