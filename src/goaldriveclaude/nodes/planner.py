"""规划节点 - 使用 LLM 的 tool_call 能力"""

from typing import Any

from langchain_anthropic import ChatAnthropic

from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import AgentState
from goaldriveclaude.tools import get_all_tools
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def _extract_text_content(content: Any) -> str:
    """从 LLM content 字段中提取文本，兼容字符串和 block 列表。"""
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


def _is_explanation_subgoal(subgoal: dict[str, Any]) -> bool:
    """判断是否为纯说明/回答类子目标。"""
    desc = str(subgoal.get("description", "")).lower()
    criteria_text = " ".join(str(c).lower() for c in subgoal.get("verification_criteria", []))
    full_text = f"{desc} {criteria_text}"

    explanation_keywords = [
        "说明",
        "解释",
        "回答",
        "回应",
        "确认",
        "介绍",
        "澄清",
        "是什么",
        "explain",
        "respond",
        "confirm",
        "clarify",
        "identity",
        "who are you",
        "what are you",
    ]
    action_phrases = [
        "创建文件",
        "写入文件",
        "读取文件",
        "编辑文件",
        "修改文件",
        "列出目录",
        "查看目录",
        "搜索代码",
        "运行测试",
        "执行命令",
        "安装依赖",
        "read file",
        "write file",
        "create file",
        "edit file",
        "modify file",
        "list directory",
        "find files",
        "run tests",
        "run command",
        "run bash",
        "run python",
    ]

    action_verbs = [
        "创建", "生成", "编写", "修改", "安装", "运行", "测试", "执行", "读取", "写入", "删除",
        "create", "generate", "write", "read", "edit", "modify", "install", "run", "test", "execute", "delete",
    ]
    action_objects = [
        "文件", "目录", "代码", "命令", "测试", "脚本", "package", "dependency",
        "file", "directory", "code", "command", "test", "script",
    ]

    has_explicit_action = any(k in full_text for k in action_phrases)
    has_verb_object_action = any(v in full_text for v in action_verbs) and any(o in full_text for o in action_objects)

    return any(k in desc for k in explanation_keywords) and not (has_explicit_action or has_verb_object_action)


def _requires_human_input(subgoal: dict[str, Any]) -> bool:
    """判断子目标是否需要等待用户输入后才能继续。"""
    desc = str(subgoal.get("description", "")).lower()
    criteria_text = " ".join(str(c).lower() for c in subgoal.get("verification_criteria", []))
    full_text = f"{desc} {criteria_text}"

    # 精确子串匹配
    human_input_phrases = [
        "确认用户意图", "询问用户", "等待用户", "获取用户反馈",
        "根据用户确认", "根据用户的", "用户回复", "用户回答",
        "confirm user", "ask the user", "wait for user", "get user input",
        "based on user confirmation", "depending on user",
    ]
    if any(p in full_text for p in human_input_phrases):
        return True

    # 非连续关键词组合：只要同时包含这些词，即可判定
    keyword_sets = [
        {"等待", "用户"},
        {"解析", "用户"},
        {"接收", "用户"},
        {"wait", "user"},
        {"parse", "user"},
        {"receive", "user"},
    ]
    for kw_set in keyword_sets:
        if kw_set.issubset(set(full_text.split())):
            return True

    return False


def _has_recent_human_message(messages: list[Any]) -> bool:
    """检查消息列表最后一条是否是用户输入。"""
    if not messages:
        return False
    last_msg = messages[-1]
    if isinstance(last_msg, tuple) and len(last_msg) >= 1:
        return last_msg[0] == "human"
    try:
        from langchain_core.messages import HumanMessage

        if isinstance(last_msg, HumanMessage):
            return True
    except Exception:
        pass
    return False


