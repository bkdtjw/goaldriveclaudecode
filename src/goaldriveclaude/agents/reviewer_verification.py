"""Reviewer 3 Verification Agent - 用 create_react_agent 构建的验证执行者。"""

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent

from goaldriveclaude.config import get_config
from goaldriveclaude.tools import get_all_tools
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def build_reviewer_verification_agent():
    """构建 Reviewer 3 的 ReAct Agent（需要调用工具执行验证标准）。"""
    config = get_config()
    tools = get_all_tools()
    llm = ChatAnthropic(
        model=config.default_model,
        api_key=config.anthropic_api_key,
        temperature=0.1,
    )
    return create_react_agent(
        model=llm,
        tools=tools,
        version="v2",
        name="ReviewerVerificationAgent",
    )


def _build_reviewer_system_message(task: dict[str, Any], working_dir: str) -> str:
    criteria = "\n".join(f"- {c}" for c in task.get("verification_criteria", []))
    return f"""你是一位严格的 QA 验证工程师。你的职责是逐项执行任务卡里的验证标准，用实际工具调用的结果来判定通过或失败。

## 任务描述
{task['description']}

## 验证标准
{criteria}

## 工作目录
{working_dir}

## 可用工具
- read_file, write_file, edit_file, list_directory, find_files
- run_bash, run_python, grep_search
- run_tests, check_syntax, check_file_exists

## 验证要求
1. 对每条验证标准，使用合适的工具去实际执行检查，不要相信 Worker 的自我报告。
2. 记录每条标准的执行结果（使用了什么工具、输出是什么、是否通过）。
3. 最后必须给出总体结论：PASS 或 REJECT，以及简短的总评。
4. 总体结论格式必须包含以下标记之一：
   总体投票：PASS
   总体投票：REJECT
"""


def invoke_reviewer_verification(task: dict[str, Any], working_dir: str) -> dict[str, Any]:
    """调用 Reviewer 3 执行验证，返回投票结果。"""
    agent = build_reviewer_verification_agent()
    system_msg = _build_reviewer_system_message(task, working_dir)

    input_messages = [
        ("system", system_msg),
        ("human", "请开始验证上述标准，使用工具实际检查。"),
    ]

    logger.info(f"Reviewer 3 开始验证任务: {task['id']}")

    try:
        result = agent.invoke({"messages": input_messages})
        messages = result.get("messages", [])

        content = ""
        for m in reversed(messages):
            if isinstance(m, AIMessage):
                content = str(m.content)
                break

        vote = "pass" if "总体投票：PASS" in content or "总体投票: PASS" in content else "reject"
        logger.info(f"Reviewer 3 验证结果: {vote}")

        return {
            "vote": vote,
            "reasoning": content,
        }
    except Exception as e:
        logger.error(f"Reviewer 3 验证异常: {e}")
        return {
            "vote": "reject",
            "reasoning": f"验证过程中发生异常: {e}",
        }
