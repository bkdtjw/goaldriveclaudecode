"""显示模块 - Rich 终端 UI"""

from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text


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

    def show_task_progress(self, task_cards: list[dict]) -> None:
        """显示任务卡进度"""
        if not task_cards:
            return

        table = Table(show_header=False, box=None)
        table.add_column("Status", style="bold")
        table.add_column("Task")

        status_icons = {
            "passed": "[green]✅[/green]",
            "done": "[green]✅[/green]",
            "in_progress": "[yellow]🔄[/yellow]",
            "working": "[yellow]🔄[/yellow]",
            "reviewing": "[cyan]⏳[/cyan]",
            "rejected": "[red]❌[/red]",
            "failed": "[red]❌[/red]",
            "pending": "[dim]⬚[/dim]",
        }

        for tc in task_cards:
            status = tc.get("status", "pending")
            icon = status_icons.get(status, "⬚")
            desc = tc.get("description", "")
            if status in ("in_progress", "working"):
                desc = f"[bold]{desc}[/bold]"
            table.add_row(icon, desc)

        self.console.print(Panel(table, title="[bold]任务进度[/bold]", border_style="cyan"))
        self.console.print()

    def show_coordinator_output(self, task_cards: list[dict]) -> None:
        """显示 Coordinator 的任务拆分结果"""
        self.console.print(Panel(f"[bold]Coordinator 已拆分 {len(task_cards)} 个任务[/bold]", border_style="blue"))

    def show_worker_progress(self, task_id: str, message: str = "") -> None:
        """显示 Worker 执行进度"""
        if message:
            self.console.print(f"[dim]Worker [{task_id}]: {message}[/dim]")
        else:
            self.console.print(f"[dim]Worker [{task_id}] 正在执行...[/dim]")

    def show_voting_results(self, task_id: str, votes: dict[str, str]) -> None:
        """显示 Supervisor 投票结果"""
        table = Table(title=f"任务 {task_id} 投票结果")
        table.add_column("Reviewer", style="cyan")
        table.add_column("Vote", style="bold")

        for reviewer, vote in votes.items():
            color = "green" if vote == "pass" else "red"
            table.add_row(reviewer, f"[{color}]{vote.upper()}[/{color}]")

        self.console.print(table)

    def show_global_verification(self, votes: dict[str, str]) -> None:
        """显示全局验证结果"""
        table = Table(title="全局集成验证")
        table.add_column("Reviewer", style="cyan")
        table.add_column("Vote", style="bold")

        for reviewer, vote in votes.items():
            color = "green" if vote == "pass" else "red"
            table.add_row(reviewer, f"[{color}]{vote.upper()}[/{color}]")

        self.console.print(table)

    def show_retry_notice(self, task_id: str, feedback: list[str]) -> None:
        """显示打回重做提示"""
        self.console.print(f"\n[yellow]任务 {task_id} 被打回重做[/yellow]")
        for fb in feedback:
            self.console.print(f"  • {fb[:200]}")

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

    def show_final_summary(self, state: dict) -> None:
        """显示最终摘要"""
        self.console.print()

        phase = state.get("phase", "")
        if phase == "done":
            self.console.print(
                Panel(
                    "[bold green]🎉 目标已达成！[/bold green]",
                    border_style="green",
                )
            )
        elif state.get("should_abort"):
            self.console.print(
                Panel(
                    f"[bold red]⛔ 任务中止: {state.get('abort_reason', '未知原因')}[/bold red]",
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

        self.console.print(f"[dim]总迭代次数: {state.get('iteration', 0)}[/dim]")
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
