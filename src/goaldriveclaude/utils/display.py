"""显示模块 - Rich 终端 UI"""

from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from goaldriveclaude.core.state import AgentState


class Display:
    """终端显示类"""

    def __init__(self):
        self.console = Console()

    def show_goal_header(self, goal: str) -> None:
        """显示目标标题"""
        self.console.print()
        self.console.print(
            Panel(
                f"[bold blue]目标:[/bold blue] {goal}",
                title="[bold]GoalDriveClaude[/bold]",
                border_style="blue",
            )
        )
        self.console.print()

    def show_subgoal_progress(self, subgoals: list[dict]) -> None:
        """显示子目标进度"""
        if not subgoals:
            return

        table = Table(show_header=False, box=None)
        table.add_column("Status", style="bold")
        table.add_column("Description")

        status_icons = {
            "done": "[green]✅[/green]",
            "in_progress": "[yellow]🔄[/yellow]",
            "failed": "[red]❌[/red]",
            "verifying": "[cyan]⏳[/cyan]",
            "pending": "[dim]⬚[/dim]",
        }

        for sg in subgoals:
            status = sg.get("status", "pending")
            icon = status_icons.get(status, "⬚")
            desc = sg.get("description", "")
            if status == "in_progress":
                desc = f"[bold]{desc}[/bold]"
            table.add_row(icon, desc)

        self.console.print(Panel(table, title="[bold]子目标进度[/bold]", border_style="cyan"))
        self.console.print()

    def show_iteration_header(self, n: int) -> None:
        """显示迭代轮次"""
        self.console.print(f"[dim]─── 第 {n} 轮迭代 ───[/dim]")

    def show_node_action(self, node: str, msg: str) -> None:
        """显示节点动作"""
        node_icons = {
            "goal_analyzer": "🔍",
            "planner": "🔧",
            "executor": "🛠",
            "evaluator": "📊",
            "verifier": "✅",
            "error_recovery": "🔄",
            "human_input": "👤",
        }
        icon = node_icons.get(node, "•")
        self.console.print(f"{icon} [bold]{node}:[/bold] {msg}")

    def show_tool_call(self, tool: str, result: dict) -> None:
        """显示工具调用结果"""
        success = result.get("success", False)
        status = "[green]成功[/green]" if success else "[red]失败[/red]"
        self.console.print(f"  → [{status}] {tool}")

    def show_verification_report(self, report: str) -> None:
        """显示验证报告"""
        self.console.print()
        self.console.print(
            Panel(
                Markdown(report),
                title="[bold]验证报告[/bold]",
                border_style="green" if "通过" in report else "red",
            )
        )

    def show_error(self, msg: str) -> None:
        """显示错误信息"""
        self.console.print(f"[bold red]错误:[/bold red] {msg}")

    def prompt_user(self, question: str) -> str:
        """询问用户"""
        return Prompt.ask(f"[bold cyan]{question}[/bold cyan]")

    def show_final_summary(self, state: AgentState) -> None:
        """显示最终摘要"""
        self.console.print()

        if state["goal_verified"]:
            self.console.print(
                Panel(
                    "[bold green]🎉 目标已达成！[/bold green]",
                    border_style="green",
                )
            )
        elif state["should_abort"]:
            self.console.print(
                Panel(
                    f"[bold red]⛔ 任务中止: {state['abort_reason']}[/bold red]",
                    border_style="red",
                )
            )
        else:
            self.console.print(
                Panel(
                    "[bold yellow]⏹ 任务结束[/bold yellow]",
                    border_style="yellow",
                )
            )

        self.console.print(f"[dim]总迭代次数: {state['iteration']}[/dim]")
        self.console.print()

    def show_history(self, sessions: list[dict]) -> None:
        """显示会话历史"""
        if not sessions:
            self.console.print("[dim]没有历史会话[/dim]")
            return

        table = Table(title="历史会话")
        table.add_column("会话 ID", style="cyan")
        table.add_column("目标")
        table.add_column("更新时间", style="dim")

        for session in sessions[:10]:  # 只显示最近10个
            session_id = session.get("session_id", "")[:8]
            goal = session.get("goal", "")[:50]
            if len(session.get("goal", "")) > 50:
                goal += "..."
            updated = session.get("updated_at", "")[:19]
            table.add_row(session_id, goal, updated)

        self.console.print(table)
