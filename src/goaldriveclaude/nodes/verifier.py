"""验证节点 - 真正执行验证（目标驱动的灵魂）

设计思路：
1. 让 LLM 为每个 verification_criteria 生成验证计划（要调用什么工具）
2. 实际执行这些工具调用
3. 用执行结果判断通过/失败
4. 汇总报告
"""

import json
from typing import Any

from langchain_anthropic import ChatAnthropic

from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import AgentState
from goaldriveclaude.tools import get_tool_by_name
from goaldriveclaude.utils.json_utils import parse_json_from_llm
from goaldriveclaude.utils.logger import get_logger

logger = get_logger(__name__)


def _generate_verification_plan(llm, state: AgentState) -> list[dict]:
    """让 LLM 为每个 criteria 生成验证计划

    返回格式：
    [
        {"criteria": "...", "tool_name": "run_bash", "tool_input": {"command": "python -m pytest"}, "expected": "passed"},
    ]
    """
    # 构建所有待验证的 criteria
    all_criteria = []
    for sg in state["subgoals"]:
        for c in sg.get("verification_criteria", []):
            all_criteria.append({"subgoal_id": sg["id"], "criteria": c})

    if not all_criteria:
        return []

    prompt = f"""你是一个 QA 工程师。请为以下验证标准生成具体的验证计划。

目标：{state["original_goal"]}

待验证标准：
{json.dumps(all_criteria, ensure_ascii=False, indent=2)}

可用工具：
- read_file(path): 读取文件内容
- write_file(path, content): 写入文件
- edit_file(path, old_string, new_string): 编辑文件
- list_directory(path="."): 列出目录
- find_files(pattern, path="."): 查找文件
- run_bash(command, timeout=30): 执行 bash 命令
- run_python(code, timeout=30): 执行 Python 代码
- grep_search(pattern, path="."): 搜索内容
- check_file_exists(path): 检查文件是否存在
- check_syntax(path): 检查代码语法
- run_tests(path="."): 运行 pytest 测试
- compare_output(command, expected_contains): 执行命令并检查输出

严格输出 JSON 数组，每项包含 criteria, tool_name, tool_input：
[{{"criteria": "...", "tool_name": "...", "tool_input": {{...}}}}]"""

    try:
        response = llm.invoke([("human", prompt)])
        return parse_json_from_llm(response.content)
    except Exception as e:
        logger.error(f"生成验证计划失败: {e}")
        return []


def _check_pass(result: dict, expected: str | None) -> bool:
    """检查工具执行结果是否通过"""
    if isinstance(result, dict):
        return result.get("success", False)
    return True


def _analyze_gaps(llm, state: AgentState, gaps: list[dict]) -> list[dict]:
    """让 LLM 分析失败原因并给出修复建议"""
    if not gaps:
        return gaps

    prompt = f"""以下验证项失败了，请分析原因并给出修复建议：

{json.dumps(gaps, ensure_ascii=False, indent=2)}

目标：{state["original_goal"]}

为每个失败项添加 suggested_fix 字段，说明应该怎么修复。
输出 JSON 数组，每项包含 criteria, actual_result, suggested_fix。"""

    try:
        response = llm.invoke([("human", prompt)])
        analyzed = parse_json_from_llm(response.content)
        # 确保返回的是列表
        if isinstance(analyzed, list):
            return analyzed
        if isinstance(analyzed, dict) and "gaps" in analyzed:
            return analyzed["gaps"]
        return gaps
    except Exception as e:
        logger.warning(f"分析差距失败: {e}")
        return gaps


def _is_actionable_criteria(criteria: str) -> bool:
    """判断验证标准是否涉及可执行操作（文件、命令、代码等）。"""
    text = criteria.lower()
    action_keywords = [
        "文件", "目录", "代码", "命令", "测试", "脚本", "语法", "输出",
        "file", "directory", "code", "command", "test", "script", "syntax", "output",
        "存在", "运行", "执行", "通过", "失败", "正确", "错误",
        "exists", "run", "execute", "pass", "fail", "correct", "error",
    ]
    return any(k in text for k in action_keywords)


def _all_subgoals_are_conversational(subgoals: list[dict]) -> bool:
    """判断是否所有子目标均为对话/说明类，无可执行验证标准。"""
    if not subgoals:
        return True
    for sg in subgoals:
        criteria_list = sg.get("verification_criteria", [])
        # 如果任意 criteria 涉及可执行操作，则不是纯对话型
        if any(_is_actionable_criteria(c) for c in criteria_list):
            return False
    return True


