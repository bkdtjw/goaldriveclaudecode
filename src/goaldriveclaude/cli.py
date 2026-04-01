"""CLI entry point - Interactive REPL interface like Claude Code"""

import signal
import sys
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel

from goaldriveclaude.config import get_config, reload_config
from goaldriveclaude.core.graph import build_graph
from goaldriveclaude.core.state import create_initial_state
from goaldriveclaude.utils.display import Display
from goaldriveclaude.utils.session import SessionManager

console = Console()


def print_welcome():
    """Print welcome message"""
    console.print()
    console.print(
        Panel(
            "[bold blue]GoalDriveClaude[/bold blue] - [dim]Multi-Agent Voting AI Programmer[/dim]\n"
            "\n"
            "[dim]Coordinator splits tasks -> Workers execute -> Supervisors vote -> Global verify[/dim]\n"
            "[dim]Commands: /help, /exit, /history, /resume <id>[/dim]",
            title="Welcome",
            border_style="blue",
        )
    )
    console.print()


def print_help():
    """Print help information"""
    console.print()
    console.print(
        Panel(
            "[bold]Commands:[/bold]\n"
            "\n"
            "  [cyan]/help[/cyan]          Show this help\n"
            "  [cyan]/exit[/cyan] or [cyan]/quit[/cyan]  Exit the program\n"
            "  [cyan]/history[/cyan]       View session history\n"
            "  [cyan]/resume <id>[/cyan]   Resume a session\n"
            "  [cyan]/new[/cyan]           Start a new goal\n"
            "  [cyan]/clear[/cyan]         Clear screen\n"
            "\n"
            "[dim]Example goals:[/dim]\n"
            "  [dim]Create a Flask blog application[/dim]\n"
            "  [dim]Refactor auth middleware with higher quality[/dim]",
            title="Help",
            border_style="cyan",
        )
    )
    console.print()


def run_repl_loop(session_manager: SessionManager, display: Display):
    """REPL main loop"""
    print_welcome()

    config = get_config()
    if not config.anthropic_api_key:
        console.print("[bold red]Error: ANTHROPIC_API_KEY not set[/bold red]")
        console.print("\n[dim]Add to .env file:[/dim]")
        console.print("  ANTHROPIC_API_KEY=your-api-key")
        return

    current_goal = None
    current_session_id = None

    while True:
        try:
            if current_goal:
                prompt_text = f"[dim](current: {current_goal[:30]}...)[/dim]\n> "
            else:
                prompt_text = "> "

            user_input = console.input(prompt_text).strip()

            if not user_input:
                continue

            if user_input.startswith("/"):
                cmd = user_input.lower()

                if cmd in ("/exit", "/quit", "/q"):
                    console.print("\n[dim]Goodbye![/dim]")
                    break

                elif cmd == "/help":
                    print_help()

                elif cmd == "/clear":
                    console.clear()
                    print_welcome()

                elif cmd == "/history":
                    sessions = session_manager.list_sessions()
                    display.show_history(sessions)

                elif cmd.startswith("/resume "):
                    session_id = user_input[8:].strip()
                    state_dict = session_manager.load_state(session_id)
                    if state_dict:
                        current_goal = state_dict.get("original_goal", "")
                        current_session_id = session_id
                        console.print(f"[green]Session resumed: {session_id[:8]}...[/green]")
                        _run_agent_interactive(state_dict, display, session_manager, session_id)
                    else:
                        console.print(f"[red]Session not found: {session_id}[/red]")

                elif cmd == "/new":
                    current_goal = None
                    current_session_id = None
                    console.print("[dim]Reset. Enter a new goal.[/dim]")

                else:
                    console.print(f"[red]Unknown command: {user_input}[/red]")
                    console.print("[dim]Type /help for available commands[/dim]")

            else:
                current_goal = user_input
                current_session_id = session_manager.create_session(current_goal)

                initial_state = create_initial_state(current_goal, max_iterations=50)
                initial_state["session_id"] = current_session_id

                display.show_goal_header(current_goal)
                _run_agent_interactive(initial_state, display, session_manager, current_session_id)

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Interrupted. Saving state...[/yellow]")
            if current_session_id:
                console.print(f"[dim]Session ID: {current_session_id}[/dim]")
            console.print("[dim]Use /resume {} to continue[/dim]".format(current_session_id if current_session_id else "<id>"))
            break

        except EOFError:
            break


