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
import shlex
import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel

from trinity.config import TrinityConfig
from trinity.models import DeliberationResult
from trinity.tui.app import AgentTUIState, TrinityTUI
from trinity.tui.events import TUIEventBus
from trinity.tui.prompt import TrinityPromptSession
from trinity.tui.theme import get_theme
from trinity.workflow import (
    ExecutionResult,
    WorkflowEngine,
    WorkflowInputAction,
    WorkflowState,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from trinity.orchestrator import TrinityOrchestrator


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
        self.workflow = WorkflowEngine(config.effective_state_dir)
        self.tui.set_workflow_session(self.workflow.session)

    def run(self) -> None:
        """Run the interactive session (blocking).

        This is the main entry point for `trinity` without arguments.
        """
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

    def _show_welcome(self) -> None:
        """Show welcome message."""
        self.console.print(self.tui.get_welcome_text())
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
        try:
            parts = shlex.split(command[1:])
        except ValueError as exc:
            self.console.print(f"[yellow]Invalid command syntax: {exc}[/yellow]")
            return
        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("quit", "exit", "q"):
            self.running = False
        elif cmd == "help":
            self.console.print(self.tui.get_welcome_text())
        elif cmd == "status":
            self._cmd_status()
        elif cmd == "context":
            self._cmd_context()
        elif cmd == "rounds":
            self._cmd_rounds(args)
        elif cmd == "agent":
            self._cmd_agent(args)
        elif cmd == "history":
            self._cmd_history()
        elif cmd == "save":
            self._cmd_save()
        elif cmd == "caveman":
            self._cmd_caveman(args)
        elif cmd == "workflow":
            self._cmd_workflow()
        elif cmd == "questions":
            self._cmd_questions(args)
        elif cmd == "answer":
            self._cmd_answer(args)
        elif cmd == "decisions":
            self._cmd_decisions()
        elif cmd == "packages":
            self._cmd_packages()
        elif cmd == "subtasks":
            self._cmd_subtasks()
        else:
            self.console.print(
                f"[yellow]Unknown command: /{cmd}. "
                f"Type /help for available commands.[/yellow]"
            )

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
        self._cmd_workflow()

    def _cmd_context(self) -> None:
        """Show shared context."""
        from trinity.context.shared import SharedContextEngine

        engine = SharedContextEngine(path=self.config.shared_context_path)
        content = engine.read()
        if content.strip():
            self.console.print(Panel(content, title="Shared Context"))
        else:
            self.console.print("[yellow]Shared context is empty.[/yellow]")

    def _cmd_rounds(self, args: list[str]) -> None:
        """Set max deliberation rounds.

        Usage: /rounds [N]
        """
        if not args:
            self.console.print(
                f"Current max rounds: [cyan]{self.config.max_deliberation_rounds}[/cyan]"
            )
            return

        try:
            n = int(args[0])
            if n < 1 or n > 20:
                self.console.print("[yellow]Rounds must be between 1 and 20.[/yellow]")
                return
            self.config.max_deliberation_rounds = n
            self.tui.max_rounds = n
            self.console.print(f"[green]Max rounds set to {n}[/green]")
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
            self.console.print(f"[green]Agent '{name}' enabled.[/green]")
        elif action == "off":
            self.config.agents[name].enabled = False
            self.tui.update_agent_status(name, AgentTUIState.DISABLED)
            self.console.print(f"[yellow]Agent '{name}' disabled.[/yellow]")
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
                f"  [dim]Usage: /caveman [on|off|lite|full|ultra][/dim]"
            )
            return

        action = args[0].lower()

        if action in ("off", "disable"):
            self.config.caveman_mode = False
            self.console.print("[yellow]🦴 Caveman compression disabled.[/yellow]")
        elif action in ("on", "enable"):
            self.config.caveman_mode = True
            self.console.print(f"[green]🦴 Caveman compression enabled ({self.config.caveman_intensity}).[/green]")
        elif action in VALID_CAVEMAN_INTENSITIES:
            self.config.caveman_mode = True
            self.config.caveman_intensity = action
            self.console.print(f"[green]🦴 Caveman set to [bold]{action}[/bold].[/green]")
        else:
            self.console.print(
                f"[yellow]Unknown option: {action}. "
                f"Use: on, off, lite, full, ultra[/yellow]"
            )

    def _cmd_workflow(self) -> None:
        """Show current workflow state."""
        session = self.workflow.session
        self.tui.set_workflow_session(session)
        self.console.print(Panel.fit(
            f"[bold]ID[/bold]: {session.id}\n"
            f"[bold]State[/bold]: {session.state.value}\n"
            f"[bold]Goal[/bold]: {session.goal or '(none)'}\n"
            f"[bold]Round[/bold]: {session.current_round}\n"
            f"[bold]Active agents[/bold]: {', '.join(session.active_agents) or '(none)'}\n"
            f"[bold]Pending questions[/bold]: {len(session.open_questions)}\n"
            f"[bold]Decisions[/bold]: {len(session.decisions)}\n"
            f"[bold]Work packages[/bold]: {len(session.work_packages)}\n"
            f"[bold]Subtasks[/bold]: {len(session.subtask_results)}\n"
            f"[bold]Review packages[/bold]: {len(session.review_packages)}",
            title="Workflow",
            border_style="magenta",
        ))

    def _cmd_questions(self, args: list[str] | None = None) -> None:
        """Show pending workflow questions."""
        args = args or []
        if any(arg in {"--select", "-s"} for arg in args):
            self._cmd_select_question()
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
            self.console.print(
                "[dim]Usage: /answer <question-id|index|next> <answer>[/dim]"
            )
            return

        active = self.config.active_agents
        if not active:
            self.console.print(
                "[red]No active agents. Use /agent <name> on to enable one.[/red]"
            )
            return

        replace = False
        filtered: list[str] = []
        for arg in args:
            if arg in {"--replace", "-r"}:
                replace = True
            else:
                filtered.append(arg)

        if not filtered:
            self.console.print(
                "[dim]Usage: /answer <question-id|index|next> <answer>[/dim]"
            )
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

    def _cmd_select_question(self) -> None:
        """Select the next question option with arrow keys."""
        questions = self.workflow.pending_questions
        if not questions:
            self.console.print("[dim]No pending workflow questions.[/dim]")
            return

        if not sys.stdin.isatty() or not sys.stdout.isatty():
            self.console.print(
                "[yellow]Interactive selection requires a terminal. "
                "Use /answer <question-id|index|next> <answer> instead.[/yellow]"
            )
            return

        question = questions[0]
        if not question.options:
            self.console.print(
                f"[yellow]{question.id} has no selectable options. "
                "Use /answer next <answer>.[/yellow]"
            )
            return

        selected = self._prompt_session.select_option(
            title=f"{question.id}",
            question=question.question,
            options=question.options,
            recommended_option=question.recommended_option,
        )
        if selected is None:
            self.console.print("[dim]Selection cancelled.[/dim]")
            return

        action = self.workflow.answer_question_option(
            str(selected),
            question_selector=question.id,
        )
        self._apply_workflow_action(action)

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
        table.add_column("Objective")

        for package in packages:
            table.add_row(
                package.id,
                package.owner_agent,
                package.status.value,
                "yes" if package.requires_execution else "no",
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

    # ─── Deliberation ──────────────────────────────────────────────────

    def _handle_user_text(self, text: str) -> None:
        """Route normal input through workflow state before deliberating."""
        active = self.config.active_agents
        if not active:
            self.console.print(
                "[red]No active agents. Use /agent <name> on to enable one.[/red]"
            )
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
            self.console.print(
                f"[green]{verb} decision {action.decision_record.id}.[/green]"
            )

        if action.should_deliberate:
            self._run_deliberation(action.prompt)
        elif self.workflow.state == WorkflowState.NEEDS_USER_DECISION:
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
                    lines.append(
                        f"    {option_index}. {escape(option)}{suffix}"
                    )
                lines.append(
                    f"    답변: /answer {index} <값> 또는 "
                    f"/answer {question.id} <값>"
                )
                if index == 1:
                    lines.append("    선택 UI: /questions --select")
            else:
                lines.append(
                    f"    답변: /answer {index} <값> 또는 "
                    f"/answer {question.id} <값>"
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
            self.console.print(
                "[red]No active agents. Use /agent <name> on to enable one.[/red]"
            )
            return

        mode_str = "interactive (tmux)" if self._has_tmux() else "print mode"
        self.console.print(Panel.fit(
            f"[bold]{prompt}[/bold]\n\n"
            f"Agents: {', '.join(active.keys())}\n"
            f"Max rounds: {self.config.max_deliberation_rounds}\n"
            f"Mode: {mode_str}",
            title="🧠 Deliberation Starting",
            border_style="cyan",
        ))

        # Create orchestrator
        orchestrator = TrinityOrchestrator(self.config, interactive=self._has_tmux())

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

        # Now reset agent states for next deliberation
        self.tui.reset_agents()

    def _run_with_live(
        self, orchestrator: "TrinityOrchestrator", prompt: str,
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

        self.workflow.begin_execution()
        self.tui.set_workflow_session(self.workflow.session)

        try:
            results = self._run_execution_with_live(orchestrator)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Execution interrupted.[/yellow]")
            return
        except Exception as exc:
            self.console.print(f"[red]Execution error: {exc}[/red]")
            logger.exception("Execution failed")
            return

        self.workflow.record_execution_results(results)
        self.tui.set_workflow_session(self.workflow.session)

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

        def _run_async():
            try:
                result_holder[0] = asyncio.run(
                    orchestrator.execute_work_packages(
                        self.workflow.session.work_packages,
                        decisions=self.workflow.decisions,
                    )
                )
            except Exception as exc:
                error_holder[0] = exc

        thread = threading.Thread(target=_run_async, daemon=True)
        thread.start()
        done_received = False

        try:
            with Live(
                self.tui.build_layout(),
                console=self.console,
                refresh_per_second=4,
                transient=True,
            ) as live:
                while thread.is_alive():
                    thread.join(timeout=0.25)
                    for event in bus.poll():
                        self.tui.consume_event(event)
                        if event.type == TUIEventType.EXECUTION_DONE:
                            done_received = True

                    if done_received:
                        for event in bus.poll():
                            self.tui.consume_event(event)
                        live.update(self.tui.build_layout())
                        thread.join(timeout=2.0)
                        break

                    live.update(self.tui.build_layout())

                for event in bus.poll():
                    self.tui.consume_event(event)
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
            self.console.print(Panel.fit(
                f"[green bold]{result.consensus.summary}[/green bold]",
                title=f"✅ Consensus (Round {result.rounds_completed})",
                border_style="green",
            ))
        else:
            summary = (
                result.consensus.summary
                if result.consensus and result.consensus.summary
                else "No consensus reached."
            )
            self.console.print(Panel.fit(
                f"[yellow]{summary}[/yellow]",
                title=f"Deliberation Result ({result.rounds_completed} rounds)",
                border_style="yellow",
            ))

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
                    self.console.print(Panel(
                        Markdown(response[:2000]),
                        border_style=theme.border_style,
                        padding=(0, 1),
                    ))

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
                self.console.print(
                    f"  [cyan]{package.id}[/cyan] {package.owner_agent}: "
                    f"{package.title} ({package.status.value})"
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
