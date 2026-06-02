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
import time
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from trinity.config import TrinityConfig
from trinity.models import DeliberationResult
from trinity.tui.app import AgentTUIState, TrinityTUI
from trinity.tui.events import TUIEventBus
from trinity.tui.theme import get_theme

logger = logging.getLogger(__name__)


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
                    # Deliberation mode
                    self._run_deliberation(user_input)

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
        """Get user input with styled prompt."""
        return Prompt.ask("\n[bold green]💬 trinity>[/bold green]", console=self.console)

    def _handle_command(self, command: str) -> None:
        """Handle a /command from the user.

        Args:
            command: The command string including the leading /.
        """
        parts = command[1:].split()
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
        table.add_column("Context")

        for name, status in self.tui.agents.items():
            spec = self.config.agents.get(name)
            if not spec:
                continue
            theme = get_theme(name)
            enabled = "✅" if spec.enabled else "❌"
            state = status.state.value
            ctx = status.context_bar
            table.add_row(
                f"[{theme.color}]{theme.icon} {name}[/{theme.color}]",
                spec.provider.value,
                enabled,
                state,
                ctx,
            )

        self.console.print(table)

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

    # ─── Deliberation ──────────────────────────────────────────────────

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
            return
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            logger.exception("Deliberation failed")
            return

        # Update TUI with result
        self.tui.set_result(result)
        self.tui.reset_agents()

        # Display results
        self._display_result(result)

    def _run_with_live(
        self, orchestrator: "TrinityOrchestrator", prompt: str,
    ) -> DeliberationResult:
        """Run deliberation with Rich Live real-time display via event bus.

        Creates a TUIEventBus, passes it to the orchestrator for event
        emission, and polls for events during the Live refresh loop to
        drive real-time TUI state updates.

        Args:
            orchestrator: The orchestrator to run.
            prompt: The user's prompt.

        Returns:
            The deliberation result.
        """
        import threading

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

        # Show live TUI while deliberation runs
        # Poll the event bus during each refresh to get real-time updates
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
                    live.update(self.tui.build_layout())

                # Drain any remaining events after thread completes
                for event in bus.poll():
                    self.tui.consume_event(event)
                live.update(self.tui.build_layout())
        except KeyboardInterrupt:
            raise

        if error_holder[0]:
            raise error_holder[0]

        return result_holder[0]  # type: ignore[return-value]

    # ─── Display ────────────────────────────────────────────────────────

    def _display_result(self, result: DeliberationResult) -> None:
        """Display deliberation result."""
        if result.has_consensus:
            self.console.print(Panel.fit(
                f"[green bold]{result.consensus.summary}[/green bold]",
                title=f"✅ Consensus (Round {result.rounds_completed})",
                border_style="green",
            ))
        else:
            self.console.print(Panel.fit(
                "[yellow]No consensus reached.[/yellow]",
                title=f"Deliberation Result ({result.rounds_completed} rounds)",
                border_style="yellow",
            ))

        if result.tasks:
            from rich.table import Table

            table = Table(title="Task Distribution")
            table.add_column("Agent")
            table.add_column("Task", style="white")
            table.add_column("Priority", justify="right")

            for task in sorted(result.tasks, key=lambda t: -t.priority):
                theme = get_theme(task.agent_name)
                desc = task.task_description[:80]
                if len(task.task_description) > 80:
                    desc += "..."
                table.add_row(
                    f"[{theme.color}]{theme.icon} {task.agent_name}[/{theme.color}]",
                    desc,
                    str(task.priority),
                )

            self.console.print(table)

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
