"""CLI 入口"""

import click
from rich.console import Console

from goaldriveclaude.config import get_config, reload_config
from goaldriveclaude.core.graph import build_graph
from goaldriveclaude.core.state import create_initial_state
from goaldriveclaude.utils.display import Display
from goaldriveclaude.utils.session import SessionManager


@click.group(invoke_without_command=True)
@click.argument("goal", required=False)
@click.option("-i", "--interactive", is_flag=True, help="交互模式")
@click.option("--resume", type=str, help="恢复会话 ID")
@click.option("--history", is_flag=True, help="查看历史会话")
@click.option("--max-iterations", type=int, default=50, help="最大迭代次数")
@click.option("--verbose", "-v", is_flag=True, help="详细日志")
@click.pass_context
def main(ctx, goal, interactive, resume, history, max_iterations, verbose):
    """GoalDriveClaude - 目标驱动的 AI 编程 Agent

    使用方式：
      goaldriveclaude "创建一个 Flask 博客应用"
      goaldriveclaude -i
      goaldriveclaude --resume abc123
    """
    # 重载配置
    reload_config()
    config = get_config()

    if verbose:
        config.log_level = "DEBUG"

    display = Display()
    session_manager = SessionManager()

    # 显示历史
    if history:
        sessions = session_manager.list_sessions()
        display.show_history(sessions)
        return

    # 恢复会话
    if resume:
        state_dict = session_manager.load_state(resume)
        if state_dict:
            display.show_goal_header(state_dict.get("original_goal", ""))
            _run_agent(state_dict, display, session_manager, resume)
        else:
            display.show_error(f"找不到会话: {resume}")
        return

    # 交互模式
    if interactive:
        goal = display.prompt_user("请输入你的目标")

    # 检查目标
    if not goal:
        click.echo("请提供目标或使用 -i 进入交互模式")
        click.echo("使用 goaldriveclaude --help 查看帮助")
        ctx.exit(1)

    # 创建新会话
    session_id = session_manager.create_session(goal)

    # 创建初始状态
    initial_state = create_initial_state(goal, max_iterations)
    initial_state["session_id"] = session_id

    display.show_goal_header(goal)
    _run_agent(initial_state, display, session_manager, session_id)


def _run_agent(state: dict, display: Display, session_manager: SessionManager, session_id: str):
    """运行 Agent

    Args:
        state: 初始状态
        display: 显示对象
        session_manager: 会话管理器
        session_id: 会话 ID
    """
    try:
        # 构建图
        graph = build_graph()

        # 运行图
        for event in graph.stream(state, stream_mode="values"):
            # 显示进度
            if "subgoals" in event:
                display.show_subgoal_progress(event["subgoals"])

            # 显示当前阶段
            if "phase" in event:
                phase = event["phase"]
                if phase == "analyzing":
                    display.show_node_action("goal_analyzer", "分析目标中...")
                elif phase == "planning":
                    display.show_node_action("planner", "规划中...")
                elif phase == "executing":
                    display.show_node_action("executor", "执行工具中...")
                elif phase == "evaluating":
                    display.show_node_action("evaluator", "评估结果中...")
                elif phase == "verifying":
                    display.show_node_action("verifier", "验证目标中...")

            # 保存状态
            session_manager.save_state(session_id, event)

            # 检查是否结束
            if event.get("should_abort") or event.get("phase") == "done":
                break

        # 显示最终结果
        final_state = event
        display.show_final_summary(final_state)

        if final_state.get("goal_verified"):
            display.show_verification_report(final_state.get("verification_report", ""))

    except Exception as e:
        display.show_error(f"运行出错: {str(e)}")
        raise


if __name__ == "__main__":
    main()
