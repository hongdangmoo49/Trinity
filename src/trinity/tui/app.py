"""Trinity TUI application — Rich Live-based interactive terminal UI.

Provides a full-screen terminal interface with:
- Header panel (version, agent status pills, session info)
- Agent status panel (compact pilot view with per-agent state)
- Deliberation panel (real-time agent opinions with Markdown rendering)
- Result panel (consensus progress, Markdown summary, task list)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.rule import Rule
from rich.text import Text

from trinity import __version__
from trinity.config import TrinityConfig
from trinity.models import DeliberationResult
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.tui.sacred_geometry import SacredGeometryAnimator
from trinity.tui.theme import get_theme
from trinity.workflow.models import WorkflowSession, WorkflowState

logger = logging.getLogger(__name__)


class AgentTUIState(str, Enum):
    """TUI display state for an agent."""

    IDLE = "idle"
    READY = "ready"
    RESPONDING = "responding"
    RESPONDED = "responded"
    ERROR = "error"
    NOT_READY = "not_ready"
    DISABLED = "disabled"


@dataclass
class AgentTUIStatus:
    """Per-agent TUI status tracking."""

    name: str
    provider: str
    state: AgentTUIState = AgentTUIState.IDLE
    response_preview: str = ""
    full_response: str = ""
    context_percent: float = 0.0
    role: str = ""
    readiness_state: str = "unknown"
    readiness_reason: str = ""
    readiness_action_hint: str = ""

    @property
    def state_icon(self) -> str:
        icons = {
            AgentTUIState.IDLE: "⬜",
            AgentTUIState.READY: "✅",
            AgentTUIState.RESPONDING: "🔄",
            AgentTUIState.RESPONDED: "✅",
            AgentTUIState.ERROR: "❌",
            AgentTUIState.NOT_READY: "⚠️",
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
    agent_opinions: dict[str, str] = field(default_factory=dict)
    consensus: str = "waiting"  # "waiting" | "checking" | "reached" | "not_reached"
    consensus_detail: str = ""
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
        *,
        show_geometry: bool = True,
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
        self.workflow_state: WorkflowState = WorkflowState.IDLE
        self.workflow_id: str = ""
        self.workflow_goal: str = ""
        self.pending_question_count: int = 0
        self.work_package_count: int = 0
        self.work_package_statuses: dict[str, str] = {}
        self.subtask_result_count: int = 0

        # Deliberation progress state
        self.deliberation_active: bool = False
        self.deliberation_prompt: str = ""
        self.current_phase: str = ""       # opinions | counter | consensus | synthesis
        self.phase_started_at: float = 0.0
        self.progress_completed: int = 0
        self.progress_total: int = 0

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

        # Sacred geometry animation
        self._animation_tick: float = 0.0
        self._geometry_animator: SacredGeometryAnimator | None = None
        if show_geometry:
            term_height = self.console.size.height or 40  # Default for non-tty
            if term_height >= 20:
                term_width = self.console.size.width or 80
                self._geometry_animator = SacredGeometryAnimator(
                    width=min(term_width - 4, 50),
                    height=11,
                    mode="modern",
                )

    # ─── Event Consumption ─────────────────────────────────────────────

    def consume_event(self, event: TUIEvent) -> None:
        """Process a TUI event and update internal state.

        Called from the main thread during Live refresh to apply
        real-time deliberation updates.

        Args:
            event: The event from TUIEventBus.
        """
        if event.type == TUIEventType.ROUND_START:
            self.start_round(event.data["round_num"])

        elif event.type == TUIEventType.AGENT_THINKING:
            name = event.data["agent"]
            self.update_agent_status(name, state=AgentTUIState.RESPONDING)

        elif event.type == TUIEventType.AGENT_RESPONDED:
            name = event.data["agent"]
            content = event.data.get("content", "")
            metadata = event.data.get("metadata", {})
            response_status = event.data.get("response_status")
            if not response_status:
                response_status = self._response_status_from_metadata(metadata)
            preview = content[:200]
            if response_status == "ok":
                self.mark_agent_responded(name, preview)
            else:
                self.mark_agent_response_error(name, preview)
            # Store full response
            if name in self.agents:
                self.agents[name].full_response = content
            # Store opinion in current round
            if self.rounds:
                self.rounds[-1].agent_opinions[name] = content

        elif event.type == TUIEventType.AGENT_ERROR:
            name = event.data["agent"]
            self.update_agent_status(name, state=AgentTUIState.ERROR)
            if name in self.agents:
                self.agents[name].full_response = event.data.get("error", "Unknown error")
            if self.rounds:
                self.rounds[-1].agent_opinions[name] = (
                    f"[Error: {event.data.get('error', 'Unknown')}]"
                )

        elif event.type == TUIEventType.PROVIDER_READINESS:
            self.mark_provider_readiness(
                name=event.data["agent"],
                ready=event.data.get("ready", False),
                readiness_state=event.data.get("state", "unknown"),
                reason=event.data.get("reason", ""),
                action_hint=event.data.get("action_hint", ""),
                excerpt=event.data.get("excerpt", ""),
            )

        elif event.type == TUIEventType.CONSENSUS_CHECKING:
            self.mark_consensus_checking()

        elif event.type == TUIEventType.CONSENSUS_RESULT:
            reached = event.data["reached"]
            self.mark_consensus_result(reached)
            if self.rounds:
                agree = event.data.get("agreement_count", 0)
                total = event.data.get("total_agents", 0)
                if total > 0:
                    pct = int(agree / total * 100)
                    self.rounds[-1].consensus_detail = f"{agree}/{total} 동의 ({pct}%)"
                elif event.data.get("summary"):
                    self.rounds[-1].consensus_detail = event.data["summary"]

        elif event.type == TUIEventType.DELIBERATION_STARTED:
            self.deliberation_active = True
            self.deliberation_prompt = event.data.get("prompt", "")
            self.current_phase = "opinions"
            self.phase_started_at = time.time()

        elif event.type == TUIEventType.DELIBERATION_PHASE:
            self.current_phase = event.data.get("phase", "")
            self.phase_started_at = time.time()

        elif event.type == TUIEventType.DELIBERATION_PROGRESS:
            self.progress_completed = event.data.get("completed", 0)
            self.progress_total = event.data.get("total", 0)

        elif event.type == TUIEventType.EXECUTION_START:
            self.work_package_count = int(
                event.data.get("package_count", self.work_package_count)
            )

        elif event.type == TUIEventType.EXECUTION_BATCH_PLANNED:
            pass

        elif event.type == TUIEventType.WORK_PACKAGE_STARTED:
            package_id = str(event.data.get("package_id", ""))
            if package_id:
                self.work_package_statuses[package_id] = str(
                    event.data.get("status", "running")
                )

        elif event.type == TUIEventType.WORK_PACKAGE_COMPLETED:
            package_id = str(event.data.get("package_id", ""))
            if package_id:
                self.work_package_statuses[package_id] = str(
                    event.data.get("status", "done")
                )

        elif event.type == TUIEventType.EXECUTION_DONE:
            pass

        elif event.type == TUIEventType.DELIBERATION_DONE:
            self.deliberation_active = False
            self.current_phase = ""
            self.progress_completed = 0
            self.progress_total = 0

    # ─── Layout Builders ───────────────────────────────────────────────

    def build_header(self) -> Panel:
        """Build the header panel with agent status pills."""
        # Agent status pills with per-agent colors
        agent_parts: list[Text] = []
        for name, status in self.agents.items():
            theme = get_theme(name)
            if status.state == AgentTUIState.DISABLED:
                pill = Text(f"  {name} ⏸  ", style="dim")
            else:
                icon = status.state_icon
                pill = Text(f"  {theme.icon} {name} {icon}  ", style=f"bold {theme.color}")
            agent_parts.append(pill)

        agent_line = Text.assemble(*agent_parts)

        elapsed = time.time() - self.session_start
        mins, secs = divmod(int(elapsed), 60)

        # Build header content parts
        header_parts: list = []

        # Sacred geometry mandala
        if self._geometry_animator is not None:
            self._animation_tick += 0.15  # Advance rotation
            agent_colors = [
                get_theme(name).color
                for name, status in self.agents.items()
                if status.state != AgentTUIState.DISABLED
            ]
            geo_text = self._geometry_animator.render_rich(
                angle=self._animation_tick,
                colors=agent_colors[:3] or ["cyan", "green", "magenta"],
            )
            header_parts.append(geo_text)
            header_parts.append(Text())

        header_parts.extend([
            Text.assemble(
                Text("🧠 ", style=""),
                Text(f"Trinity v{__version__}", style="bold cyan"),
                Text("  —  ", style="dim"),
                Text("Three minds, one context", style="dim italic"),
            ),
            Text(),
            agent_line,
            Text(),
            Text.assemble(
                Text(f"📡 Session: {self.config.session_name}", style="dim"),
                Text(f"  ⏱ {mins}m {secs:02d}s", style="dim"),
            ),
            Text.assemble(
                Text("Workflow: ", style="dim"),
                Text(self.workflow_state.value, style="bold magenta"),
                Text(
                    f"  Pending questions: {self.pending_question_count}",
                    style="dim",
                ),
                Text(
                    f"  Work packages: {self._work_package_summary()}",
                    style="dim",
                ),
                Text(f"  Subtasks: {self.subtask_result_count}", style="dim"),
            ),
            Text.assemble(
                self._caveman_badge(),
            ),
            Text(),
        ])

        content = Group(*header_parts)

        return Panel.fit(
            content,
            border_style="cyan",
        )

    def build_agent_panel(self) -> Panel:
        """Build the agent status panel — compact pilot view.

        Shows a single line per active agent with icon, name, and state.
        Detailed status is available via /status command.
        """
        parts: list[Text] = []
        for name, status in self.agents.items():
            if status.state == AgentTUIState.DISABLED:
                continue

            theme = get_theme(name)
            icon = status.state_icon

            # Compact: icon + name + state
            label = status.readiness_state if status.state == AgentTUIState.NOT_READY else status.state.value
            parts.append(
                Text(
                    f"  {theme.icon} {name} {icon} {label}  ",
                    style=f"bold {theme.color}",
                )
            )

        if not parts:
            parts.append(Text("  No active agents", style="dim"))

        return Panel(
            Text.assemble(*parts),
            title="📊 Agents",
            border_style="blue",
        )

    def build_deliberation_panel(self) -> Panel:
        """Build the deliberation panel — status-only during live updates.

        During the Live refresh loop, shows only agent status indicators
        (thinking/responded) without opinion content. This prevents garbled
        CLI splash screens from appearing in the panel. Content is displayed
        only in the final result after deliberation completes.
        """
        renderables: list = []

        if not self.rounds:
            renderables.append(
                Text("  No deliberation yet. Ask a question to begin.", style="dim")
            )
        else:
            for round_status in self.rounds:
                # Round separator
                renderables.append(
                    Rule(
                        f"  Round {round_status.round_num}  ",
                        style="bold cyan",
                        characters="─",
                    )
                )

                # Show each agent's status only — NO content during live
                for name, state in round_status.agent_states.items():
                    theme = get_theme(name)

                    if state == AgentTUIState.RESPONDING:
                        renderables.append(
                            Text.assemble(
                                Text("  🔄 ", style=""),
                                Text(f"{name}", style=f"bold {theme.color}"),
                                Text(f" ({theme.role_label})", style="dim"),
                                Text(" 생각중...", style="yellow"),
                            )
                        )
                    elif state == AgentTUIState.ERROR:
                        renderables.append(
                            Text.assemble(
                                Text("  ❌ ", style=""),
                                Text(f"{name}", style=f"bold {theme.color}"),
                                Text(f" ({theme.role_label})", style="dim"),
                                Text(" 오류 발생", style="red"),
                            )
                        )
                    elif state == AgentTUIState.RESPONDED:
                        renderables.append(
                            Text.assemble(
                                Text("  ✅ ", style=""),
                                Text(f"{name}", style=f"bold {theme.color}"),
                                Text(f" ({theme.role_label})", style="dim"),
                                Text(" 응답 완료", style="green"),
                            )
                        )

                # Consensus status for this round
                consensus_labels = {
                    "waiting": ("⏳ 대기중", "dim"),
                    "checking": ("🔍 합의 판정중...", "yellow"),
                    "reached": ("✅ 합의 도달!", "bold green"),
                    "not_reached": ("❌ 합의 실패", "yellow"),
                }
                label, style = consensus_labels.get(
                    round_status.consensus,
                    (round_status.consensus, "white"),
                )

                consensus_line = Text(f"  {label}", style=style)
                if round_status.consensus_detail:
                    consensus_line.append(
                        Text(f"  {round_status.consensus_detail}", style="dim")
                    )
                renderables.append(consensus_line)

        # Round counter + elapsed time
        round_info = f"Round: {self.current_round}/{self.max_rounds}"
        elapsed = time.time() - self.session_start
        mins, secs = divmod(int(elapsed), 60)
        time_info = f"⏱ {mins}m {secs:02d}s"

        renderables.append(Text())
        renderables.append(
            Text(f"  {round_info}    {time_info}", style="dim")
        )

        return Panel(
            Group(*renderables),
            title="💬 Deliberation",
            border_style="green",
        )

    def build_result_panel(self) -> Panel | None:
        """Build the result panel with consensus progress and task distribution."""
        if not self.last_result:
            return None

        result = self.last_result
        renderables: list = []

        # Consensus status header
        if result.has_consensus:
            renderables.append(
                Text("  ✅ 합의 도달", style="bold green")
            )
            if result.consensus:
                # Consensus progress bar
                agree = result.consensus.agreement_count
                total = result.consensus.total_agents
                if total > 0:
                    progress = Progress(
                        TextColumn("  "),
                        TextColumn("{task.description}", style="dim"),
                        BarColumn(bar_width=30, complete_style="green"),
                        TextColumn("{task.completed}/{task.total}", style="bold"),
                    )
                    task = progress.add_task(
                        "합의 진행률", total=total, completed=agree
                    )
                    # Stop the progress (static rendering)
                    progress.update(task, completed=agree)
                    renderables.append(progress)
                    renderables.append(Text())

                # Consensus summary as Markdown
                if result.consensus.summary:
                    renderables.append(
                        Panel(
                            Markdown(result.consensus.summary),
                            title="📋 합의 요약",
                            border_style="green",
                            padding=(0, 1),
                        )
                    )
        else:
            renderables.append(
                Text(f"  ⚠️ 합의 실패 ({result.rounds_completed} 라운드)", style="yellow")
            )

        # Task distribution as simple list
        if result.tasks:
            renderables.append(Text())
            renderables.append(Text("  🎯 작업 분배", style="bold"))
            for task in sorted(result.tasks, key=lambda t: -t.priority):
                theme = get_theme(task.agent_name)
                desc = task.task_description[:120]
                if len(task.task_description) > 120:
                    desc += "..."
                renderables.append(
                    Text.from_markup(
                        f"    [{theme.color}]{theme.icon} {task.agent_name}[/{theme.color}]: "
                        f"{desc}"
                    )
                )

        # Stats line
        stats = (
            f"\n  [dim]소요시간: {result.duration_seconds:.1f}s | "
            f"토큰: {result.total_tokens_used:,} | "
            f"라운드: {result.rounds_completed}[/dim]"
        )
        renderables.append(Text.from_markup(stats))

        return Panel(
            Group(*renderables),
            title="📋 Result",
            border_style="yellow",
        )

    def build_layout(self) -> Group:
        """Build the complete TUI layout."""
        panels: list = [
            self.build_header(),
            self.build_agent_panel(),
            self.build_deliberation_panel(),
        ]

        result_panel = self.build_result_panel()
        if result_panel:
            panels.append(result_panel)

        panels.append(Text())  # Spacer
        panels.append(Text("💬 trinity>", style="bold green"))

        return Group(*panels)

    # ─── State Mutations ───────────────────────────────────────────────

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
            if status.state not in {AgentTUIState.DISABLED, AgentTUIState.NOT_READY}:
                agent_states[name] = AgentTUIState.RESPONDING
                status.state = AgentTUIState.RESPONDING
                status.response_preview = ""
                status.full_response = ""

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

    def mark_agent_response_error(self, name: str, preview: str = "") -> None:
        """Mark a completed response as unusable or unreliable."""
        self.update_agent_status(name, AgentTUIState.ERROR, preview)

        if self.rounds:
            self.rounds[-1].agent_states[name] = AgentTUIState.ERROR

    def mark_provider_readiness(
        self,
        name: str,
        ready: bool,
        readiness_state: str,
        reason: str,
        action_hint: str,
        excerpt: str,
    ) -> None:
        """Record provider readiness state for one agent."""
        if name not in self.agents:
            logger.warning(f"TUI: Unknown agent '{name}'")
            return

        status = self.agents[name]
        status.readiness_state = readiness_state
        status.readiness_reason = reason
        status.readiness_action_hint = action_hint
        status.full_response = "\n".join(
            part for part in (reason, action_hint, excerpt) if part
        )
        status.state = AgentTUIState.READY if ready else AgentTUIState.NOT_READY

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

    @staticmethod
    def _response_status_from_metadata(metadata: Any) -> str:
        """Infer response quality from event metadata for older emitters."""
        if not isinstance(metadata, dict):
            return "ok"

        if metadata.get("invalid_response"):
            return "invalid_response"

        validation = metadata.get("response_validation")
        if isinstance(validation, dict) and validation.get("usable") is False:
            return str(validation.get("classification") or "invalid_response")

        if metadata.get("error") == "timeout":
            return "timeout"

        if metadata.get("completed") is False:
            return "completion_timeout"

        detector = str(metadata.get("detector", "")).lower()
        if detector == "fallback" or detector.startswith("fallbackchain("):
            return "captured_fallback"

        return "ok"

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

    def set_workflow_session(self, session: WorkflowSession) -> None:
        """Reflect persisted workflow state in the TUI header."""
        self.workflow_state = session.state
        self.workflow_id = session.id
        self.workflow_goal = session.goal
        self.pending_question_count = len(session.open_questions)
        self.work_package_count = len(session.work_packages)
        self.work_package_statuses = {
            package.id: package.status.value for package in session.work_packages
        }
        self.subtask_result_count = len(session.subtask_results)

    def reset_agents(self) -> None:
        """Reset all agent states to idle and clear round history."""
        for name, status in self.agents.items():
            if status.state != AgentTUIState.DISABLED:
                status.state = AgentTUIState.IDLE
                status.response_preview = ""
                status.full_response = ""
                status.readiness_state = "unknown"
                status.readiness_reason = ""
                status.readiness_action_hint = ""
        # Clear round history between deliberations
        self.rounds.clear()
        self.current_round = 0

    def _work_package_summary(self) -> str:
        """Render a compact package status summary for the header."""
        if not self.work_package_count:
            return "0"
        done = sum(
            1 for status in self.work_package_statuses.values() if status == "done"
        )
        return f"{done}/{self.work_package_count} done"

    def _caveman_badge(self) -> Text:
        """Render caveman status badge for the header."""
        if self.config.caveman_mode:
            intensity = self.config.caveman_intensity.upper()
            return Text.assemble(
                Text("  🦴 ", style=""),
                Text(f"CAVEMAN:{intensity}", style="bold orange3"),
            )
        return Text()

    def get_welcome_text(self) -> str:
        """Get the welcome/help text for the TUI (markdown string)."""
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
            "  [cyan]/caveman[/cyan]   — Toggle compression [on|off|lite|full|ultra]\n"
            "  [cyan]/workflow[/cyan]   — Show workflow state\n"
            "  [cyan]/questions [--select --all][/cyan] — Show/answer workflow questions\n"
            "  [cyan]/answer <id|n|next> <text>[/cyan] — Answer a workflow question\n"
            "  [cyan]/decisions[/cyan]  — Show recorded workflow decisions\n"
            "  [cyan]/report[/cyan]          — 협의 결과 개괄 보고서\n"
            "  [cyan]/report save[/cyan]     — 보고서를 Markdown 파일로 저장\n"
            "  [cyan]/packages[/cyan]   — Show workflow work packages\n"
            "  [cyan]/subtasks[/cyan]   — Show delegated subtask reports\n"
            "  [cyan]/resume [n|latest|id][/cyan] — Resume a saved workflow session\n"
            "  [cyan]/execute [text][/cyan] — Execute the current approved blueprint\n"
            "  [cyan]/target [path|clear][/cyan] — Show or set implementation workspace\n"
            "  [cyan]/help[/cyan]       — Show this help\n"
            "  [cyan]/quit[/cyan]       — Exit Trinity\n"
        )

    def get_welcome_renderable(self) -> Group:
        """Get the full welcome display with sacred geometry mandala.

        Returns a Rich renderable combining the geometry animation
        with the welcome text and agent status.
        """
        parts: list = []

        # Sacred geometry mandala (static frame for welcome screen)
        if self._geometry_animator is not None:
            agent_colors = [
                get_theme(name).color
                for name, status in self.agents.items()
                if status.state != AgentTUIState.DISABLED
            ]
            geo_text = self._geometry_animator.render_rich(
                angle=0.0,
                colors=agent_colors[:3] or ["cyan", "green", "magenta"],
            )
            parts.append(geo_text)
            parts.append(Text())

        # Branding
        parts.append(
            Text.assemble(
                Text("🧠 ", style=""),
                Text(f"Trinity v{__version__}", style="bold cyan"),
                Text("  —  ", style="dim"),
                Text("Three minds, one context", style="dim italic"),
            ),
        )
        parts.append(Text())

        # Agent status pills
        agent_parts: list[Text] = []
        for name, status in self.agents.items():
            theme = get_theme(name)
            if status.state == AgentTUIState.DISABLED:
                pill = Text(f"  {name} ⏸  ", style="dim")
            else:
                icon = status.state_icon
                pill = Text(f"  {theme.icon} {name} {icon}  ", style=f"bold {theme.color}")
            agent_parts.append(pill)
        if agent_parts:
            parts.append(Text.assemble(*agent_parts))
            parts.append(Text())

        # Welcome text (commands)
        parts.append(Text.from_markup(self.get_welcome_text()))

        return Group(*parts)
