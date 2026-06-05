"""Deliberation report — structured Rich + Markdown render of workflow sessions.

Produces a composed report from a WorkflowSession and DeliberationResult,
combining overview, consensus, blueprint, decisions, work packages, and
execution results into a single Rich Group for terminal display or a clean
Markdown string for persistence and sharing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.console import Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from trinity.models import ConsensusResult, DeliberationResult
from trinity.tui.theme import get_theme
from trinity.workflow.models import (
    Blueprint,
    DecisionRecord,
    ExecutionResult,
    WorkPackage,
    WorkflowSession,
    WorkflowState,
)

if TYPE_CHECKING:
    from rich.console import RenderableType


# ─── Helpers ────────────────────────────────────────────────────────────────


def _format_timestamp(timestamp: float) -> str:
    """Format a Unix timestamp as a human-readable string."""
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
    except (OSError, ValueError):
        return "unknown"


def _truncate(text: str, limit: int) -> str:
    """Truncate text to *limit* characters, appending ellipsis when needed."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _escape_md_table(text: str) -> str:
    """Escape pipe characters for safe inclusion in Markdown tables."""
    return text.replace("|", "\\|")


# ─── Frozen report section dataclasses ──────────────────────────────────────


@dataclass(frozen=True)
class ReportMeta:
    """Top-level session metadata for the report overview panel."""

    session_id: str
    goal: str
    created_at: str
    agents: tuple[str, ...]
    rounds: int
    duration: str
    tokens: str
    state: str


@dataclass(frozen=True)
class ReportConsensus:
    """Consensus outcome captured at report-build time."""

    reached: bool
    agreement_ratio: str
    summary: str


@dataclass(frozen=True)
class ReportBlueprint:
    """Blueprint summary captured at report-build time."""

    title: str
    summary: str
    architecture_count: int
    risk_count: int
    data_flow_count: int
    acceptance_criteria_count: int


@dataclass(frozen=True)
class ReportPackage:
    """A single work-package row captured for the report."""

    id: str
    title: str
    owner_agent: str
    status: str
    objective: str
    requires_execution: bool


@dataclass(frozen=True)
class ReportExecution:
    """A single execution-result row captured for the report."""

    package_id: str
    agent_name: str
    status: str
    files_count: int
    summary: str


@dataclass(frozen=True)
class ReportDecision:
    """A single resolved decision captured for the report."""

    id: str
    decision: str
    decided_by: str


