"""Trinity interactive session — TUI input loop + deliberation runner.

Manages the interactive prompt loop:
1. Display TUI layout via Rich Live
2. Accept user input (questions or /commands)
3. Run deliberation asynchronously
4. Update TUI in real-time during deliberation via event bus
5. Display results
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel

from trinity.config import TrinityConfig
from trinity.models import DeliberationResult
from trinity.slash_commands import SESSION_ONLY_SETTING_NOTICE, parse_slash_command
from trinity.tui.app import AgentTUIState, TrinityTUI
from trinity.tui.events import TUIEvent, TUIEventBus
from trinity.tui.kitty_compat import install_prompt_toolkit_parser_patch
from trinity.tui.prompt import CUSTOM_OPTION_VALUE, TrinityPromptSession
from trinity.tui.theme import get_theme
from trinity.workflow import (
    ExecutionResult,
    WorkflowEngine,
    WorkflowInputAction,
    WorkflowPersistence,
    WorkflowState,
    classify_blueprint_followup_action,
)

logger = logging.getLogger(__name__)

PLAIN_TUI_COMMAND_HANDLERS: dict[str, str] = {
    "quit": "_cmd_quit",
    "help": "_cmd_help",
    "status": "_cmd_status",
    "context": "_cmd_context",
    "rounds": "_cmd_rounds",
    "agent": "_cmd_agent",
    "history": "_cmd_history",
    "save": "_cmd_save",
    "caveman": "_cmd_caveman",
    "workflow": "_cmd_workflow",
    "questions": "_cmd_questions",
    "answer": "_cmd_answer",
    "decisions": "_cmd_decisions",
    "packages": "_cmd_packages",
    "subtasks": "_cmd_subtasks",
    "report": "_cmd_report",
    "resume": "_cmd_resume",
    "execute": "_cmd_execute",
    "target": "_cmd_target",
}

PLAIN_TUI_COMMANDS_WITH_ARGS = frozenset(
    {
        "rounds",
        "agent",
        "caveman",
        "questions",
        "answer",
        "report",
        "resume",
        "execute",
        "target",
    }
)

if TYPE_CHECKING:
    from trinity.orchestrator import TrinityOrchestrator


# ─── Kitty Keyboard Protocol Management ──────────────────────────────


def _is_kitty_keyboard_capable() -> bool:
    """Return True when the terminal likely supports the Kitty keyboard protocol.

    The Kitty keyboard protocol sends key events as CSI escape sequences
    (``CSI code-point ; modifiers u``).  On terminals such as Ghostty or
    Kitty this is enabled by default.  While the protocol itself works
    fine for Latin input, it can interfere with CJK IME composition
    because prompt_toolkit receives raw key codes for each individual
    keystroke instead of the final composed character.
    """
    if not sys.stdout.isatty():
        return False
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    term = os.environ.get("TERM", "").lower()
    return "ghostty" in term_program or "kitty" in term


def _push_kitty_keyboard_mode() -> None:
    """Disable the Kitty keyboard protocol for CJK IME compatibility.

    Pushes the current keyboard mode onto the terminal's internal stack
    and sets mode 0 (disabled).  This forces the terminal to report key
    events via the legacy xterm protocol, which correctly delivers
    IME-composed text to prompt_toolkit.
    """
    if not _is_kitty_keyboard_capable():
        return
    # CSI < 0 u  →  push current mode and set mode 0 (disabled)
    try:
        fd = sys.stdout.fileno()
        os.write(fd, b"\x1b[<0u")
    except (OSError, ValueError, AttributeError):
        pass


def _pop_kitty_keyboard_mode() -> None:
    """Restore the previously saved Kitty keyboard protocol mode."""
    if not _is_kitty_keyboard_capable():
        return
    # CSI = u  →  pop saved keyboard mode
    try:
        fd = sys.stdout.fileno()
        os.write(fd, b"\x1b[=u")
    except (OSError, ValueError, AttributeError):
        pass


class InteractiveSession:
    """Interactive Trinity session with TUI.

    Runs the main loop:
        - Display TUI
        - Accept input
        - Run deliberation
        - Update display
    """

    def __init__(
        self,
        config: TrinityConfig,
        console: Console | None = None,
    ):
        self.config = config
        self.console = console or Console()
        self.tui = TrinityTUI(config, self.console)
        self.running = False
        self._history_file = config.effective_state_dir / "history" / "session_history.json"
        self._prompt_session = TrinityPromptSession(config.effective_state_dir)
        self.workflow_persistence = WorkflowPersistence(config.effective_state_dir)
        self._startup_archive = self.workflow_persistence.archive_active_session()
        self._question_wizard_active = False
        self.workflow = WorkflowEngine(config.effective_state_dir)
        self.tui.set_workflow_session(self.workflow.session)

    def run(self) -> None:
        """Run the interactive session (blocking).

        This is the main entry point for `trinity` without arguments.
        """
        # Disable Kitty keyboard protocol to prevent CJK IME input issues
        # on Ghostty/Kitty terminals.  See _push_kitty_keyboard_mode().
        install_prompt_toolkit_parser_patch()
        _push_kitty_keyboard_mode()
        try:
            self.running = True
            self._show_welcome()

            while self.running:
                try:
                    user_input = self._get_input()
                    if not user_input or not user_input.strip():
                        continue

                    user_input = user_input.strip()

                    # Command mode
                    if user_input.startswith("/"):
                        self._handle_command(user_input)
                    else:
                        self._handle_user_text(user_input)

                except KeyboardInterrupt:
                    self.console.print("\n[dim]Use /quit to exit.[/dim]")
                except EOFError:
                    break

            self._show_goodbye()
        finally:
            _pop_kitty_keyboard_mode()

    def _show_welcome(self) -> None:
        """Show welcome message with sacred geometry mandala."""
        self.console.print(self.tui.get_welcome_renderable())
        if self._startup_archive:
            self.console.print(
                "[dim]Previous workflow saved to history. Use /resume to restore it.[/dim]"
            )
        self.console.print(
            "[dim]Type a question to start deliberation, or /help for commands.[/dim]\n"
        )

    def _show_goodbye(self) -> None:
        """Show goodbye message."""
        self.console.print("\n[bold cyan]👋 Goodbye from Trinity![/bold cyan]")

    def _get_input(self) -> str:
        """Get user input with prompt_toolkit (arrow keys, history, tab completion)."""
        return self._prompt_session.get_input()

    def _handle_command(self, command: str) -> None:
        """Handle a /command from the user.

        Args:
            command: The command string including the leading /.
        """
        parsed = parse_slash_command(command)
        if parsed is None:
            return
        if parsed.error:
            self.console.print(f"[yellow]{parsed.error}[/yellow]")
            return
        if not parsed.token:
            return
        if parsed.spec is None:
            self.console.print(
                f"[yellow]Unknown command: {parsed.token}. "
                f"Type /help for available commands.[/yellow]"
            )
            return

        command_id = parsed.command_id
        handler_name = PLAIN_TUI_COMMAND_HANDLERS.get(command_id)
        if handler_name is None:
            self.console.print(
                f"[yellow]Command {parsed.spec.name} is not available in the plain TUI.[/yellow]"
            )
            return

        handler = getattr(self, handler_name)
        args = list(parsed.args)
        if command_id in PLAIN_TUI_COMMANDS_WITH_ARGS:
            handler(args)
        else:
            handler()

    def _cmd_quit(self) -> None:
        """Exit the interactive plain TUI loop."""
        self.running = False

    def _cmd_help(self) -> None:
        """Show available command help."""
        self.console.print(self.tui.get_welcome_text())

    def _cmd_status(self) -> None:
        """Show agent status table."""
        from rich.table import Table

        table = Table(title="Agent Status")
        table.add_column("Agent")
        table.add_column("Provider", style="green")
        table.add_column("Enabled")
        table.add_column("State")
        table.add_column("Readiness")
        table.add_column("Context")

        for name, status in self.tui.agents.items():
            spec = self.config.agents.get(name)
            if not spec:
                continue
            theme = get_theme(name)
            enabled = "✅" if spec.enabled else "❌"
            state = status.state.value
            readiness = status.readiness_state
            if status.readiness_reason:
                readiness = f"{readiness}: {status.readiness_reason}"
            ctx = status.context_bar
            table.add_row(
                f"[{theme.color}]{theme.icon} {name}[/{theme.color}]",
                spec.provider.value,
                enabled,
                state,
                readiness,
                ctx,
            )

        self.console.print(table)
        self.console.print(f"[dim]Transport: {self.config.transport_mode}[/dim]")
        self.console.print(
            f"[dim]Synthesis: {self.config.synthesis_mode} "
            f"{self.config.synthesis_agent or 'auto'}/"
            f"{self.config.synthesis_model}[/dim]"
        )
        self._cmd_workflow()

    def _cmd_context(self) -> None:
        """Show current workflow session context."""
        session = self.workflow.session
        if not self._session_has_context():
            self.console.print("[yellow]No current session context.[/yellow]")
            return

        lines = [
            f"[bold]ID[/bold]: {session.id}",
            f"[bold]State[/bold]: {session.state.value}",
            f"[bold]Goal[/bold]: {session.goal or '(none)'}",
            f"[bold]Round[/bold]: {session.current_round}",
            f"[bold]Pending questions[/bold]: {len(session.open_questions)}",
            f"[bold]Decisions[/bold]: {len(session.decisions)}",
            f"[bold]Work packages[/bold]: {len(session.work_packages)}",
            f"[bold]Subtasks[/bold]: {len(session.subtask_results)}",
        ]
        if session.blueprint and session.blueprint.summary:
            lines.extend(["", "[bold]Synthesis[/bold]:", session.blueprint.summary])
        self.console.print(Panel("\n".join(lines), title="Current Session Context"))

    def _session_has_context(self) -> bool:
        """Return whether the plain TUI has meaningful current workflow context."""
        session = self.workflow.session
        return bool(
            session.goal
            or session.current_round
            or session.active_agents
            or session.target_workspace
            or session.blueprint
            or session.open_questions
            or session.decisions
            or session.work_packages
            or session.execution_results
            or session.subtask_results
            or session.review_packages
            or session.review_results
        )

    def _cmd_rounds(self, args: list[str]) -> None:
        """Set max deliberation rounds.

        Usage: /rounds [N]
        """
        if not args:
            self.console.print(
                f"Current max rounds: [cyan]{self.config.max_deliberation_rounds}[/cyan]\n"
                f"[dim]{SESSION_ONLY_SETTING_NOTICE}[/dim]"
            )
            return

        try:
            n = int(args[0])
            if n < 1 or n > 20:
                self.console.print("[yellow]Rounds must be between 1 and 20.[/yellow]")
                return
            self.config.max_deliberation_rounds = n
            self.tui.max_rounds = n
            self.console.print(
                f"[green]Max rounds set to {n} for this session only.[/green]\n"
                f"[dim]{SESSION_ONLY_SETTING_NOTICE}[/dim]"
            )
        except ValueError:
            self.console.print("[yellow]Invalid number.[/yellow]")

    def _cmd_agent(self, args: list[str]) -> None:
        """Enable/disable an agent.

        Usage: /agent <name> on|off
        """
        if len(args) < 2:
            self.console.print("[dim]Usage: /agent <name> on|off[/dim]")
            return

        name, action = args[0].lower(), args[1].lower()
        if name not in self.config.agents:
            self.console.print(f"[yellow]Unknown agent: {name}[/yellow]")
            return

        if action == "on":
            self.config.agents[name].enabled = True
            self.tui.update_agent_status(name, AgentTUIState.IDLE)
            self.console.print(
                f"[green]Agent '{name}' enabled for this session only.[/green]\n"
                f"[dim]{SESSION_ONLY_SETTING_NOTICE}[/dim]"
            )
        elif action == "off":
            self.config.agents[name].enabled = False
            self.tui.update_agent_status(name, AgentTUIState.DISABLED)
            self.console.print(
                f"[yellow]Agent '{name}' disabled for this session only.[/yellow]\n"
                f"[dim]{SESSION_ONLY_SETTING_NOTICE}[/dim]"
            )
        else:
            self.console.print("[dim]Usage: /agent <name> on|off[/dim]")

    def _cmd_history(self) -> None:
        """Show deliberation history."""
        if not self.tui.history:
            self.console.print("[dim]No deliberation history yet.[/dim]")
            return

        from rich.table import Table

        table = Table(title="Deliberation History")
        table.add_column("#", justify="right", style="cyan")
        table.add_column("Prompt", max_width=40)
        table.add_column("Rounds", justify="right")
        table.add_column("Consensus")
        table.add_column("Duration", justify="right")

        for i, entry in enumerate(self.tui.history, 1):
            prompt = entry["prompt"][:40]
            if len(entry["prompt"]) > 40:
                prompt += "..."
            consensus = "✅" if entry["consensus"] else "❌"
            duration = f"{entry['duration']:.1f}s"
            table.add_row(str(i), prompt, str(entry["rounds"]), consensus, duration)

        self.console.print(table)

    def _cmd_save(self) -> None:
        """Save current session results to history file."""
        if not self.tui.last_result:
            self.console.print("[yellow]No results to save yet.[/yellow]")
            return

        self._save_history()
        self.console.print(f"[green]✓ Session history saved to {self._history_file}[/green]")

    def _cmd_caveman(self, args: list[str]) -> None:
        """Toggle or configure caveman compression.

        Usage: /caveman [on|off|lite|full|ultra]
        """
        from trinity.i18n import VALID_CAVEMAN_INTENSITIES

        if not args:
            mode = "on" if self.config.caveman_mode else "off"
            intensity = self.config.caveman_intensity
            self.console.print(
                f"  🦴 Caveman: [cyan]{mode}[/cyan] "
                f"(intensity: [cyan]{intensity}[/cyan])\n"
                f"  [dim]{SESSION_ONLY_SETTING_NOTICE}[/dim]\n"
                f"  [dim]Usage: /caveman [on|off|lite|full|ultra][/dim]"
            )
            return

        action = args[0].lower()

        if action in ("off", "disable"):
            self.config.caveman_mode = False
            self.console.print(
                "[yellow]🦴 Caveman compression disabled for this session only.[/yellow]\n"
                f"[dim]{SESSION_ONLY_SETTING_NOTICE}[/dim]"
            )
        elif action in ("on", "enable"):
            self.config.caveman_mode = True
            self.console.print(
                "[green]🦴 Caveman compression enabled "
                f"({self.config.caveman_intensity}) for this session only.[/green]\n"
                f"[dim]{SESSION_ONLY_SETTING_NOTICE}[/dim]"
            )
        elif action in VALID_CAVEMAN_INTENSITIES:
            self.config.caveman_mode = True
            self.config.caveman_intensity = action
            self.console.print(
                f"[green]🦴 Caveman set to [bold]{action}[/bold] "
                "for this session only.[/green]\n"
                f"[dim]{SESSION_ONLY_SETTING_NOTICE}[/dim]"
            )
        else:
            self.console.print(
                f"[yellow]Unknown option: {action}. Use: on, off, lite, full, ultra[/yellow]"
            )

    def _cmd_workflow(self) -> None:
        """Show current workflow state."""
        session = self.workflow.session
        self.tui.set_workflow_session(session)
        parallel_groups = self.workflow.plan_parallel_groups()
        target_workspace = (
            str(session.target_workspace) if session.target_workspace else "(not set)"
        )
        next_action = ""
        if session.state == WorkflowState.BLUEPRINT_READY and session.blueprint:
            next_action = (
                "\n[bold]Next action[/bold]: /target, /execute, 구현해라, 설계 다듬기, or /workflow"
            )
        recovery = self.workflow.execution_recovery_summary()
        recovery_text = ""
        if recovery is not None:
            recovery_text = (
                "\n[bold]Execution[/bold]: "
                f"{escape(str(recovery.get('state') or 'unknown'))}"
                "\n[bold]Retry candidates[/bold]: "
                f"{escape(', '.join(recovery.get('retry_candidates') or []) or '(none)')}"
                "\n[bold]Recovery actions[/bold]: "
                "/execute retry, /execute mark-interrupted, /execute abort"
            )
        self.console.print(
            Panel.fit(
                f"[bold]ID[/bold]: {session.id}\n"
                f"[bold]State[/bold]: {session.state.value}\n"
                f"[bold]Goal[/bold]: {session.goal or '(none)'}\n"
                f"[bold]Round[/bold]: {session.current_round}\n"
                f"[bold]Active agents[/bold]: {', '.join(session.active_agents) or '(none)'}\n"
                f"[bold]Target workspace[/bold]: {escape(target_workspace)}\n"
                f"[bold]Pending questions[/bold]: {len(session.open_questions)}\n"
                f"[bold]Decisions[/bold]: {len(session.decisions)}\n"
                f"[bold]Work packages[/bold]: {len(session.work_packages)}\n"
                f"[bold]Parallel groups[/bold]: {len(parallel_groups)}\n"
                f"[bold]Subtasks[/bold]: {len(session.subtask_results)}\n"
                f"[bold]Review packages[/bold]: {len(session.review_packages)}"
                f"{recovery_text}"
                f"{next_action}",
                title="Workflow",
                border_style="magenta",
            )
        )

    def _print_execution_recovery(self, message: str = "") -> None:
        recovery = self.workflow.execution_recovery_summary()
        if recovery is None:
            self.console.print("[dim]No interrupted execution recorded.[/dim]")
            return
        lines = []
        if message:
            lines.append(message)
            lines.append("")
        lines.extend(
            [
                f"[bold]Execution[/bold]: {escape(str(recovery.get('state') or 'unknown'))}",
                f"[bold]Run[/bold]: {escape(str(recovery.get('run_id') or '(unknown)'))}",
                f"[bold]Target[/bold]: {escape(str(recovery.get('target_workspace') or '(not set)'))}",
                (
                    "[bold]Running packages at exit[/bold]: "
                    f"{escape(', '.join(recovery.get('running_packages') or []) or '(none)')}"
                ),
                (
                    "[bold]Retry candidates[/bold]: "
                    f"{escape(', '.join(recovery.get('retry_candidates') or []) or '(none)')}"
                ),
                (
                    "[bold]Done packages[/bold]: "
                    f"{escape(', '.join(recovery.get('done_packages') or []) or '(none)')}"
                ),
                f"[bold]Last event[/bold]: {escape(str(recovery.get('last_event') or '(none)'))}",
                "",
                "Provider process reattach is not supported. Use /execute retry, "
                "/execute mark-interrupted, or /execute abort.",
            ]
        )
        self.console.print(
            Panel("\n".join(lines), title="Execution Recovery", border_style="yellow")
        )

    def _cmd_questions(self, args: list[str] | None = None) -> None:
        """Show pending workflow questions."""
        args = args or []
        if any(arg in {"--select", "-s"} for arg in args):
            select_all = any(arg in {"--all", "--wizard", "-a"} for arg in args)
            self._cmd_select_question(select_all=select_all)
            return

        questions = self.workflow.pending_questions
        if not questions:
            self.console.print("[dim]No pending workflow questions.[/dim]")
            return

        self.console.print(self._build_questions_panel(questions))

    def _cmd_answer(self, args: list[str]) -> None:
        """Answer a pending workflow question.

        Usage:
            /answer <question-id|index|next> <answer>
            /answer <option-index>
            /answer --replace <question-id|decision-id> <answer>
        """
        if not args:
            self.console.print("[dim]Usage: /answer <question-id|index|next> <answer>[/dim]")
            return

        active = self.config.active_agents
        if not active:
            self.console.print("[red]No active agents. Use /agent <name> on to enable one.[/red]")
            return

        replace = False
        filtered: list[str] = []
        for arg in args:
            if arg in {"--replace", "-r"}:
                replace = True
            else:
                filtered.append(arg)

        if not filtered:
            self.console.print("[dim]Usage: /answer <question-id|index|next> <answer>[/dim]")
            return

        if len(filtered) == 1 and filtered[0].isdigit():
            action = self.workflow.answer_question_option(
                filtered[0],
                replace=replace,
            )
            self._apply_workflow_action(action)
            return

        if len(filtered) == 1:
            selector = "next"
            answer = filtered[0]
        else:
            selector = filtered[0]
            answer = " ".join(filtered[1:])

        action = self.workflow.answer_question(selector, answer, replace=replace)
        self._apply_workflow_action(action)

    def _cmd_select_question(self, *, select_all: bool = False) -> None:
        """Select one or all pending workflow questions interactively."""
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            self.console.print(
                "[yellow]Interactive selection requires a terminal. "
                "Use /answer <question-id|index|next> <answer> instead.[/yellow]"
            )
            return

        active = self.config.active_agents
        if not active:
            self.console.print("[red]No active agents. Use /agent <name> on to enable one.[/red]")
            return

        previous_wizard_state = self._question_wizard_active
        self._question_wizard_active = True
        try:
            while True:
                questions = self.workflow.pending_questions
                if not questions:
                    self.console.print("[dim]No pending workflow questions.[/dim]")
                    return

                question = questions[0]
                if question.options:
                    selected = self._prompt_session.select_option(
                        title=f"{question.id}",
                        question=question.question,
                        options=question.options,
                        recommended_option=question.recommended_option,
                        allow_custom=True,
                    )
                    if selected is None:
                        self.console.print("[dim]Selection cancelled.[/dim]")
                        return
                    if selected == CUSTOM_OPTION_VALUE:
                        answer = self._prompt_session.get_answer_input(
                            question_id=question.id,
                        ).strip()
                        if not answer:
                            self.console.print("[dim]Selection cancelled.[/dim]")
                            return
                        action = self.workflow.answer_question(question.id, answer)
                    else:
                        action = self.workflow.answer_question_option(
                            str(selected),
                            question_selector=question.id,
                        )
                else:
                    self.console.print(self._build_questions_panel([question], compact=True))
                    answer = self._prompt_session.get_answer_input(
                        question_id=question.id,
                    ).strip()
                    if not answer:
                        self.console.print("[dim]Selection cancelled.[/dim]")
                        return
                    action = self.workflow.answer_question(question.id, answer)

                self._apply_workflow_action(action)
                if action.should_deliberate or action.message or not select_all:
                    return
        finally:
            self._question_wizard_active = previous_wizard_state

    def _cmd_decisions(self) -> None:
        """Show workflow decision ledger."""
        decisions = self.workflow.decisions
        if not decisions:
            self.console.print("[dim]No workflow decisions recorded.[/dim]")
            return

        from rich.table import Table

        table = Table(title="Decisions")
        table.add_column("ID", style="cyan")
        table.add_column("Question")
        table.add_column("Decision")
        table.add_column("By")

        for decision in decisions:
            table.add_row(
                decision.id,
                decision.question_id or "",
                decision.decision,
                decision.decided_by,
            )

        self.console.print(table)

    def _cmd_packages(self) -> None:
        """Show generated workflow work packages."""
        packages = self.workflow.work_packages
        if not packages:
            self.console.print("[dim]No workflow work packages generated.[/dim]")
            return

        from rich.table import Table

        table = Table(title="Work Packages")
        table.add_column("ID", style="cyan")
        table.add_column("Owner")
        table.add_column("Status")
        table.add_column("Exec")
        table.add_column("Deps")
        table.add_column("Files")
        table.add_column("Weight", justify="right")
        table.add_column("Objective")

        for package in packages:
            status = package.status.value if package.requires_execution else "planning_only"
            table.add_row(
                package.id,
                package.owner_agent,
                status,
                "yes" if package.requires_execution else "no",
                ", ".join(package.dependencies) or "-",
                ", ".join(package.expected_files) or "-",
                str(package.estimated_weight),
                package.objective,
            )

        self.console.print(table)

    def _cmd_subtasks(self) -> None:
        """Show provider-internal subtask delegation reports."""
        subtasks = self.workflow.subtask_results
        if not subtasks:
            self.console.print("[dim]No delegated subtask reports recorded.[/dim]")
            return

        from rich.table import Table

        table = Table(title="Subtasks")
        table.add_column("ID", style="cyan")
        table.add_column("Package")
        table.add_column("Parent")
        table.add_column("Delegated To")
        table.add_column("Status")
        table.add_column("Summary")

        for subtask in subtasks:
            table.add_row(
                subtask.id,
                subtask.parent_package_id,
                subtask.parent_agent,
                subtask.delegated_to,
                subtask.status.value,
                subtask.result_summary,
            )

        self.console.print(table)

    def _cmd_report(self, args: list[str]) -> None:
        """협의 결과를 개괄 Report 형식으로 표시.

        Usage:
            /report          — TUI에 Rich 형식으로 표시
            /report save     — Markdown 파일로 저장
        """
        from trinity.tui.report import DeliberationReportBuilder

        result = self.tui.last_result
        session = self.workflow.session
        if not session.goal and result is None:
            self.console.print(
                "[yellow]아직 협의 결과가 없습니다. 먼저 질문을 입력해 협의를 시작하세요.[/yellow]"
            )
            return

        builder = DeliberationReportBuilder(session, result)
        report = builder.build()

        save_requested = args and args[0].lower() in ("save", "s")
        if save_requested:
            self._save_report_markdown(report)
        else:
            self.console.print(report.render())
            if self.workflow.execution_recovery_summary() is not None:
                self._print_execution_recovery()
            self.console.print("\n[dim]/report save 로 Markdown 파일로 저장할 수 있습니다.[/dim]")

    def _save_report_markdown(self, report) -> None:
        """Report를 Markdown 파일로 저장."""
        report_dir = self.config.effective_state_dir / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"report-{report.meta.session_id[:8]}-{timestamp}.md"
        filepath = report_dir / filename
        filepath.write_text(report.to_markdown(), encoding="utf-8")
        self.console.print(f"[green]📋 Report 저장 완료: {filepath}[/green]")

    def _cmd_resume(self, args: list[str]) -> None:
        """Resume an archived workflow session.

        Usage:
            /resume
            /resume latest
            /resume <index|workflow-id>
        """
        archives = self.workflow_persistence.list_archives()
        if not archives:
            self.console.print("[dim]No saved workflow sessions to resume.[/dim]")
            return

        selector = args[0] if args else ""
        if not selector:
            if sys.stdin.isatty() and sys.stdout.isatty():
                labels = [self._archive_label(archive) for archive in archives]
                selected = self._prompt_session.select_option(
                    title="Resume Workflow",
                    question="Select a saved workflow session.",
                    options=labels,
                )
                if selected is None:
                    self.console.print("[dim]Resume cancelled.[/dim]")
                    return
                selector = selected
            else:
                self._print_resume_table(archives)
                self.console.print("[dim]Usage: /resume <index|latest|workflow-id>[/dim]")
                return

        archive = self._resolve_archive(archives, selector)
        if archive is None:
            self.console.print(f"[yellow]No matching workflow session: {selector}[/yellow]")
            return

        archived_current = self.workflow_persistence.archive_active_session()
        self.workflow_persistence.restore_archive(archive)
        self.workflow = WorkflowEngine(self.config.effective_state_dir)
        self.tui.set_workflow_session(self.workflow.session)

        if archived_current:
            self.console.print(
                f"[dim]Current workflow saved as {archived_current.session.id}.[/dim]"
            )
        self.console.print(f"[green]Resumed workflow {self.workflow.session.id}.[/green]")
        self._cmd_workflow()

    def _cmd_execute(self, args: list[str]) -> None:
        """Execute the current approved blueprint work packages."""
        instruction = " ".join(args).strip()
        normalized = instruction.lower()
        if normalized in {"retry", "retry-interrupted", "recovery retry"}:
            summary = self.workflow.retry_interrupted_execution()
            if summary is None:
                self.console.print("[yellow]No interrupted execution to retry.[/yellow]")
                return
            self.console.print("[green]Retrying interrupted execution packages.[/green]")
            self._run_enabled_execution()
            self._cmd_workflow()
            return
        if normalized in {"mark", "mark-interrupted", "mark interrupted"}:
            if self.workflow.mark_interrupted_execution() is None:
                self.console.print("[yellow]No interrupted execution to mark.[/yellow]")
                return
            self._print_execution_recovery("Execution marked as interrupted.")
            self._cmd_workflow()
            return
        if normalized in {"abort", "abort-execution", "abort execution"}:
            if self.workflow.abort_interrupted_execution() is None:
                self.console.print("[yellow]No interrupted execution to abort.[/yellow]")
                return
            self._print_execution_recovery("Interrupted execution aborted.")
            self._cmd_workflow()
            return
        recovery = self.workflow.detect_interrupted_execution(worker_running=False)
        if recovery is not None and str(recovery.get("state", "")) == "interrupted":
            self._print_execution_recovery(
                "Previous execution was interrupted. Review running packages before retrying."
            )
            return
        self._execute_current_blueprint(instruction=instruction)

    def _cmd_target(self, args: list[str]) -> None:
        """Show, set, or clear the implementation target workspace."""
        if not args:
            current = self.workflow.session.target_workspace
            default = self._default_target_workspace()
            self.console.print(
                Panel.fit(
                    f"[bold]Current[/bold]: {current or '(not set)'}\n"
                    f"[bold]Default[/bold]: {default}\n\n"
                    "Usage: /target <path> or /target clear",
                    title="Target Workspace",
                    border_style="cyan",
                )
            )
            return

        action = args[0].strip().lower()
        if action in {"clear", "reset", "none"}:
            self.workflow.clear_target_workspace()
            self.tui.set_workflow_session(self.workflow.session)
            self.console.print("[yellow]Target workspace cleared.[/yellow]")
            return

        path = self._resolve_user_path(" ".join(args))
        self._set_target_workspace(path, create=True, require_existing=False)

    def _print_resume_table(self, archives) -> None:
        """Print archived workflow sessions for manual selection."""
        from rich.table import Table

        table = Table(title="Saved Workflow Sessions")
        table.add_column("#", justify="right", style="cyan")
        table.add_column("ID")
        table.add_column("State")
        table.add_column("Updated")
        table.add_column("Goal")

        for index, archive in enumerate(archives, 1):
            session = archive.session
            table.add_row(
                str(index),
                session.id,
                session.state.value,
                self._format_timestamp(session.updated_at),
                self._short_goal(session.goal),
            )

        self.console.print(table)

    def _resolve_archive(self, archives, selector: str):
        """Resolve a resume selector to one archive."""
        normalized = selector.strip().lower()
        if normalized in {"latest", "last", "newest"}:
            return archives[0]
        if normalized.isdigit():
            index = int(normalized) - 1
            if 0 <= index < len(archives):
                return archives[index]
            return None
        return next(
            (archive for archive in archives if archive.session.id.lower() == normalized),
            None,
        )

    def _archive_label(self, archive) -> str:
        """Build a concise label for interactive resume selection."""
        session = archive.session
        return (
            f"{session.id} · {session.state.value} · "
            f"{self._format_timestamp(session.updated_at)} · "
            f"{self._short_goal(session.goal)}"
        )

    @staticmethod
    def _format_timestamp(
        timestamp: float,
        fmt: str = "%Y-%m-%d %H:%M",
    ) -> str:
        """Format a persisted Unix timestamp for display."""
        from trinity.tui.formatting import format_timestamp

        return format_timestamp(timestamp, fmt)

    @staticmethod
    def _short_goal(goal: str, limit: int = 60) -> str:
        """Return a compact single-line workflow goal."""
        text = " ".join((goal or "(none)").split())
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    # ─── Deliberation ──────────────────────────────────────────────────

    def _handle_user_text(self, text: str) -> None:
        """Route normal input through workflow state before deliberating."""
        active = self.config.active_agents
        if not active:
            self.console.print("[red]No active agents. Use /agent <name> on to enable one.[/red]")
            return

        if self.workflow.state == WorkflowState.BLUEPRINT_READY and self.workflow.work_packages:
            self._handle_blueprint_ready_text(text, list(active.keys()))
            return

        action = self.workflow.handle_user_input(text, list(active.keys()))
        self._apply_workflow_action(action)

    def _apply_workflow_action(self, action: WorkflowInputAction) -> None:
        """Apply a routed workflow action to the TUI and deliberation runner."""
        self.tui.set_workflow_session(self.workflow.session)

        if action.message:
            self.console.print(f"[yellow]{action.message}[/yellow]")

        if action.decision_record:
            verb = "Updated" if action.replaced_decision else "Recorded"
            self.console.print(f"[green]{verb} decision {action.decision_record.id}.[/green]")

        if action.should_deliberate:
            self._run_deliberation(action.prompt)
        elif action.execution_requested:
            self._run_enabled_execution()
        elif (
            self.workflow.state == WorkflowState.NEEDS_USER_DECISION
            and not self._question_wizard_active
        ):
            self._print_decision_required()

    def _print_decision_required(self) -> None:
        """Print the next actionable workflow decision hint."""
        questions = self.workflow.pending_questions
        if not questions:
            return
        self.console.print(self._build_questions_panel(questions, compact=True))

    def _build_questions_panel(self, questions, *, compact: bool = False) -> Panel:
        """Build an actionable pending-question panel."""
        lines: list[str] = []
        shown = questions[:1] if compact else questions
        for index, question in enumerate(shown, 1):
            lines.append(
                f"[bold cyan][{index}][/bold cyan] "
                f"[cyan]{escape(question.id)}[/cyan] · {escape(question.question)}"
            )
            if question.recommended_option:
                lines.append(f"    추천: {escape(question.recommended_option)}")
            if question.options:
                for option_index, option in enumerate(question.options, 1):
                    suffix = (
                        " [green](recommended)[/green]"
                        if option == question.recommended_option
                        else ""
                    )
                    lines.append(f"    {option_index}. {escape(option)}{suffix}")
                lines.append(
                    f"    답변: 직접 입력 또는 /answer {index} <값> 또는 /answer {question.id} <값>"
                )
                if index == 1:
                    lines.append("    선택 UI: /questions --select")
                    lines.append("    직접 답변: 프롬프트에 답변을 그대로 입력")
                    if len(questions) > 1:
                        lines.append("    전체 선택 UI: /questions --select --all")
            else:
                lines.append(
                    f"    답변: 직접 입력 또는 /answer {index} <값> 또는 /answer {question.id} <값>"
                )
            if question.rationale:
                lines.append(f"    이유: {escape(question.rationale)}")
            if not compact:
                lines.append("")

        if compact and len(questions) > 1:
            remaining = len(questions) - 1
            lines.append(f"\n남은 질문 {remaining}개는 /questions 로 확인하세요.")

        title = "Decision Required" if compact else "Pending Questions"
        return Panel.fit(
            "\n".join(lines).rstrip(),
            title=title,
            border_style="yellow",
        )

    def _run_deliberation(self, prompt: str) -> None:
        """Run a deliberation on the user's prompt with real-time TUI updates.

        Uses Rich Live to show agent status and round progress
        while the deliberation is running.

        Args:
            prompt: The user's question/topic.
        """
        from trinity.orchestrator import TrinityOrchestrator

        active = self.config.active_agents
        if not active:
            self.console.print("[red]No active agents. Use /agent <name> on to enable one.[/red]")
            return

        use_tmux = self._uses_tmux_transport()
        if use_tmux and not self._has_tmux():
            self.console.print(
                "[red]transport_mode is 'tmux', but tmux is not installed or not on PATH.[/red]"
            )
            return
        if use_tmux:
            self.console.print(
                "[yellow]Using legacy tmux agent transport. "
                "One-shot remains the default transport.[/yellow]"
            )

        mode_str = self._transport_mode_label()
        self.console.print(
            Panel.fit(
                f"[bold]{prompt}[/bold]\n\n"
                f"Agents: {', '.join(active.keys())}\n"
                f"Max rounds: {self.config.max_deliberation_rounds}\n"
                f"Mode: {mode_str}",
                title="🧠 Deliberation Starting",
                border_style="cyan",
            )
        )

        # Create orchestrator
        orchestrator = TrinityOrchestrator(self.config, interactive=use_tmux)

        # Reset TUI state for new deliberation
        self.tui.reset_agents()

        try:
            # Run with real-time Live display
            result = self._run_with_live(orchestrator, prompt)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Deliberation interrupted.[/yellow]")
            self.tui.reset_agents()
            return
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            logger.exception("Deliberation failed")
            self.tui.reset_agents()
            return

        # Guard: result may be None if deliberation was interrupted or failed silently
        if result is None:
            self.console.print("[yellow]Deliberation did not produce a result.[/yellow]")
            self.tui.reset_agents()
            return

        # Update TUI with result
        self.tui.set_result(result)
        self.workflow.mark_deliberation_result(result)
        self.tui.set_workflow_session(self.workflow.session)

        self._maybe_run_execution(orchestrator)

        # Display results BEFORE resetting (agents store full_response)
        self._display_result(result)

        self._offer_pending_questions()

        # Now reset agent states for next deliberation
        self.tui.reset_agents()

    def _handle_blueprint_ready_text(
        self,
        text: str,
        active_agents: list[str],
    ) -> None:
        """Handle session-like follow-up text after a blueprint is ready."""
        action = self._select_blueprint_followup_action(text)
        if action == "cancel":
            self.console.print("[dim]Workflow action cancelled.[/dim]")
            return
        if action == "execute":
            self._execute_current_blueprint(instruction=text)
            return
        if action == "new":
            self._archive_current_workflow_for_new_goal()
            workflow_action = self.workflow.start(text, active_agents)
            self._apply_workflow_action(workflow_action)
            return

        workflow_action = self.workflow.continue_from_blueprint(text, active_agents)
        self._apply_workflow_action(workflow_action)

    def _select_blueprint_followup_action(self, text: str) -> str:
        """Return execute, continue, new, or cancel for blueprint-ready text."""
        classified = classify_blueprint_followup_action(text)
        if classified is not None:
            return classified

        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return "continue"

        selected = self._prompt_session.select_option(
            title="Workflow",
            question=(
                f"현재 승인된 설계가 있습니다. 방금 입력한 내용을 어떻게 처리할까요?\n\n{text}"
            ),
            options=[
                "이 설계도로 구현 시작",
                "이 설계를 더 다듬기",
                "새 workflow 시작",
                "취소",
            ],
            recommended_option="이 설계도로 구현 시작",
        )
        return {
            "1": "execute",
            "2": "continue",
            "3": "new",
            "4": "cancel",
        }.get(str(selected), "cancel")

    def _archive_current_workflow_for_new_goal(self) -> None:
        """Archive the current workflow before intentionally starting a new goal."""
        archived = self.workflow_persistence.archive_active_session(force=True)
        self.workflow = WorkflowEngine(self.config.effective_state_dir)
        self.tui.set_workflow_session(self.workflow.session)
        if archived:
            self.console.print(f"[dim]Current workflow saved as {archived.session.id}.[/dim]")

    def _offer_pending_questions(self) -> None:
        """Prompt for synthesized user decisions after a deliberation round."""
        if self.workflow.state != WorkflowState.NEEDS_USER_DECISION:
            return
        if not self.workflow.pending_questions:
            return

        if sys.stdin.isatty() and sys.stdout.isatty():
            self._cmd_select_question(select_all=True)
        else:
            self.console.print(
                self._build_questions_panel(
                    self.workflow.pending_questions,
                    compact=True,
                )
            )
            self.console.print(
                "[dim]Type an answer at the prompt, or use /questions --select.[/dim]"
            )

    def _ensure_target_workspace_for_execution(self) -> bool:
        """Ensure implementation has an explicit writable target workspace."""
        target = self.workflow.session.target_workspace
        if target is not None:
            return self._validate_existing_target_workspace(target)

        default = self._default_target_workspace()
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            self.console.print(
                Panel.fit(
                    "Implementation requires a target workspace before provider "
                    "workspace-write can start.\n\n"
                    f"Recommended default:\n{default}\n\n"
                    "Use /target <path>, then run /execute again.",
                    title="Target Workspace Required",
                    border_style="yellow",
                )
            )
            return False

        selected = self._prompt_session.select_option(
            title="Target Workspace",
            question="구현 산출물을 어느 경로에 만들까요?",
            options=[
                f"새 프로젝트 디렉터리 만들기: {default}",
                "기존 프로젝트 디렉터리 사용",
                f"현재 경로 사용: {Path.cwd().resolve()}",
                "구현 취소",
            ],
            recommended_option=f"새 프로젝트 디렉터리 만들기: {default}",
        )
        if selected is None or selected == "4":
            self.console.print("[dim]Implementation cancelled.[/dim]")
            return False
        if selected == "1":
            return self._set_target_workspace(
                default,
                create=True,
                require_existing=False,
            )
        if selected == "2":
            value = self._prompt_session.get_path_input(
                label="target workspace",
            ).strip()
            if not value:
                self.console.print("[dim]Implementation cancelled.[/dim]")
                return False
            return self._set_target_workspace(
                self._resolve_user_path(value),
                create=False,
                require_existing=True,
            )
        if selected == "3":
            return self._set_target_workspace(
                Path.cwd(),
                create=False,
                require_existing=True,
            )
        return False

    def _validate_existing_target_workspace(self, target: Path) -> bool:
        """Validate a persisted target workspace before execution resumes."""
        resolved = target.expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            self.console.print(f"[yellow]Target workspace does not exist: {resolved}[/yellow]")
            return False
        if (
            self._is_inside_control_repo(resolved)
            and not self.workflow.session.control_repo_target_confirmed
        ):
            return self._confirm_and_store_control_repo_target(resolved)
        return True

    def _set_target_workspace(
        self,
        path: Path,
        *,
        create: bool,
        require_existing: bool,
    ) -> bool:
        """Persist a target workspace path after validation."""
        resolved = path.expanduser().resolve()
        if require_existing and (not resolved.exists() or not resolved.is_dir()):
            self.console.print(f"[yellow]Target workspace does not exist: {resolved}[/yellow]")
            return False
        if create:
            resolved.mkdir(parents=True, exist_ok=True)
        if not resolved.is_dir():
            self.console.print(f"[yellow]Target workspace is not a directory: {resolved}[/yellow]")
            return False

        control_repo_confirmed = False
        if self._is_inside_control_repo(resolved):
            control_repo_confirmed = self._confirm_control_repo_target(resolved)
            if not control_repo_confirmed:
                self.console.print("[dim]Target workspace selection cancelled.[/dim]")
                return False

        self.workflow.set_target_workspace(
            resolved,
            control_repo_confirmed=control_repo_confirmed,
        )
        self.tui.set_workflow_session(self.workflow.session)
        self.console.print(f"[green]Target workspace set to {resolved}[/green]")
        return True

    def _confirm_and_store_control_repo_target(self, path: Path) -> bool:
        """Ask for confirmation when a persisted target points at the control repo."""
        if not self._confirm_control_repo_target(path):
            return False
        self.workflow.set_target_workspace(path, control_repo_confirmed=True)
        self.tui.set_workflow_session(self.workflow.session)
        return True

    def _confirm_control_repo_target(self, path: Path) -> bool:
        """Return whether the user explicitly accepts writing inside control repo."""
        message = (
            "현재 경로는 Trinity 제어 저장소 내부입니다. 여기에 사용자 "
            "프로젝트 파일을 만들면 Trinity 코드와 산출물이 섞입니다. "
            "그래도 계속할까요?\n\n"
            f"{path}"
        )
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            self.console.print(
                Panel.fit(
                    message + "\n\nUse a target workspace outside the Trinity repo.",
                    title="Target Workspace Warning",
                    border_style="red",
                )
            )
            return False

        selected = self._prompt_session.select_option(
            title="Target Workspace Warning",
            question=message,
            options=["취소", "그래도 현재 경로 사용"],
            recommended_option="취소",
        )
        return selected == "2"

    def _default_target_workspace(self) -> Path:
        """Return the recommended new project path outside the control repo."""
        session = self.workflow.session
        title = (
            session.blueprint.title
            if session.blueprint and session.blueprint.title.strip()
            else session.goal
        )
        slug = self._slugify_workspace_name(title) or "trinity-project"
        return self.config.project_dir.resolve().parent / slug

    @staticmethod
    def _slugify_workspace_name(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9가-힣]+", "-", value.lower()).strip("-")
        normalized = re.sub(r"-{2,}", "-", normalized)
        return normalized[:80].strip("-")

    def _resolve_user_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        return self.config.project_dir / path

    def _is_inside_control_repo(self, path: Path) -> bool:
        control_repo = self.config.project_dir.resolve()
        resolved = path.expanduser().resolve()
        return resolved == control_repo or control_repo in resolved.parents

    def _run_with_live(
        self,
        orchestrator: "TrinityOrchestrator",
        prompt: str,
    ) -> DeliberationResult:
        """Run deliberation with Rich Live real-time display via event bus.

        Creates a TUIEventBus, passes it to the orchestrator for event
        emission, and polls for events during the Live refresh loop to
        drive real-time TUI state updates.

        Exits on DELIBERATION_DONE or thread completion. Agent/provider
        timeouts are enforced inside the deliberation protocol.

        Args:
            orchestrator: The orchestrator to run.
            prompt: The user's prompt.

        Returns:
            The deliberation result.
        """
        import threading

        from trinity.tui.events import TUIEventType

        bus = TUIEventBus()
        orchestrator.set_event_bus(bus)

        result_holder: list[DeliberationResult | None] = [None]
        error_holder: list[Exception | None] = [None]

        def _run_async():
            """Run the async deliberation in a background thread."""
            try:
                result = asyncio.run(orchestrator.ask(prompt))
                result_holder[0] = result
            except Exception as e:
                error_holder[0] = e

        # Start deliberation in background thread
        thread = threading.Thread(target=_run_async, daemon=True)
        thread.start()

        done_received = False

        # Show live TUI while deliberation runs
        try:
            with Live(
                self.tui.build_layout(),
                console=self.console,
                refresh_per_second=4,
                transient=True,
            ) as live:
                while thread.is_alive():
                    thread.join(timeout=0.25)

                    # Consume all pending events and update TUI state
                    for event in bus.poll():
                        self.tui.consume_event(event)
                        # Early exit when deliberation is done
                        if event.type == TUIEventType.DELIBERATION_DONE:
                            done_received = True

                    # If DELIBERATION_DONE received, drain remaining events and exit
                    if done_received:
                        for event in bus.poll():
                            self.tui.consume_event(event)
                        live.update(self.tui.build_layout())
                        # Give the thread a moment to finish cleanup
                        thread.join(timeout=2.0)
                        break

                    live.update(self.tui.build_layout())

                # Drain any remaining events after thread completes
                for event in bus.poll():
                    self.tui.consume_event(event)
                live.update(self.tui.build_layout())
        except KeyboardInterrupt:
            raise

        if error_holder[0]:
            raise error_holder[0]

        result = result_holder[0]
        if result is None:
            logger.warning("Deliberation thread completed but produced no result")

        return result  # type: ignore[return-value]

    # ─── Execution ─────────────────────────────────────────────────────

    def _maybe_run_execution(self, orchestrator: "TrinityOrchestrator") -> None:
        """Run generated executable work packages after blueprint consensus."""
        if self.workflow.state != WorkflowState.BLUEPRINT_READY:
            return
        if not self.workflow.has_pending_execution:
            return
        if not self._ensure_target_workspace_for_execution():
            return

        orchestrator = self._execution_orchestrator(orchestrator)
        target_workspace = self.workflow.session.target_workspace

        self.workflow.begin_execution()
        self.tui.set_workflow_session(self.workflow.session)
        self.console.print(
            Panel.fit(
                f"[bold]Target workspace[/bold]\n{target_workspace}",
                title="Execution Starting",
                border_style="green",
            )
        )

        try:
            results = self._run_execution_with_live(orchestrator)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Execution interrupted.[/yellow]")
            return
        except Exception as exc:
            self.console.print(f"[red]Execution error: {exc}[/red]")
            logger.exception("Execution failed")
            return

        self.workflow.record_execution_results(results, emit_events=False)
        self.tui.set_workflow_session(self.workflow.session)

    def _execute_current_blueprint(self, *, instruction: str = "") -> None:
        """Mark current blueprint executable and run pending execution packages."""
        if self.workflow.state != WorkflowState.BLUEPRINT_READY:
            self.console.print(
                "[yellow]No blueprint is ready. Finish deliberation before execution.[/yellow]"
            )
            return
        if not self._ensure_target_workspace_for_execution():
            return

        action = self.workflow.enable_execution_for_current_blueprint(instruction)
        self.tui.set_workflow_session(self.workflow.session)
        if action.message:
            self.console.print(f"[yellow]{action.message}[/yellow]")
        if action.target_workspace_required:
            return
        if not self.workflow.has_pending_execution:
            self._cmd_workflow()
            return

        self._run_enabled_execution()
        self._cmd_workflow()

    def _run_enabled_execution(self) -> None:
        """Run already-enabled executable work packages for the current blueprint."""
        if not self.workflow.has_pending_execution:
            self._cmd_workflow()
            return
        if not self._ensure_target_workspace_for_execution():
            return

        from trinity.orchestrator import TrinityOrchestrator

        use_tmux = self._uses_tmux_transport()
        if use_tmux and not self._has_tmux():
            self.console.print(
                "[red]transport_mode is 'tmux', but tmux is not installed or not on PATH.[/red]"
            )
            return
        if use_tmux:
            self.console.print(
                "[yellow]Using legacy tmux agent transport. "
                "One-shot remains the default transport.[/yellow]"
            )

        orchestrator = TrinityOrchestrator(
            self.config,
            interactive=use_tmux,
            target_workspace=self.workflow.session.target_workspace,
            allow_control_repo_writes=(self.workflow.session.control_repo_target_confirmed),
        )
        self._maybe_run_execution(orchestrator)

    def _execution_orchestrator(
        self,
        orchestrator: "TrinityOrchestrator",
    ) -> "TrinityOrchestrator":
        """Return an orchestrator whose providers launch in target workspace."""
        target = self.workflow.session.target_workspace
        if (
            target is not None
            and getattr(orchestrator, "target_workspace", None) == target.resolve()
            and getattr(orchestrator, "allow_control_repo_writes", False)
            == self.workflow.session.control_repo_target_confirmed
        ):
            return orchestrator

        from trinity.orchestrator import TrinityOrchestrator

        return TrinityOrchestrator(
            self.config,
            interactive=self._uses_tmux_transport(),
            target_workspace=target,
            allow_control_repo_writes=(self.workflow.session.control_repo_target_confirmed),
        )

    def _run_execution_with_live(
        self,
        orchestrator: "TrinityOrchestrator",
    ) -> list[ExecutionResult]:
        """Run work package execution while consuming TUI events."""
        import threading

        from trinity.tui.events import TUIEventType

        bus = TUIEventBus()
        orchestrator.set_event_bus(bus)

        result_holder: list[list[ExecutionResult] | None] = [None]
        error_holder: list[Exception | None] = [None]
        progress_lock = threading.Lock()
        progress_results: list[ExecutionResult] = []

        def _record_progress(result: ExecutionResult) -> None:
            with progress_lock:
                progress_results.append(result)

        def _drain_progress() -> None:
            with progress_lock:
                results = list(progress_results)
                progress_results.clear()
            if not results:
                return
            self.workflow.record_execution_results(
                results,
                finalize=False,
                emit_events=False,
            )
            self.tui.set_workflow_session(self.workflow.session)

        def _event_occurred_at(event: TUIEvent) -> float | None:
            value = event.data.get("occurred_at")
            try:
                return float(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        def _event_batches(event: TUIEvent) -> list[list[str]]:
            batches = event.data.get("batches", [])
            if not isinstance(batches, list):
                return []
            normalized: list[list[str]] = []
            for batch in batches:
                if isinstance(batch, list):
                    normalized.append([str(item) for item in batch if str(item).strip()])
            return normalized

        def _event_notices(event: TUIEvent) -> list[dict[str, object]]:
            notices = event.data.get("notices", [])
            if not isinstance(notices, list):
                return []
            return [item for item in notices if isinstance(item, dict)]

        def _consume_events() -> bool:
            execution_done = False
            for event in bus.poll():
                self.tui.consume_event(event)
                if event.type == TUIEventType.EXECUTION_BATCH_PLANNED:
                    self.workflow.record_execution_batch_planned(
                        _event_batches(event),
                        _event_notices(event),
                        _event_occurred_at(event),
                    )
                    self.tui.set_workflow_session(self.workflow.session)
                if event.type == TUIEventType.WORK_PACKAGE_STARTED:
                    self.workflow.record_work_package_started(
                        str(event.data.get("package_id") or ""),
                        str(event.data.get("agent") or ""),
                        _event_occurred_at(event),
                    )
                    self.tui.set_workflow_session(self.workflow.session)
                if event.type == TUIEventType.WORK_PACKAGE_COMPLETED:
                    self.workflow.record_work_package_completed(
                        str(event.data.get("package_id") or ""),
                        str(event.data.get("agent") or ""),
                        str(event.data.get("status") or ""),
                        str(event.data.get("summary") or ""),
                        _event_occurred_at(event),
                    )
                    self.tui.set_workflow_session(self.workflow.session)
                if event.type == TUIEventType.EXECUTION_DONE:
                    execution_done = True
            _drain_progress()
            return execution_done

        def _run_async():
            try:
                result_holder[0] = asyncio.run(
                    orchestrator.execute_work_packages(
                        self.workflow.session.work_packages,
                        decisions=self.workflow.decisions,
                        result_callback=_record_progress,
                    )
                )
            except Exception as exc:
                error_holder[0] = exc

        thread = threading.Thread(target=_run_async, daemon=True)
        thread.start()

        try:
            with Live(
                self.tui.build_layout(),
                console=self.console,
                refresh_per_second=4,
                transient=True,
            ) as live:
                while thread.is_alive():
                    thread.join(timeout=0.25)
                    _consume_events()
                    live.update(self.tui.build_layout())

                _consume_events()
                live.update(self.tui.build_layout())
        except KeyboardInterrupt:
            raise

        if error_holder[0]:
            raise error_holder[0]
        return result_holder[0] or []

    # ─── Display ────────────────────────────────────────────────────────

    def _display_result(self, result: DeliberationResult) -> None:
        """Display deliberation result with agent opinions."""
        from rich.markdown import Markdown

        if result.has_consensus:
            self.console.print(
                Panel.fit(
                    f"[green bold]{result.consensus.summary}[/green bold]",
                    title=f"✅ Consensus (Round {result.rounds_completed})",
                    border_style="green",
                )
            )
        else:
            summary = (
                result.consensus.summary
                if result.consensus and result.consensus.summary
                else "No consensus reached."
            )
            self.console.print(
                Panel.fit(
                    f"[yellow]{summary}[/yellow]",
                    title=f"Deliberation Result ({result.rounds_completed} rounds)",
                    border_style="yellow",
                )
            )

        # Show each agent's final opinion
        if self.tui.agents:
            self.console.print()
            for name, status in self.tui.agents.items():
                if status.state == AgentTUIState.DISABLED:
                    continue
                theme = get_theme(name)
                response = status.full_response
                if response:
                    self.console.print(
                        f"  [{theme.color}]{theme.icon} {name}[/{theme.color}] "
                        f"[dim]({theme.role_label})[/dim]"
                    )
                    self.console.print(
                        Panel(
                            Markdown(response[:2000]),
                            border_style=theme.border_style,
                            padding=(0, 1),
                        )
                    )

        if result.tasks:
            self.console.print("\n[bold]🎯 작업 분배[/bold]")
            for task in sorted(result.tasks, key=lambda t: -t.priority):
                theme = get_theme(task.agent_name)
                desc = task.task_description[:120]
                if len(task.task_description) > 120:
                    desc += "..."
                self.console.print(
                    f"  [{theme.color}]{theme.icon} {task.agent_name}[/{theme.color}]: {desc}"
                )

        if self.workflow.work_packages:
            self.console.print("\n[bold]📦 Work Packages[/bold]")
            for package in self.workflow.work_packages:
                status = package.status.value if package.requires_execution else "planning_only"
                self.console.print(
                    f"  [cyan]{package.id}[/cyan] {package.owner_agent}: {package.title} ({status})"
                )

        if self.workflow.execution_results:
            self.console.print("\n[bold]🛠 Task Results[/bold]")
            for execution_result in self.workflow.execution_results:
                summary = execution_result.summary[:120]
                if len(execution_result.summary) > 120:
                    summary += "..."
                self.console.print(
                    f"  [cyan]{execution_result.package_id}[/cyan] "
                    f"{execution_result.agent_name}: "
                    f"{execution_result.status.value} - {summary}"
                )

        if self.workflow.subtask_results:
            self.console.print("\n[bold]Delegated Subtasks[/bold]")
            for subtask in self.workflow.subtask_results:
                summary = subtask.result_summary[:120]
                if len(subtask.result_summary) > 120:
                    summary += "..."
                self.console.print(
                    f"  [cyan]{subtask.id}[/cyan] {subtask.parent_agent} -> "
                    f"{subtask.delegated_to}: {subtask.status.value} - {summary}"
                )

        self.console.print(
            f"\n[dim]Duration: {result.duration_seconds:.1f}s | "
            f"Tokens: {result.total_tokens_used:,} | "
            f"Rounds: {result.rounds_completed}[/dim]\n"
        )
        self.console.print(
            "[dim]/report 로 전체 협의 결과 개괄 보기, /report save 로 파일 저장[/dim]"
        )

    # ─── Persistence ────────────────────────────────────────────────────

    def _save_history(self) -> None:
        """Save session history to JSON file."""
        self._history_file.parent.mkdir(parents=True, exist_ok=True)

        existing = []
        if self._history_file.exists():
            try:
                existing = json.loads(self._history_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = []

        existing.extend(self.tui.history)
        self._history_file.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def _has_tmux(self) -> bool:
        """Check if tmux is available for interactive mode."""
        import shutil

        return shutil.which("tmux") is not None

    def _uses_tmux_transport(self) -> bool:
        """Whether agent calls should use the legacy tmux transport."""
        return self.config.transport_mode == "tmux"

    def _transport_mode_label(self) -> str:
        """Human-readable label for the active agent transport."""
        if self._uses_tmux_transport():
            return "legacy tmux"
        return "one-shot"
