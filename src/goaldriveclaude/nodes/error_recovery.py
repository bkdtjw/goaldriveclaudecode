"""错误恢复节点 - 结构化错误恢复策略

策略：
1. 分析最近的错误类型
2. 根据错误类型选择恢复策略
3. 超过恢复次数上限则请求人工介入
"""

from typing import Any

from goaldriveclaude.core.state import AgentState
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def error_recovery(state: AgentState) -> dict[str, Any]:
    """结构化错误恢复

    Args:
        state: 当前状态

    Returns:
        更新后的状态字段
    """
    # 超过5次连续失败，请求人工介入
    if state["consecutive_failures"] >= 5:
        logger.warning(f"连续失败 {state['consecutive_failures']} 次，请求人工介入")
        return {
            "needs_human_input": True,
            "phase": "human_input",
            "messages": [("ai", f"连续失败 {state['consecutive_failures']} 次，需要人工介入")],
        }

    # 获取最近的失败
    recent_failures = [
        r for r in state["tool_results"][-5:] if not r.get("success")
    ]

    if not recent_failures:
        # 没有最近失败，清零返回
        return {
            "phase": "planning",
            "consecutive_failures": 0,
        }

    last_error = recent_failures[-1].get("error", "")

    # 检测重复错误（同样的错误出现 3 次）
    error_signatures = [r.get("error", "")[:100] for r in recent_failures]
    if len(error_signatures) >= 3 and len(set(error_signatures[-3:])) == 1:
        error_msg = f"同一个错误重复出现 3 次，需要人工介入: {last_error[:200]}"
        logger.error(error_msg)
        return {
            "needs_human_input": True,
            "phase": "human_input",
            "messages": [("ai", error_msg)],
        }

    # 分析错误类型并给出建议
    recovery_message = _analyze_error_and_suggest(last_error)

    # 正常恢复：清零连续失败计数，回到规划
    logger.info(f"错误恢复: {recovery_message}")

    return {
        "consecutive_failures": 0,  # 重置计数
        "phase": "planning",
        "messages": [("ai", recovery_message)],
    }


def _analyze_error_and_suggest(error: str) -> str:
    """分析错误类型并给出恢复建议"""
    error_lower = error.lower()

    if "file not found" in error_lower or "no such file" in error_lower:
        return f"错误恢复：文件不存在。将尝试创建或查找正确路径。错误: {error[:200]}"

    if "permission denied" in error_lower:
        return f"错误恢复：权限不足。将尝试使用不同方式或请求授权。错误: {error[:200]}"

    if "syntax error" in error_lower:
        return f"错误恢复：语法错误。将尝试修正代码。错误: {error[:200]}"

    if "timeout" in error_lower:
        return f"错误恢复：执行超时。将尝试优化或分步执行。错误: {error[:200]}"

    if "unknown tool" in error_lower:
        return f"错误恢复：工具调用错误。将尝试使用可用工具。错误: {error[:200]}"

    # 默认
    return f"错误恢复：{error[:200]}，将尝试不同策略"