@dataclass(frozen=True)
class DeliberationReport:
    """Immutable snapshot of a deliberation session ready for rendering.

    Use :class:`DeliberationReportBuilder` to construct instances from live
    workflow objects, then call :meth:`render` for Rich output or
    :meth:`to_markdown` for plain-text persistence.
    """

    meta: ReportMeta
    consensus: ReportConsensus | None
    blueprint: ReportBlueprint | None
    decisions: tuple[ReportDecision, ...]
    packages: tuple[ReportPackage, ...]
    executions: tuple[ReportExecution, ...]

    # ── Rich rendering ──────────────────────────────────────────────────

    def render(self) -> Group:
        """Return a Rich :class:`Group` of panels and tables for console output."""
        renderables: list[RenderableType] = []
        renderables.append(self._render_overview())
        renderables.append(self._render_consensus())
        if self.blueprint is not None:
            renderables.append(self._render_blueprint())
        if self.decisions:
            renderables.append(self._render_decisions())
        if self.packages:
            renderables.append(self._render_packages())
        if self.executions:
            renderables.append(self._render_executions())
        return Group(*renderables)

    # ── Overview ────────────────────────────────────────────────────────

    def _render_overview(self) -> Panel:
        m = self.meta
        agent_labels: list[str] = []
        for name in m.agents:
            theme = get_theme(name)
            agent_labels.append(f"[{theme.color}]{theme.icon} {name}[/{theme.color}]")
        agents_line = ", ".join(agent_labels) if agent_labels else "(none)"

        content = (
            f"[bold]Session[/bold]: {escape(m.session_id)}\n"
            f"[bold]Goal[/bold]: {escape(m.goal)}\n"
            f"[bold]Created[/bold]: {m.created_at}\n"
            f"[bold]State[/bold]: {m.state}\n"
            f"[bold]Agents[/bold]: {agents_line}\n"
            f"[bold]Rounds[/bold]: {m.rounds}\n"
            f"[bold]Duration[/bold]: {m.duration}\n"
            f"[bold]Tokens[/bold]: {m.tokens}"
        )
        return Panel.fit(content, title="Overview", border_style="cyan")

    # ── Consensus ───────────────────────────────────────────────────────

    def _render_consensus(self) -> Panel:
        c = self.consensus
        if c is None:
            return Panel.fit(
                "[dim]No consensus evaluation recorded.[/dim]",
                title="Consensus",
                border_style="dim",
            )
        icon = "✅" if c.reached else "⚠️"
        style = "green" if c.reached else "yellow"
        content = (
            f"[{style} bold]{icon} "
            f"{'Consensus reached' if c.reached else 'No consensus'}"
            f"[/{style} bold]\n"
            f"[bold]Agreement[/bold]: {c.agreement_ratio}\n"
            f"[bold]Summary[/bold]: {escape(c.summary)}"
        )
        return Panel.fit(content, title="Consensus", border_style=style)

    # ── Blueprint ───────────────────────────────────────────────────────

    def _render_blueprint(self) -> Panel:
        bp = self.blueprint
        content = (
            f"[bold]Title[/bold]: {escape(bp.title)}\n"
            f"[bold]Summary[/bold]: {escape(bp.summary)}\n"
            f"[bold]Components[/bold]: {bp.architecture_count}\n"
            f"[bold]Risks[/bold]: {bp.risk_count}\n"
            f"[bold]Data flows[/bold]: {bp.data_flow_count}\n"
            f"[bold]Acceptance criteria[/bold]: {bp.acceptance_criteria_count}"
        )
        return Panel.fit(content, title="Blueprint", border_style="magenta")

    # ── Decisions ───────────────────────────────────────────────────────

    def _render_decisions(self) -> Panel:
        lines: list[str] = []
        for d in self.decisions:
            lines.append(
                f"[cyan]{escape(d.id)}[/cyan] → {escape(d.decision)} "
                f"[dim](by {escape(d.decided_by)})[/dim]"
            )
        return Panel.fit(
            "\n".join(lines),
            title="Decisions",
            border_style="yellow",
        )

    # ── Work Packages ───────────────────────────────────────────────────

    def _render_packages(self) -> Table:
        table = Table(title="Work Packages")
        table.add_column("ID", style="cyan")
        table.add_column("Title")
        table.add_column("Owner")
        table.add_column("Status")
        table.add_column("Objective", max_width=120)

        for pkg in self.packages:
            theme = get_theme(pkg.owner_agent)
            owner = f"[{theme.color}]{theme.icon} {pkg.owner_agent}[/{theme.color}]"
            status_label = pkg.status
            if pkg.requires_execution:
                status_label = f"{status_label} (exec)"
            table.add_row(
                escape(pkg.id),
                escape(pkg.title),
                owner,
                status_label,
                escape(_truncate(pkg.objective, 120)),
            )
        return table

    # ── Execution Results ───────────────────────────────────────────────

    def _render_executions(self) -> Table:
        table = Table(title="Execution Results")
        table.add_column("Package", style="cyan")
        table.add_column("Agent")
        table.add_column("Status")
        table.add_column("Files", justify="right")
        table.add_column("Summary", max_width=120)

        for ex in self.executions:
            theme = get_theme(ex.agent_name)
            agent = f"[{theme.color}]{theme.icon} {ex.agent_name}[/{theme.color}]"
            table.add_row(
                escape(ex.package_id),
                agent,
                ex.status,
                str(ex.files_count),
                escape(_truncate(ex.summary, 120)),
            )
        return table

    # ── Markdown ────────────────────────────────────────────────────────

    def to_markdown(self) -> str:
        """Return a complete Markdown string of the report."""
        lines: list[str] = []
        lines.append(self._md_overview())
        lines.append(self._md_consensus())
        if self.blueprint is not None:
            lines.append(self._md_blueprint())
        if self.decisions:
            lines.append(self._md_decisions())
        if self.packages:
            lines.append(self._md_packages())
        if self.executions:
            lines.append(self._md_executions())
        return "\n".join(lines).rstrip() + "\n"

    def _md_overview(self) -> str:
        m = self.meta
        agents = ", ".join(m.agents) if m.agents else "(none)"
        return (
            f"# Deliberation Report\n"
            f"\n"
            f"**Session**: {m.session_id}  \n"
            f"**Goal**: {m.goal}  \n"
            f"**Created**: {m.created_at}  \n"
            f"**State**: {m.state}  \n"
            f"**Agents**: {agents}  \n"
            f"**Rounds**: {m.rounds}  \n"
            f"**Duration**: {m.duration}  \n"
            f"**Tokens**: {m.tokens}\n"
        )

    def _md_consensus(self) -> str:
        c = self.consensus
        if c is None:
            return "\n## Consensus\n\nNo consensus evaluation recorded.\n"
        icon = "✅" if c.reached else "⚠️"
        label = "Consensus reached" if c.reached else "No consensus"
        return (
            f"\n## Consensus\n"
            f"\n"
            f"{icon} **{label}**  \n"
            f"**Agreement**: {c.agreement_ratio}  \n"
            f"**Summary**: {c.summary}\n"
        )

    def _md_blueprint(self) -> str:
        bp = self.blueprint
        return (
            f"\n## Blueprint\n"
            f"\n"
            f"**Title**: {bp.title}  \n"
            f"**Summary**: {bp.summary}  \n"
            f"**Components**: {bp.architecture_count}  \n"
            f"**Risks**: {bp.risk_count}  \n"
            f"**Data flows**: {bp.data_flow_count}  \n"
            f"**Acceptance criteria**: {bp.acceptance_criteria_count}\n"
        )

    def _md_decisions(self) -> str:
        lines = ["\n## Decisions\n"]
        for d in self.decisions:
            lines.append(f"- **{d.id}**: {d.decision} *(by {d.decided_by})*")
        lines.append("")
        return "\n".join(lines)

    def _md_packages(self) -> str:
        lines = [
            "\n## Work Packages\n",
            "| ID | Title | Owner | Status | Objective |",
            "|----|-------|-------|--------|-----------|",
        ]
        for pkg in self.packages:
            status_label = pkg.status
            if pkg.requires_execution:
                status_label = f"{status_label} (exec)"
            lines.append(
                f"| {_escape_md_table(pkg.id)} | {_escape_md_table(pkg.title)} "
                f"| {_escape_md_table(pkg.owner_agent)} "
                f"| {_escape_md_table(status_label)} "
                f"| {_escape_md_table(_truncate(pkg.objective, 120))} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _md_executions(self) -> str:
        lines = [
            "\n## Execution Results\n",
            "| Package | Agent | Status | Files | Summary |",
            "|---------|-------|--------|-------|---------|",
        ]
        for ex in self.executions:
            lines.append(
                f"| {_escape_md_table(ex.package_id)} "
                f"| {_escape_md_table(ex.agent_name)} "
                f"| {_escape_md_table(ex.status)} | {ex.files_count} "
                f"| {_escape_md_table(_truncate(ex.summary, 120))} |"
            )
        lines.append("")
        return "\n".join(lines)


# ─── Builder ────────────────────────────────────────────────────────────────


class DeliberationReportBuilder:
    """Constructs a :class:`DeliberationReport` from live workflow objects.

    Usage::

        report = DeliberationReportBuilder(session, result).build()
        console.print(report.render())
        path.write_text(report.to_markdown())
    """

    def __init__(
        self,
        session: WorkflowSession,
        result: DeliberationResult | None = None,
    ) -> None:
        self._session = session
        self._result = result

    def build(self) -> DeliberationReport:
        """Assemble a frozen :class:`DeliberationReport`."""
        return DeliberationReport(
            meta=self._build_meta(),
            consensus=self._build_consensus(),
            blueprint=self._build_blueprint(),
            decisions=self._build_decisions(),
            packages=self._build_packages(),
            executions=self._build_executions(),
        )

    # ── Section builders ────────────────────────────────────────────────

    def _build_meta(self) -> ReportMeta:
        s = self._session
        r = self._result
        return ReportMeta(
            session_id=s.id,
            goal=s.goal or "(none)",
            created_at=_format_timestamp(s.created_at),
            agents=tuple(s.active_agents),
            rounds=r.rounds_completed if r else s.current_round,
            duration=f"{r.duration_seconds:.1f}s" if r else "N/A",
            tokens=f"{r.total_tokens_used:,}" if r else "N/A",
            state=s.state.value,
        )

    def _build_consensus(self) -> ReportConsensus | None:
        if self._result is None or self._result.consensus is None:
            return None
        c = self._result.consensus
        ratio = (
            f"{c.agreement_count}/{c.total_agents}"
            if c.total_agents > 0
            else "0/0"
        )
        return ReportConsensus(
            reached=c.reached,
            agreement_ratio=ratio,
            summary=c.summary or "(no summary)",
        )

    def _build_blueprint(self) -> ReportBlueprint | None:
        bp = self._session.blueprint
        if bp is None:
            return None
        return ReportBlueprint(
            title=bp.title or "(untitled)",
            summary=bp.summary or "(no summary)",
            architecture_count=len(bp.architecture),
            risk_count=len(bp.risks),
            data_flow_count=len(bp.data_flow),
            acceptance_criteria_count=len(bp.acceptance_criteria),
        )

    def _build_decisions(self) -> tuple[ReportDecision, ...]:
        return tuple(
            ReportDecision(
                id=d.id,
                decision=d.decision,
                decided_by=d.decided_by,
            )
            for d in self._session.decisions
        )

    def _build_packages(self) -> tuple[ReportPackage, ...]:
        return tuple(
            ReportPackage(
                id=pkg.id,
                title=pkg.title,
                owner_agent=pkg.owner_agent,
                status=pkg.status.value,
                objective=pkg.objective,
                requires_execution=pkg.requires_execution,
            )
            for pkg in self._session.work_packages
        )

    def _build_executions(self) -> tuple[ReportExecution, ...]:
        return tuple(
            ReportExecution(
                package_id=ex.package_id,
                agent_name=ex.agent_name,
                status=ex.status.value,
                files_count=len(ex.files_changed),
                summary=ex.summary,
            )
            for ex in self._session.execution_results
        )