def _build_planning_prompt(state: AgentState, current_subgoal: dict) -> str:
    """构建自适应的 planning prompt：让 LLM 自行判断简单/复杂并选择对应模式。"""
    # 收集已完成的子目标
    completed = [sg["description"] for sg in state["subgoals"][: state["current_subgoal_index"]] if sg["status"] == "done"]

    # 收集最近的工具执行结果作为上下文
    recent_results = ""
    if state["tool_results"]:
        for tr in state["tool_results"][-3:]:
            status = "✓" if tr.get("success") else "✗"
            recent_results += f"\n{status} {tr.get('tool', 'unknown')}: {tr.get('output', '')[:150]}..."

    # 验证差距信息
    gap_info = ""
    if state["verification_gaps"]:
        gap_info = "\n注意：之前的验证发现以下问题需要修复:\n"
        for gap in state["verification_gaps"][:3]:
            gap_info += f"- {gap.get('criteria', '')}: {gap.get('suggested_fix', '')}\n"

    criteria_text = "\n".join(f"- {c}" for c in current_subgoal.get("verification_criteria", []))
    completed_text = "\n".join(f"- {c}" for c in completed) if completed else "无"

    prompt = f"""你是一个任务自适应专家。请根据当前的子目标判断它是【简单任务】还是【复杂任务】，并严格按照对应的模式执行。

## 判断标准
- 【简单任务】：只需要简单回复、确认、问候、一句话解释，不涉及代码/文件/命令/测试操作。
- 【复杂任务】：涉及代码开发、调试、重构、架构设计、问题排查、性能优化等，需要动手操作或深入分析。

## 模式要求

### 【简单任务】模式
你必须直接给出简短、自然的最终回复。只输出回复正文，绝对禁止分析、禁止标题、禁止列表、禁止过程化措辞（如“当前状态分析”“子目标”“验证标准”“下一步”“我需要”）。

### 【复杂任务】模式
如果判定为复杂任务，你的话术中必须包含（可以内嵌在 reasoning 中，不强制输出结构化标题，但思考要有逻辑）：
1. 背景：这个子目标涉及什么模块/文件/逻辑？
2. 问题定位：当前缺陷/瓶颈在哪？
3. 修改方案：需要改什么、新增什么、删除什么？
4. 验收标准：如何验证修改正确、无回归？
5. 边界意识：什么不应该做？如何避免过度设计？
只有完成上述分析后，才能调用工具或给出结构化建议。

---

当前子目标：{current_subgoal['description']}

验证标准：
{criteria_text}

已完成的子目标：
{completed_text}
"""

    if recent_results:
        prompt += f"\n最近执行结果：{recent_results}\n"

    if gap_info:
        prompt += gap_info

    prompt += f"""
工作目录：{state['working_directory']}
当前迭代：{state['iteration']}/{state['max_iterations']}

---

请现在判断并执行：
- 如果是简单任务，直接输出最终回复（一句话即可）。
- 如果是复杂任务，先进行上述五步分析，然后决定调用工具还是给出建议。

## 典型示例

【简单任务示例】
子目标：向用户发送确认回复'OK'
→ OK

子目标：问候用户并确认收到消息
→ 你好！我已收到消息，有什么可以帮你的？

【复杂任务示例】
子目标：重构认证中间件以提高安全性
→ （先分析背景：当前使用 session token 存储不符合新合规要求；定位问题：token 存储在本地内存且无加密；修改方案：替换为 JWT + Redis；验收标准：所有旧用例测试通过 + 静态扫描无高风险；边界意识：不改变现有 API 签名，只改内部实现。）然后再调用 read_file 查看当前中间件代码。
"""
    return prompt


def planner(state: AgentState) -> dict[str, Any]:
    """规划下一步操作

    核心变更：使用 LLM 的 tool_call 能力而非手动解析 JSON

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
        # 所有子目标索引已处理完，进入验证阶段
        return {"phase": "verifying"}

    current_subgoal = state["subgoals"][current_idx]

    # 更新子目标状态为 in_progress（如果原来是 pending）
    subgoals = list(state["subgoals"])  # 浅拷贝
    if current_subgoal["status"] == "pending":
        subgoals[current_idx] = {**current_subgoal, "status": "in_progress"}
        current_subgoal = subgoals[current_idx]

    # 如果当前子目标需要用户输入，但用户尚未回复，则暂停 graph 等待用户
    if _requires_human_input(current_subgoal) and not _has_recent_human_message(state.get("messages", [])):
        logger.info(f"子目标 '{current_subgoal['description'][:40]}...' 需要用户输入，暂停执行")
        return {
            "phase": "waiting_for_user",
            "subgoals": subgoals,
            "messages": [("ai", "等待用户输入以继续下一步...")],
        }

    # 构建 LLM（绑定工具！）
    tools = get_all_tools()
    llm = ChatAnthropic(
        model=config.default_model,
        api_key=config.anthropic_api_key,
        temperature=0.2,
    ).bind_tools(tools)  # ⭐ 关键：绑定工具

    # 构建 system prompt
    system_msg = _build_planning_prompt(state, current_subgoal)

    # 构建消息（包含最近的 messages 作为上下文）
    messages = [("system", system_msg)]

    # 添加最近的 AI/Human 消息作为上下文（最多3轮）
    recent_msgs = [m for m in state["messages"][-6:] if isinstance(m, tuple)]
    messages.extend(recent_msgs)

    # 如果没有最近消息，添加默认 human 消息
    if not recent_msgs:
        messages.append(("human", "请执行下一步操作。"))

    logger.info(f"规划子目标: {current_subgoal['description'][:50]}...")

    try:
        response = llm.invoke(messages)
        response_text = _extract_text_content(response.content)

        # 提取 tool_call
        if response.tool_calls:
            tool_call = response.tool_calls[0]  # 取第一个

            # 纯说明类子目标不应调用工具，强制改为直接回复动作
            if _is_explanation_subgoal(current_subgoal):
                content = response_text
                logger.info("纯说明类子目标，忽略工具调用并转为直接回复")
                return {
                    "pending_action": {
                        "tool_name": "_direct_response",
                        "tool_input": {"content": content},
                        "reasoning": "纯说明类子目标，直接输出文本",
                    },
                    "subgoals": subgoals,
                    "phase": "executing",
                }

            logger.info(f"计划调用工具: {tool_call['name']}")

            return {
                "pending_action": {
                    "tool_name": tool_call["name"],
                    "tool_input": tool_call["args"],
                    "reasoning": response_text,
                },
                "subgoals": subgoals,
                "phase": "executing",
            }
        else:
            # LLM 没有调用工具，可能是在思考或完成
            content = response_text or "规划中..."
            logger.info(f"LLM 回复（无工具调用）: {content[:100]}...")

            # 把无工具回复转成“直接回复动作”，避免空转循环
            return {
                "pending_action": {
                    "tool_name": "_direct_response",
                    "tool_input": {"content": content},
                    "reasoning": "当前子目标无需工具，直接回复",
                },
                "subgoals": subgoals,
                "phase": "executing",
            }

    except Exception as e:
        logger.error(f"规划失败: {e}")
        return {
            "consecutive_failures": state["consecutive_failures"] + 1,
            "messages": [("ai", f"规划失败: {str(e)}")],
        }
