"""Coordinator node - 拆分任务，只运行一次。"""

import json
from typing import Any

from langchain_anthropic import ChatAnthropic

from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import GoalState
from goaldriveclaude.utils.json_utils import clean_bom, parse_json_from_llm
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


COORINATION_SYSTEM_PROMPT = """你是 Coordinator，一位资深项目拆解专家。你的职责是：
1. 用一句话复述对用户目标的理解。
2. 把目标拆分成多个相互独立的子任务。

每个子任务必须满足以下约束：
- 相互独立：一个 Worker 执行它时不需要知道其他 Worker 在做什么。
- 明确产出物：必须说明产出了什么（例如"一个文件""一个通过的测试""一个可运行的服务"）。
- 可执行验证：验证标准必须是可自动执行的，不能是"代码写得好"这种模糊描述，必须是"运行 pytest 全部通过"这种可执行的标准。

如果目标非常简单（问候、确认、一句话问答），只产生 1 个对话性子任务，不要加入文件操作或命令执行。

请严格输出 JSON 格式：
{
    "goal_understanding": "对目标的理解（一句话）",
    "task_cards": [
        {
            "id": "tc_001",
            "description": "子任务描述",
            "expected_outputs": ["产出物1", "产出物2"],
            "verification_criteria": ["可执行验证标准1", "可执行验证标准2"],
            "priority": 1,
            "depends_on": []
        }
    ]
}
"""


def _validate_task_cards(data: dict) -> list[dict]:
    """验证并构建任务卡列表。"""
    raw_cards = data.get("task_cards", [])
    if not raw_cards:
        raise ValueError("没有返回任何任务卡")

    cards = []
    for i, tc in enumerate(raw_cards):
        if "description" not in tc:
            raise ValueError(f"任务卡 {i+1} 缺少 description")
        if "verification_criteria" not in tc or not tc["verification_criteria"]:
            raise ValueError(f"任务卡 {i+1} 缺少 verification_criteria")

        cards.append({
            "id": tc.get("id", f"tc_{i+1:03d}"),
            "description": tc["description"],
            "expected_outputs": tc.get("expected_outputs", []),
            "verification_criteria": tc.get("verification_criteria", []),
            "priority": tc.get("priority", i + 1),
            "depends_on": tc.get("depends_on", []),
            "worker_report": "",
            "review_feedback": [],
            "review_votes": {},
            "retry_count": 0,
            "status": "pending",
        })
    return cards


def coordinator(state: GoalState) -> dict[str, Any]:
    """Coordinator：理解目标、拆分任务卡、初始化状态。"""
    config = get_config()
    llm = ChatAnthropic(
        model=config.default_model,
        api_key=config.anthropic_api_key,
        temperature=0.2,
    )

    user_prompt = f"""目标：{state['original_goal']}
工作目录：{state['working_directory']}

请根据上面的要求，输出 JSON 格式的任务拆分。"""

    messages = [
        ("system", COORINATION_SYSTEM_PROMPT),
        ("human", user_prompt),
    ]

    logger.info(f"Coordinator 分析目标: {state['original_goal'][:50]}...")

    last_error = None
    for attempt in range(2):
        try:
            response = llm.invoke(messages)
            content = clean_bom(response.content)
            parsed = parse_json_from_llm(content)
            task_cards = _validate_task_cards(parsed)
            logger.info(f"Coordinator 拆分完成，共 {len(task_cards)} 个任务")
            return {
                "goal_understanding": parsed.get("goal_understanding", ""),
                "task_cards": task_cards,
                "current_task_index": 0,
                "phase": "working",
                "messages": [("ai", f"目标理解: {parsed.get('goal_understanding', '')}")],
            }
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            logger.warning(f"Coordinator 第 {attempt + 1} 次尝试失败: {e}")
            if attempt == 0:
                messages.append(("ai", "解析失败，请严格输出 JSON 格式。"))

    error_msg = f"无法解析 Coordinator 输出: {last_error}"
    logger.error(error_msg)
    return {
        "should_abort": True,
        "abort_reason": error_msg,
        "phase": "aborted",
        "messages": [("ai", error_msg)],
    }
