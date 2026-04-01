"""Worker Agent - 独立的 ReAct Agent，用 create_react_agent 构建。"""

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent

from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import GoalState
from goaldriveclaude.tools import get_all_tools
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def build_worker_agent():
    """构建 Worker ReAct Agent。

    Returns:
        CompiledStateGraph 类型的 ReAct Agent
    """
    config = get_config()
    tools = get_all_tools()
    llm = ChatAnthropic(
        model=config.default_model,
        api_key=config.anthropic_api_key,
        temperature=0.2,
    )
    return create_react_agent(
        model=llm,
        tools=tools,
        version="v2",
        name="WorkerAgent",
    )


def _build_worker_system_message(task: dict[str, Any], working_dir: str) -> str:
    """根据任务卡生成 Worker 的系统提示词。"""
    outputs = "\n".join(f"- {o}" for o in task.get("expected_outputs", []))
    criteria = "\n".join(f"- {c}" for c in task.get("verification_criteria", []))

    return f"""你是一个独立的软件开发 Worker。你只知道以下任务信息，不知道其他任何 Worker 或子任务的存在。

## 任务 ID
{task['id']}

## 任务描述
{task['description']}

## 预期产出物
{outputs}

## 验证标准（完成后必须满足）
{criteria}

## 工作目录
{working_dir}

## 可用工具
- read_file(path): 读取文件
- write_file(path, content): 写入文件
- edit_file(path, old_text, new_text): 替换文件中的文本
- list_directory(path="."): 列出目录
- find_files(pattern, directory="."): 查找文件
- run_bash(command): 执行 bash 命令
- run_python(code): 运行 Python 代码
- grep_search(pattern, path="."): 代码搜索
- run_tests(path="."): 运行测试
- check_syntax(path): 检查语法
- check_file_exists(path): 检查文件是否存在

## 执行要求
1. 使用 ReAct 循环（思考 → 调用工具 → 观察 → 再思考）完成任务。
2. 每一步都要明确说明你正在做什么，不要默默调用工具。
3. 任务完成后，在最后一条回复中必须包含一个简短的执行报告，格式如下：

---执行报告---
做了什么：<一句话总结>
修改/创建的文件：<文件列表>
最终状态：<成功/部分成功/失败>
"""


def invoke_worker(state: GoalState) -> dict[str, Any]:
    """调用 Worker Agent 执行当前任务，并把结果写回 GoalState。

    Args:
        state: 外层 Goal Loop 的当前状态

    Returns:
        需要合并回 GoalState 的更新字典
    """
    config = get_config()
    current_idx = state["current_task_index"]
    task_cards = list(state["task_cards"])
    task = task_cards[current_idx]

    agent = build_worker_agent()
    system_msg = _build_worker_system_message(task, state["working_directory"])

    # Worker 的输入消息
    input_messages = [
        ("system", system_msg),
        ("human", "请开始执行上面的任务。完成后给出执行报告。"),
    ]

    logger.info(f"Worker 开始执行任务: {task['id']}")

    try:
        result = agent.invoke({"messages": input_messages})
        messages = result.get("messages", [])

        # 提取最后一条 AI 消息作为 worker_report
        report = ""
        for m in reversed(messages):
            if isinstance(m, AIMessage):
                report = str(m.content)
                break

        task_cards[current_idx] = {
            **task,
            "worker_report": report,
            "status": "reviewing",
            "retry_count": task.get("retry_count", 0),
        }

        # 把 Worker 运行过程中产生的 tool_results 也同步到外层（挑选成功的）
        new_tool_results: list[dict] = []
        for m in messages:
            # ToolMessage 包含工具调用结果
            if hasattr(m, "content") and getattr(m, "type", None) == "tool":
                new_tool_results.append({
                    "tool": getattr(m, "name", "unknown"),
                    "success": True,
                    "output": str(m.content)[:500],
                    "error": "",
                })

        logger.info(f"Worker 任务 {task['id']} 执行完毕，报告长度 {len(report)}")

        return {
            "task_cards": task_cards,
            "messages": messages,
            "tool_results": new_tool_results,
            "phase": "reviewing",
            "iteration": state["iteration"] + 1,
        }

    except Exception as e:
        logger.error(f"Worker 执行异常: {e}")
        task_cards[current_idx] = {
            **task,
            "worker_report": f"执行异常: {e}",
            "status": "failed",
        }
        return {
            "task_cards": task_cards,
            "phase": "reviewing",
            "iteration": state["iteration"] + 1,
        }
