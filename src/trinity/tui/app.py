"""Trinity TUI application — Rich Live-based interactive terminal UI.

Provides a full-screen terminal interface with:
- Header panel (version, agent status, session info)
- Agent status panel (per-agent response summary, context usage, state)
- Deliberation progress panel (round status, consensus tracking)
- Input prompt (user question entry + command mode)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from trinity import __version__
from trinity.config import TrinityConfig
from trinity.models import AgentHealth, ConsensusResult, DeliberationResult, TaskAssignment

logger = logging.getLogger(__name__)


class AgentTUIState(str, Enum):
    """TUI display state for an agent."""

    IDLE = "idle"
    RESPONDING = "responding"
    RESPONDED = "responded"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class AgentTUIStatus:
    """Per-agent TUI status tracking."""

    name: str
    provider: str
    state: AgentTUIState = AgentTUIState.IDLE
    response_preview: str = ""
    context_percent: float = 0.0
    role: str = ""

    @property
    def state_icon(self) -> str:
        icons = {
            AgentTUIState.IDLE: "⬜",
            AgentTUIState.RESPONDING: "🔄",
            AgentTUIState.RESPONDED: "✅",
            AgentTUIState.ERROR: "❌",
            AgentTUIState.DISABLED: "⏸️",
        }
        return icons.get(self.state, "❓")

    @property
    def context_bar(self) -> str:
        pct = int(self.context_percent)
        if pct >= 80:
            color = "red"
        elif pct >= 60:
            color = "yellow"
        else:
            color = "green"
        return f"[{color}]{pct}%[/{color}]"


@dataclass
class RoundStatus:
    """Tracking for a single deliberation round."""

    round_num: int
    agent_states: dict[str, AgentTUIState] = field(default_factory=dict)
    consensus: str = "waiting"  # "waiting" | "checking" | "reached" | "not_reached"
    duration: float = 0.0


class TrinityTUI:
    """Rich Live-based terminal UI for Trinity.

    Renders a full-screen TUI with real-time updates during deliberation.
    Supports command mode (/status, /context, /quit, etc.) and
    interactive question input.
    """

    def __init__(
        self,
        config: TrinityConfig,
        console: Console | None = None,
    ):
        self.config = config
        self.console = console or Console()
        self.agents: dict[str, AgentTUIStatus] = {}
        self.rounds: list[RoundStatus] = []
        self.current_round: int = 0
        self.max_rounds: int = config.max_deliberation_rounds
        self.session_start: float = time.time()
        self.last_result: DeliberationResult | None = None
        self.history: list[dict[str, Any]] = []

        # Callbacks for commands
        self.on_ask: Callable[[str], Any] | None = None
        self.on_command: Callable[[str, list[str]], Any] | None = None

        # Initialize agent status from config
        for name, spec in config.agents.items():
            self.agents[name] = AgentTUIStatus(
                name=name,
                provider=spec.provider.value,
                role=spec.role_prompt.split(".")[0] if spec.role_prompt else "",
                state=AgentTUIState.DISABLED if not spec.enabled else AgentTUIState.IDLE,
            )

    def build_header(self) -> Panel:
        """Build the header panel."""
        # Agent status line
        agent_parts = []
        for name, status in self.agents.items():
            if status.state == AgentTUIState.DISABLED:
                agent_parts.append(f"{name} ❌")
            else:
                agent_parts.append(f"{name} ✅")
        agent_line = "  ".join(agent_parts)

        elapsed = time.time() - self.session_start
        mins, secs = divmod(int(elapsed), 60)

        content = (
            f"[bold cyan]🧠 Trinity v{__version__}[/bold cyan]\n"
            f"[dim]Three minds, one context[/dim]\n\n"
            f"Agents: {agent_line}\n"
            f"Session: {self.config.session_name}  ⏱ {mins}m {secs:02d}s"
        )

        return Panel.fit(
            content,
            border_style="cyan",
        )

    def build_agent_panel(self) -> Panel:
        """Build the agent status panel."""
        table = Table(
            show_header=True,
            header_style="bold",
            expand=True,
            title="📊 Agent Status",
            title_style="bold",
        )
        table.add_column("Agent", style="cyan", min_width=12)
        table.add_column("Role", max_width=20)
        table.add_column("Status", min_width=12)
        table.add_column("Context", justify="right", min_width=8)
        table.add_column("Response", max_width=40)

        for name, status in self.agents.items():
            if status.state == AgentTUIState.DISABLED:
                continue

            state_str = f"{status.state_icon} {status.state.value}"
            preview = status.response_preview[:40]
            if len(status.response_preview) > 40:
                preview += "..."

            table.add_row(
                name,
                status.role[:20],
                state_str,
                status.context_bar,
                preview,
            )

        return Panel(table, border_style="blue")

    def build_deliberation_panel(self) -> Panel:
        """Build the deliberation progress panel."""
        table = Table(
            show_header=True,
            header_style="bold",
            expand=True,
            title="📋 Deliberation Progress",
            title_style="bold",
        )
        table.add_column("Round", style="cyan", min_width=8)
        table.add_column("Agents", max_width=50)
        table.add_column("Consensus", min_width=15)

        for round_status in self.rounds:
            round_label = f"Round {round_status.round_num}"
            agent_parts = []
            for name, state in round_status.agent_states.items():
                icon = {
                    AgentTUIState.IDLE: "⬜",
                    AgentTUIState.RESPONDING: "🔄",
                    AgentTUIState.RESPONDED: "✅",
                    AgentTUIState.ERROR: "❌",
                }.get(state, "❓")
                agent_parts.append(f"{icon} {name}")

            agents_str = " → ".join(agent_parts)

            consensus_icons = {
                "waiting": "⏳ 대기",
                "checking": "🔍 판정중",
                "reached": "✅ 합의 도달",
                "not_reached": "❌ 합의 실패",
            }
            consensus_str = consensus_icons.get(
                round_status.consensus, round_status.consensus
            )

            table.add_row(round_label, agents_str, consensus_str)

        if not self.rounds:
            table.add_row("[dim]—[/dim]", "[dim]No deliberation yet[/dim]", "[dim]—[/dim]")

        # Consensus summary
        round_info = f"Round: {self.current_round}/{self.max_rounds}"
        elapsed = time.time() - self.session_start
        mins, secs = divmod(int(elapsed), 60)
        time_info = f"⏱ {mins}m {secs:02d}s"

        return Panel(
            Group(table, Text(f"\n{round_info}  {time_info}")),
            border_style="green",
        )

    def build_result_panel(self) -> Panel | None:
        """Build the result panel if a result is available."""
        if not self.last_result:
            return None

        result = self.last_result

        if result.has_consensus:
            content = f"[green bold]✅ Consensus Reached (Round {result.rounds_completed})[/green bold]\n\n"
            content += f"[white]{result.consensus.summary}[/white]\n"
        else:
            content = f"[yellow]⚠️ No Consensus ({result.rounds_completed} rounds)[/yellow]\n"

        if result.tasks:
            content += "\n[bold]Task Distribution:[/bold]\n"
            for task in sorted(result.tasks, key=lambda t: -t.priority):
                desc = task.task_description[:60]
                if len(task.task_description) > 60:
                    desc += "..."
                content += f"  • [cyan]{task.agent_name}[/cyan]: {desc}\n"

        stats = (
            f"\n[dim]Duration: {result.duration_seconds:.1f}s | "
            f"Tokens: {result.total_tokens_used:,} | "
            f"Rounds: {result.rounds_completed}[/dim]"
        )
        content += stats

        return Panel(content, title="📋 Result", border_style="yellow")

    def build_layout(self) -> Group:
        """Build the complete TUI layout."""
        panels = [
            self.build_header(),
            self.build_agent_panel(),
            self.build_deliberation_panel(),
        ]

        result_panel = self.build_result_panel()
        if result_panel:
            panels.append(result_panel)

        panels.append(Text())  # Spacer
        panels.append(Text("[bold green]💬 trinity>[/bold green] ", style="bold green"))

        return Group(*panels)

    def update_agent_status(
        self,
        name: str,
        state: AgentTUIState | None = None,
        response_preview: str | None = None,
        context_percent: float | None = None,
    ) -> None:
        """Update the TUI status for a specific agent.

        Args:
            name: Agent name.
            state: New state (or None to keep current).
            response_preview: New response preview (or None to keep current).
            context_percent: New context percentage (or None to keep current).
        """
        if name not in self.agents:
            logger.warning(f"TUI: Unknown agent '{name}'")
            return

        agent = self.agents[name]
        if state is not None:
            agent.state = state
        if response_preview is not None:
            agent.response_preview = response_preview
        if context_percent is not None:
            agent.context_percent = context_percent

    def start_round(self, round_num: int) -> None:
        """Mark the start of a new deliberation round.

        Args:
            round_num: The round number (1-based).
        """
        self.current_round = round_num

        agent_states = {}
        for name, status in self.agents.items():
            if status.state != AgentTUIState.DISABLED:
                agent_states[name] = AgentTUIState.RESPONDING
                status.state = AgentTUIState.RESPONDING
                status.response_preview = ""

        self.rounds.append(RoundStatus(
            round_num=round_num,
            agent_states=agent_states,
            consensus="waiting",
        ))

    def mark_agent_responded(self, name: str, preview: str = "") -> None:
        """Mark an agent as having responded in the current round.

        Args:
            name: Agent name.
            preview: Response preview text.
        """
        self.update_agent_status(name, AgentTUIState.RESPONDED, preview)

        if self.rounds:
            self.rounds[-1].agent_states[name] = AgentTUIState.RESPONDED

    def mark_consensus_checking(self) -> None:
        """Mark that consensus is being evaluated for the current round."""
        if self.rounds:
            self.rounds[-1].consensus = "checking"

    def mark_consensus_result(self, reached: bool) -> None:
        """Mark the consensus result for the current round.

        Args:
            reached: Whether consensus was reached.
        """
        if self.rounds:
            self.rounds[-1].consensus = "reached" if reached else "not_reached"

    def set_result(self, result: DeliberationResult) -> None:
        """Set the final deliberation result.

        Args:
            result: The deliberation result.
        """
        self.last_result = result
        self.history.append({
            "prompt": result.user_prompt,
            "rounds": result.rounds_completed,
            "consensus": result.has_consensus,
            "duration": result.duration_seconds,
            "timestamp": time.time(),
        })

    def reset_agents(self) -> None:
        """Reset all agent states to idle."""
        for name, status in self.agents.items():
            if status.state != AgentTUIState.DISABLED:
                status.state = AgentTUIState.IDLE
                status.response_preview = ""

    def get_welcome_text(self) -> str:
        """Get the welcome/help text for the TUI."""
        return (
            f"[bold cyan]🧠 Trinity v{__version__}[/bold cyan]\n\n"
            "[bold]Commands:[/bold]\n"
            "  [cyan]<text>[/cyan]       — Ask agents to deliberate on a topic\n"
            "  [cyan]/status[/cyan]     — Show agent status table\n"
            "  [cyan]/context[/cyan]    — Show shared context\n"
            "  [cyan]/rounds [N][/cyan] — Set max deliberation rounds\n"
            "  [cyan]/agent <n> on/off[/cyan] — Enable/disable an agent\n"
            "  [cyan]/history[/cyan]    — Show deliberation history\n"
            "  [cyan]/save[/cyan]       — Save current session results\n"
            "  [cyan]/help[/cyan]       — Show this help\n"
            "  [cyan]/quit[/cyan]       — Exit Trinity\n"
        )