def _run_agent_interactive(
    state: dict[str, Any],
    display: Display,
    session_manager: SessionManager,
    session_id: str,
) -> dict[str, Any]:
    """Run agent interactively"""
    config = get_config()
    interrupted = False
    last_state = state

    def handle_interrupt(signum, frame):
        nonlocal interrupted
        interrupted = True
        console.print("\n[yellow]Saving state...[/yellow]")

    original_handler = signal.signal(signal.SIGINT, handle_interrupt)

    try:
        graph = build_graph()

        with console.status("[dim]Thinking...[/dim]", spinner="dots"):
            for event in graph.stream(state, stream_mode="values"):
                last_state = event

                if interrupted:
                    break

                current_iteration = event.get("iteration", 0)
                if current_iteration > 0:
                    display.show_iteration_header(current_iteration)

                phase = event.get("phase", "")
                task_cards = event.get("task_cards", [])

                if phase == "coordinating" and task_cards:
                    display.show_coordinator_output(task_cards)

                if task_cards:
                    display.show_task_progress(task_cards)

                # Show recent tool calls from Worker or Reviewer
                if event.get("tool_results"):
                    last_result = event["tool_results"][-1]
                    tool_name = last_result.get("tool", "")
                    if tool_name:
                        display.show_tool_call(tool_name, last_result)

                # Voting results
                current_idx = event.get("current_task_index", 0)
                if phase == "working" and task_cards and 0 <= current_idx < len(task_cards):
                    tc = task_cards[current_idx]
                    if tc.get("review_votes") and tc.get("status") in ("passed", "rejected"):
                        display.show_voting_results(tc["id"], tc["review_votes"])

                # Global verification
                if phase == "global_reviewing" and event.get("verification_report"):
                    display.show_verification_report(event["verification_report"])

                session_manager.save_state(session_id, event)

                if event.get("should_abort") or event.get("phase") in ("done", "aborted"):
                    break

        display.show_final_summary(last_state)

        if interrupted:
            console.print(f"\n[yellow]Session saved: {session_id}[/yellow]")

    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        if config.log_level == "DEBUG":
            import traceback
            traceback.print_exc()

    finally:
        signal.signal(signal.SIGINT, original_handler)
        session_manager.save_state(session_id, last_state)

    return last_state


@click.group(invoke_without_command=True)
@click.argument("goal", required=False)
@click.option("--resume", type=str, help="Resume session ID")
@click.option("--max-iterations", type=int, default=50, help="Max iterations")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
@click.pass_context
def main(ctx, goal, resume, max_iterations, verbose):
    """GoalDriveClaude - Multi-Agent Voting Programming Agent"""
    reload_config()
    config = get_config()

    if verbose:
        config.log_level = "DEBUG"

    display = Display()
    session_manager = SessionManager()

    if resume:
        state_dict = session_manager.load_state(resume)
        if state_dict:
            display.show_goal_header(state_dict.get("original_goal", ""))
            _run_agent_interactive(state_dict, display, session_manager, resume)
        else:
            console.print(f"[red]Session not found: {resume}[/red]")
        return

    if goal:
        session_id = session_manager.create_session(goal)
        initial_state = create_initial_state(goal, max_iterations)
        initial_state["session_id"] = session_id

        display.show_goal_header(goal)
        _run_agent_interactive(initial_state, display, session_manager, session_id)
        return

    run_repl_loop(session_manager, display)


if __name__ == "__main__":
    main()
