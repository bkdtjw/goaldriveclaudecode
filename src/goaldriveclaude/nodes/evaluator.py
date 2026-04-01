"""Evaluator node: assess current subgoal completion."""

from typing import Any

from langchain_anthropic import ChatAnthropic

from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import AgentState
from goaldriveclaude.utils.json_utils import parse_json_from_llm
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def _extract_text_content(content: Any) -> str:
    """Extract text from LLM content that may be string or block list."""
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
                continue

            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
                    continue

                nested_content = block.get("content")
                if isinstance(nested_content, str):
                    text_parts.append(nested_content)

        return "\n".join(part.strip() for part in text_parts if part and part.strip())

    return ""


def _find_next_subgoal_index(subgoals: list[dict[str, Any]]) -> int | None:
    """Find next unfinished subgoal index."""
    for i, sg in enumerate(subgoals):
        if sg.get("status") in ("pending", "in_progress", "failed"):
            return i
    return None


def _is_explanation_subgoal(subgoal: dict[str, Any]) -> bool:
    """判断是否为纯说明/回答类子目标。"""
    desc = str(subgoal.get("description", "")).lower()
    criteria_text = " ".join(str(c).lower() for c in subgoal.get("verification_criteria", []))
    full_text = f"{desc} {criteria_text}"

    explanation_keywords = [
        "说明", "解释", "回答", "回应", "确认", "介绍", "澄清", "是什么",
        "explain", "respond", "confirm", "clarify", "identity", "who are you", "what are you",
    ]
    return any(k in desc for k in explanation_keywords)


def _should_auto_complete(current_subgoal: dict[str, Any], state: AgentState) -> bool:
    """对于纯说明/确认类子目标，如果已经发了直接回复，自动认为完成。"""
    if not _is_explanation_subgoal(current_subgoal):
        return False
    for tr in reversed(state.get("tool_results", [])):
        if tr.get("tool") == "_direct_response" and tr.get("success"):
            return True
    return False


def _build_eval_prompt(state: AgentState, current_subgoal: dict[str, Any]) -> str:
    """Build evaluation prompt."""
    latest_result = state["tool_results"][-1] if state["tool_results"] else None
    recent_result_text = "无"
    if latest_result:
        status = "成功" if latest_result.get("success") else "失败"
        recent_result_text = (
            f"- {latest_result.get('tool', 'unknown')}: {status}\n"
            f"  输出: {str(latest_result.get('output', ''))[:600]}"
        )

    # 收集最近对话上下文
    recent_messages = []
    for m in state.get("messages", [])[-6:]:
        if isinstance(m, tuple) and len(m) >= 2:
            role, content = m[0], str(m[1])[:200]
            recent_messages.append(f"{role}: {content}")
    recent_messages_text = "\n".join(recent_messages) if recent_messages else "无"

    prompt = f"""评估当前子目标的完成情况。

子目标：{current_subgoal['description']}

验证标准：
"""
    for criteria in current_subgoal.get("verification_criteria", []):
        prompt += f"- {criteria}\n"

    prompt += f"""
最近一次执行结果：
{recent_result_text}

最近对话上下文：
{recent_messages_text}

如果子目标是"确认用户意图"、"询问用户"等类型，只要 AI 已经向用户发出了询问或回应，即视为完成。
请综合最近一次执行结果和对话上下文进行评估。

输出 JSON 格式：
{{
    "subgoal_completed": true/false,
    "reasoning": "评估理由...",
    "next_action_hint": "如果未完成，下一步建议做什么"
}}
"""
    return prompt


def evaluator(state: AgentState) -> dict[str, Any]:
    """Evaluate whether the current subgoal is completed."""
    config = get_config()
    current_idx = state["current_subgoal_index"]

    # 如果处于等待用户状态，不要覆盖
    if state.get("phase") == "waiting_for_user":
        return {"phase": "waiting_for_user"}

    if current_idx >= len(state["subgoals"]):
        return {"phase": "verifying"}

    current_subgoal = state["subgoals"][current_idx]

    if current_subgoal.get("status") == "done":
        next_idx = _find_next_subgoal_index(state["subgoals"])
        if next_idx is not None:
            return {
                "current_subgoal_index": next_idx,
                "phase": "planning",
            }
        return {"phase": "verifying"}

    # 快速通道：纯说明类子目标如果已有直接回复，自动判完成
    if _should_auto_complete(current_subgoal, state):
        logger.info(f"Subgoal {current_subgoal['id']} auto-completed (explanation with direct response)")
        subgoals = []
        for i, sg in enumerate(state["subgoals"]):
            if i == current_idx:
                subgoals.append({**sg, "status": "done"})
            else:
                subgoals.append(sg)

        next_idx = _find_next_subgoal_index(subgoals)
        if next_idx is not None:
            return {
                "subgoals": subgoals,
                "current_subgoal_index": next_idx,
                "consecutive_failures": 0,
                "phase": "planning",
                "messages": [("ai", f" 子目标完成: {current_subgoal['description']}")],
            }
        return {
            "subgoals": subgoals,
            "consecutive_failures": 0,
            "phase": "verifying",
            "messages": [("ai", "所有子目标已完成，进入验证阶段")],
        }

    llm = ChatAnthropic(
        model=config.default_model,
        api_key=config.anthropic_api_key,
        temperature=0.2,
    )

    prompt = _build_eval_prompt(state, current_subgoal)

    try:
        response = llm.invoke([("human", prompt)])
        response_text = _extract_text_content(response.content)
        evaluation = parse_json_from_llm(response_text)

        if evaluation.get("subgoal_completed"):
            logger.info(f"Subgoal {current_subgoal['id']} evaluated as completed")

            subgoals = []
            for i, sg in enumerate(state["subgoals"]):
                if i == current_idx:
                    subgoals.append({**sg, "status": "done"})
                else:
                    subgoals.append(sg)

            next_idx = _find_next_subgoal_index(subgoals)
            if next_idx is not None:
                return {
                    "subgoals": subgoals,
                    "current_subgoal_index": next_idx,
                    "consecutive_failures": 0,
                    "phase": "planning",
                    "messages": [("ai", f" 子目标完成: {current_subgoal['description']}")],
                }

            return {
                "subgoals": subgoals,
                "consecutive_failures": 0,
                "phase": "verifying",
                "messages": [("ai", "所有子目标已完成，进入验证阶段")],
            }

        logger.info(f"Subgoal {current_subgoal['id']} not completed, continue planning")
        return {
            "phase": "planning",
            "consecutive_failures": 0,
            "messages": [(
                "ai",
                str(evaluation.get("next_action_hint") or "继续执行当前子目标"),
            )],
        }

    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        return {
            "consecutive_failures": state["consecutive_failures"] + 1,
            "phase": "planning",
        }
