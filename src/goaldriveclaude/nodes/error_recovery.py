"""错误恢复节点 - 处理错误和失败"""

import json
from typing import Any

from langchain_anthropic import ChatAnthropic

from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import AgentState
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def error_recovery(state: AgentState) -> dict[str, Any]:
    """尝试从错误中恢复

    Args:
        state: 当前状态

    Returns:
        更新后的状态字段
    """
    config = get_config()

    # 如果连续失败太多，需要人工介入
    if state["consecutive_failures"] >= config.max_consecutive_failures:
        logger.warning(f"连续失败 {state['consecutive_failures']} 次，需要人工介入")
        return {
            "needs_human_input": True,
            "messages": [(
                "ai",
                f"连续失败 {state['consecutive_failures']} 次，需要人工帮助。"
            )],
        }

    # 获取最近的失败信息
    last_failure = None
    for tr in reversed(state["tool_results"]):
        if not tr.get("success", True):
            last_failure = tr
            break

    if last_failure is None:
        # 没有失败，继续规划
        return {
            "phase": "planning",
            "messages": [("ai", "错误恢复：未发现错误，继续执行")],
        }

    logger.info(f"尝试恢复错误: {last_failure.get('error', 'unknown error')[:100]}...")

    # 简单的错误恢复策略
    error_msg = str(last_failure.get("error", "")).lower()

    # 文件不存在错误
    if "not found" in error_msg or "不存在" in error_msg:
        return {
            "phase": "planning",
            "messages": [("ai", "错误恢复：文件不存在，需要先创建文件")],
        }

    # 权限错误
    if "permission" in error_msg or "权限" in error_msg:
        return {
            "phase": "planning",
            "messages": [("ai", "错误恢复：权限不足，尝试其他方法")],
        }

    # 语法错误
    if "syntax" in error_msg or "语法" in error_msg:
        return {
            "phase": "planning",
            "messages": [("ai", "错误恢复：代码有语法错误，需要修复")],
        }

    # 默认：返回规划阶段重试
    return {
        "phase": "planning",
        "messages": [("ai", "错误恢复：将尝试不同的方法")],
    }
