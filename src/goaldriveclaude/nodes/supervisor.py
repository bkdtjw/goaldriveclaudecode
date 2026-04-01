"""Supervisor Voting Panel - 3 个独立 Reviewer 投票节点。"""

from typing import Any

from langchain_anthropic import ChatAnthropic

from goaldriveclaude.agents.reviewer_verification import invoke_reviewer_verification
from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import GoalState
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def _review_code_quality(llm, task: dict[str, Any], worker_report: str) -> dict[str, str]:
    """Reviewer 1: 代码质量审查。"""
    prompt = f"""你是一位资深代码审查工程师。请审查以下 Worker 的产出物和报告，从代码质量维度给出 PASS 或 REJECT 的投票。

## 任务描述
{task['description']}

## Worker 执行报告
{worker_report[:2000]}

## 审查维度
- 代码是否可读、结构清晰
- 是否有明显的 bug 或逻辑错误
- 是否有适当的类型注解和文档说明
- 错误处理是否完善

请输出你的投票和理由。最后一行必须是以下格式之一：
投票：PASS
投票：REJECT
"""
    try:
        response = llm.invoke([("human", prompt)])
        content = str(response.content)
        vote = "pass" if "投票：PASS" in content or "投票: PASS" in content else "reject"
        return {"vote": vote, "reasoning": content}
    except Exception as e:
        logger.error(f"Reviewer 1 异常: {e}")
        return {"vote": "reject", "reasoning": f"审查异常: {e}"}


def _review_functional_completeness(llm, task: dict[str, Any], worker_report: str) -> dict[str, str]:
    """Reviewer 2: 功能完整性审查。"""
    criteria = "\n".join(f"- {c}" for c in task.get("verification_criteria", []))
    prompt = f"""你是一位产品经理 + QA 审查员。请审查以下 Worker 是否完整完成了任务描述中的所有要求。

## 任务描述
{task['description']}

## 预期产出物
{"\n".join(f"- {o}" for o in task.get("expected_outputs", []))}

## 验证标准
{criteria}

## Worker 执行报告
{worker_report[:2000]}

## 审查维度
- 产出物是否满足任务描述的所有要求
- 是否有遗漏的功能点
- 边界情况是否被考虑

请输出你的投票和理由。最后一行必须是以下格式之一：
投票：PASS
投票：REJECT
"""
    try:
        response = llm.invoke([("human", prompt)])
        content = str(response.content)
        vote = "pass" if "投票：PASS" in content or "投票: PASS" in content else "reject"
        return {"vote": vote, "reasoning": content}
    except Exception as e:
        logger.error(f"Reviewer 2 异常: {e}")
        return {"vote": "reject", "reasoning": f"审查异常: {e}"}


def _apply_voting_result(
    state: GoalState, votes: dict[str, str], feedback: list[str]
) -> dict[str, Any]:
    """纯函数：根据投票结果更新任务卡和状态。"""
    current_idx = state["current_task_index"]
    task_cards = list(state["task_cards"])
    task = task_cards[current_idx]
    retry_count = task.get("retry_count", 0)
    pass_count = sum(1 for v in votes.values() if v == "pass")
    reject_count = len(votes) - pass_count

    if pass_count >= 2:
        logger.info(f"任务 {task['id']} 通过投票 ({pass_count}/3)")
        task_cards[current_idx] = {
            **task,
            "review_votes": votes,
            "review_feedback": [],
            "status": "passed",
            "retry_count": retry_count,
        }
        return {
            "task_cards": task_cards,
            "phase": "working",
            "messages": [("ai", f"任务 {task['id']} 通过审查 ({pass_count}/3 PASS)")],
        }

    new_retry = retry_count + 1
    logger.warning(f"任务 {task['id']} 未通过投票 ({reject_count}/3 REJECT)，第 {new_retry} 次重做")
    task_cards[current_idx] = {
        **task,
        "review_votes": votes,
        "review_feedback": feedback,
        "status": "rejected",
        "retry_count": new_retry,
    }

    if new_retry >= 3:
        abort_reason = f"任务 {task['id']} 连续 3 次未通过 Supervisor 审查，系统暂停。"
        logger.error(abort_reason)
        return {
            "task_cards": task_cards,
            "should_abort": True,
            "abort_reason": abort_reason,
            "phase": "aborted",
            "messages": [("ai", abort_reason)],
        }

    return {
        "task_cards": task_cards,
        "phase": "working",
        "messages": [("ai", f"任务 {task['id']} 被打回重做。反馈：{feedback}")],
    }


def supervisor(state: GoalState) -> dict[str, Any]:
    """Supervisor Panel：串行执行 3 个 Reviewer，汇总投票结果。"""
    config = get_config()
    current_idx = state["current_task_index"]
    task = state["task_cards"][current_idx]
    worker_report = task.get("worker_report", "")

    llm = ChatAnthropic(
        model=config.default_model,
        api_key=config.anthropic_api_key,
        temperature=0.1,
    )

    logger.info(f"Supervisor 开始审查任务: {task['id']}")

    r1 = _review_code_quality(llm, task, worker_report)
    logger.info(f"Reviewer 1 (代码质量): {r1['vote']}")

    r2 = _review_functional_completeness(llm, task, worker_report)
    logger.info(f"Reviewer 2 (功能完整性): {r2['vote']}")

    r3 = invoke_reviewer_verification(task, state["working_directory"])
    logger.info(f"Reviewer 3 (验证执行): {r3['vote']}")

    votes = {
        "code_quality": r1["vote"],
        "functional": r2["vote"],
        "verification": r3["vote"],
    }

    feedback: list[str] = []
    if r1["vote"] == "reject":
        feedback.append(f"[代码质量] {r1['reasoning'][:300]}")
    if r2["vote"] == "reject":
        feedback.append(f"[功能完整性] {r2['reasoning'][:300]}")
    if r3["vote"] == "reject":
        feedback.append(f"[验证执行] {r3['reasoning'][:300]}")

    return _apply_voting_result(state, votes, feedback)
