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
            "[bold blue]GoalDriveClaude[/bold blue] - [dim]Goal-driven AI Programming Assistant[/dim]\n"
            "\n"
            "[dim]Enter your goal, and I'll decompose, execute, and verify until completion.[/dim]\n"
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
            "  [dim]Write a Python script to process CSV files[/dim]",
            title="Help",
            border_style="cyan",
        )
    )
    console.print()


def run_repl_loop(session_manager: SessionManager, display: Display):
    """REPL main loop"""
    print_welcome()

    # Check API key
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
            # Show prompt
            if current_goal:
                prompt_text = f"[dim](current: {current_goal[:30]}...)[/dim]\n> "
            else:
                prompt_text = "> "

            user_input = console.input(prompt_text).strip()

            if not user_input:
                continue

            # 如果当前 session 正在等待用户输入，把输入作为回复继续
            if current_session_id and not user_input.startswith("/"):
                saved_state = session_manager.load_state(current_session_id)
                if saved_state and saved_state.get("phase") == "waiting_for_user":
                    # 修复 JSON 反序列化后的 messages 格式（list -> tuple）
                    messages = saved_state.get("messages", [])
                    fixed_messages = []
                    for m in messages:
                        if isinstance(m, list) and len(m) >= 2:
                            fixed_messages.append(tuple(m))
                        else:
                            fixed_messages.append(m)
                    saved_state["messages"] = fixed_messages
                    saved_state["messages"].append(("human", user_input))
                    saved_state["phase"] = "planning"
                    _run_agent_interactive(saved_state, display, session_manager, current_session_id)
                    continue

            # Handle commands
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
                # Process goal
                current_goal = user_input
                current_session_id = session_manager.create_session(current_goal)

                # Create initial state
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
    """Run agent interactively

    Returns:
        Final state
    """
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

                # Show iteration info
                current_iteration = event.get("iteration", 0)
                if current_iteration > 0:
                    display.show_iteration_header(current_iteration)

                # Show subgoal progress
                if event.get("subgoals"):
                    display.show_subgoal_progress(event["subgoals"])

                # Show recent tool calls
                if event.get("tool_results"):
                    last_result = event["tool_results"][-1]
                    tool_name = last_result.get("tool", "")
                    if tool_name and tool_name not in ("planner", "evaluator"):
                        display.show_tool_call(tool_name, last_result)

                # Show verification report
                if event.get("goal_verified") and event.get("verification_report"):
                    display.show_verification_report(event["verification_report"])

                # Save state
                session_manager.save_state(session_id, event)

                # Check if should stop
                if event.get("should_abort") or event.get("phase") in ("done", "aborted"):
                    break

        # Show final summary (or waiting hint)
        if last_state.get("phase") == "waiting_for_user":
            console.print("\n[dim]⏸  已暂停，等待用户输入后继续...[/dim]")
        else:
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
    """GoalDriveClaude - Goal-driven AI Programming Agent

    Usage:
      goaldriveclaude                    # Start interactive mode
      goaldriveclaude "Create Flask app" # Execute goal directly
      goaldriveclaude --resume abc123    # Resume session
    """
    reload_config()
    config = get_config()

    if verbose:
        config.log_level = "DEBUG"

    display = Display()
    session_manager = SessionManager()

    # Resume session
    if resume:
        state_dict = session_manager.load_state(resume)
        if state_dict:
            display.show_goal_header(state_dict.get("original_goal", ""))
            _run_agent_interactive(state_dict, display, session_manager, resume)
        else:
            console.print(f"[red]Session not found: {resume}[/red]")
        return

    # Execute goal directly
    if goal:
        session_id = session_manager.create_session(goal)
        initial_state = create_initial_state(goal, max_iterations)
        initial_state["session_id"] = session_id

        display.show_goal_header(goal)
        _run_agent_interactive(initial_state, display, session_manager, session_id)
        return

    # No arguments: enter REPL interactive mode
    run_repl_loop(session_manager, display)


if __name__ == "__main__":
    main()