def verifier(state: AgentState) -> dict[str, Any]:
    """验证目标是否真正达成

    这是目标驱动的灵魂。Verifier 自己执行工具来验证，而不是让 LLM 幻想一个报告。

    Args:
        state: 当前状态

    Returns:
        更新后的状态字段
    """
    config = get_config()

    if state["verification_attempts"] >= config.max_verification_attempts:
        logger.warning("验证尝试次数达到上限")
        return {
            "needs_human_input": True,
            "phase": "human_input",
            "messages": [("ai", "验证多次失败，需要人工介入")],
        }

    # 纯对话类目标无可执行验证标准，直接通过
    if _all_subgoals_are_conversational(state["subgoals"]):
        logger.info("纯对话类目标，跳过工具验证")
        return {
            "goal_verified": True,
            "verification_report": "目标为对话/确认类，无需工具验证",
            "phase": "done",
            "messages": [("ai", "目标已完成")],
        }

    # 初始化 LLM
    llm = ChatAnthropic(
        model=config.default_model,
        api_key=config.anthropic_api_key,
        temperature=0.1,  # 低温度，更确定性
    )

    # Step 1: 让 LLM 生成验证计划
    logger.info("生成验证计划...")
    verification_plan = _generate_verification_plan(llm, state)

    if not verification_plan:
        logger.warning("没有验证计划，假设验证通过")
        return {
            "goal_verified": True,
            "verification_report": "没有可验证的标准，假设通过",
            "phase": "done",
        }

    # Step 2: 逐一执行验证 ⭐
    logger.info(f"执行验证计划，共 {len(verification_plan)} 项")
    results = []

    for item in verification_plan:
        criteria = item.get("criteria", "")
        tool_name = item.get("tool_name", "")
        tool_input = item.get("tool_input", {})
        expected = item.get("expected")

        tool = get_tool_by_name(tool_name)
        if tool is None:
            results.append({
                "criteria": criteria,
                "passed": False,
                "evidence": f"工具不存在: {tool_name}",
                "method": tool_name,
            })
            continue

        try:
            result = tool.invoke(tool_input)
            passed = _check_pass(result, expected)

            evidence = ""
            if isinstance(result, dict):
                if result.get("success"):
                    evidence = str(result.get("output", ""))[:500]
                else:
                    evidence = str(result.get("error", ""))[:500]
            else:
                evidence = str(result)[:500]

            results.append({
                "criteria": criteria,
                "passed": passed,
                "evidence": evidence,
                "method": f"{tool_name}({tool_input})",
            })

        except Exception as e:
            results.append({
                "criteria": criteria,
                "passed": False,
                "evidence": str(e)[:500],
                "method": f"{tool_name}({tool_input})",
            })

    # Step 3: 汇总
    all_passed = all(r["passed"] for r in results)

    report_lines = ["=== 验证报告 ===", ""]
    for r in results:
        status = "✓" if r["passed"] else "✗"
        report_lines.append(f"{status} {r['criteria']}")
        if not r["passed"]:
            report_lines.append(f"   证据: {r['evidence'][:100]}...")
    report = "\n".join(report_lines)

    if all_passed:
        logger.info("所有验证通过！")
        return {
            "goal_verified": True,
            "verification_report": report,
            "phase": "done",
            "messages": [("ai", report)],
        }

    logger.warning("验证失败，准备重新规划")

    # 构建差距信息
    gaps = [
        {
            "criteria": r["criteria"],
            "actual_result": r["evidence"],
            "suggested_fix": "",
        }
        for r in results if not r["passed"]
    ]

    # 让 LLM 分析差距
    gap_analysis = _analyze_gaps(llm, state, gaps)

    # 重新激活失败的子目标
    failed_criteria = {r["criteria"] for r in results if not r["passed"]}
    subgoals = []
    for sg in state["subgoals"]:
        if any(c in failed_criteria for c in sg.get("verification_criteria", [])):
            subgoals.append({**sg, "status": "in_progress"})
        else:
            subgoals.append(sg)

    # 找到第一个需要重做的子目标
    restart_idx = next(
        (i for i, sg in enumerate(subgoals) if sg["status"] == "in_progress"), 0
    )

    return {
        "goal_verified": False,
        "verification_report": report,
        "verification_attempts": state["verification_attempts"] + 1,
        "verification_gaps": gap_analysis,
        "subgoals": subgoals,
        "current_subgoal_index": restart_idx,
        "phase": "planning",
        "messages": [("ai", report + "\n\n验证失败，将重新规划执行。")],
    }
