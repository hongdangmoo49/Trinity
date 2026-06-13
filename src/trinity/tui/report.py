"""Deliberation report — structured Rich + Markdown render of workflow sessions.

Produces a composed report from a WorkflowSession and DeliberationResult,
combining overview, consensus, blueprint, decisions, work packages, and
execution results into a single Rich Group for terminal display or a clean
Markdown string for persistence and sharing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rich.console import Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from trinity.models import DeliberationResult
from trinity.tui.theme import get_theme
from trinity.workflow.models import (
    Blueprint,
    WorkStatus,
    WorkflowSession,
)

if TYPE_CHECKING:
    from rich.console import RenderableType


# ─── Helpers ────────────────────────────────────────────────────────────────

from trinity.tui.formatting import format_timestamp

_MD_SPECIAL_CHARS = "\\`*_{}[]<>()#+-.!|"
_EXECUTION_REPORT_EVENTS = {
    "target_workspace_selected",
    "execution_enabled",
    "implementation_requested",
    "execution_run_started",
    "execution_batch_planned",
    "work_package_started",
    "work_package_completed",
    "execution_result_recorded",
    "execution_interrupted_detected",
    "work_package_retry_requested",
    "work_package_retry_skipped",
    "execution_recovery_action",
    "review_result_recorded",
    "work_package_repair_requested",
    "work_package_repair_blocked",
    "work_package_repair_stopped",
    "state_changed",
    "workflow_continued",
}


def _truncate(text: str, limit: int) -> str:
    """Truncate text to *limit* characters, appending ellipsis when needed."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _escape_md_table(text: str) -> str:
    """Normalize and escape text for safe inclusion in Markdown tables."""
    normalized = " ".join(str(text).split())
    return normalized.replace("|", "\\|")


def _escape_md_inline(text: str) -> str:
    """Normalize and escape Markdown inline syntax from user-controlled text."""
    normalized = " ".join(str(text).split())
    return "".join(
        f"\\{char}" if char in _MD_SPECIAL_CHARS else char
        for char in normalized
    )


def _md_block(text: str, language: str = "text") -> str:
    """Return text in a fenced Markdown block, extending fences when needed."""
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    fence = "```"
    while fence in normalized:
        fence += "`"
    return f"{fence}{language}\n{normalized}\n{fence}"


def _json_block(data: Mapping[str, object]) -> str:
    return _md_block(
        json.dumps(dict(data), ensure_ascii=False, indent=2, default=str),
        "json",
    )


def _md_list_section(title: str, items: tuple[str, ...]) -> list[str]:
    if not items:
        return []
    lines = ["", f"### {title}", ""]
    lines.extend(f"- {_escape_md_inline(item)}" for item in items)
    return lines


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
    architecture: tuple[str, ...]
    data_flow: tuple[str, ...]
    external_dependencies: tuple[str, ...]
    risks: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
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
    attempt_chain: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReportDecision:
    """A single resolved decision captured for the report."""

    id: str
    decision: str
    decided_by: str


@dataclass(frozen=True)
class ReportProvider:
    """Provider runtime/session metadata captured for audit output."""

    name: str
    provider: str
    configured_model: str
    actual_model: str
    context_window: int
    budget_source: str
    provider_session_id: str
    session_kind: str
    cwd: str


@dataclass(frozen=True)
class ReportConversationMessage:
    """One central-agent conversation or command transcript item."""

    timestamp: float
    role: str
    channel: str
    title: str
    body: str
    command: str = ""
    related_ids: tuple[str, ...] = ()
    truncated: bool = False


@dataclass(frozen=True)
class ReportExecutionEvent:
    """A workflow/execution event normalized for report output."""

    timestamp: float
    event: str
    state: str
    run_id: str
    package_id: str
    agent: str
    status: str
    target_workspace: str
    summary: str
    raw_data: Mapping[str, object]


@dataclass(frozen=True)
class ReportReview:
    """A persisted review result summarized for report output."""

    review_package_id: str
    package_id: str
    reviewer_agent: str
    target_agent: str
    status: str
    severity: str
    scope: str
    summary: str
    required_changes: tuple[str, ...]
    findings: tuple[str, ...]


@dataclass(frozen=True)
class ReportRepair:
    """Review-repair state summarized for report output."""

    package_id: str
    status: str
    attempt_count: int
    blocked_reason: str
    summary: str
    notes: tuple[str, ...]


@dataclass(frozen=True)
class ReportRecovery:
    """Execution recovery state summarized for report output."""

    run_id: str
    state: str
    target_workspace: str
    running_packages: tuple[str, ...]
    done_packages: tuple[str, ...]
    retry_candidates: tuple[str, ...]
    interrupted_reason: str


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
    target_workspace: str = ""
    providers: tuple[ReportProvider, ...] = ()
    conversation: tuple[ReportConversationMessage, ...] = ()
    execution_events: tuple[ReportExecutionEvent, ...] = ()
    reviews: tuple[ReportReview, ...] = ()
    repairs: tuple[ReportRepair, ...] = ()
    recovery: ReportRecovery | None = None

    # ── Rich rendering ──────────────────────────────────────────────────

    def render(self) -> Group:
        """Return a Rich :class:`Group` of panels and tables for console output."""
        renderables: list[RenderableType] = []
        renderables.append(self._render_overview())
        if self.providers:
            renderables.append(self._render_providers())
        renderables.append(self._render_consensus())
        if self.blueprint is not None:
            renderables.append(self._render_blueprint())
        if self.decisions:
            renderables.append(self._render_decisions())
        if self.packages:
            renderables.append(self._render_packages())
        if self.executions:
            renderables.append(self._render_executions())
        if self.execution_events:
            renderables.append(self._render_execution_events())
        if self.reviews:
            renderables.append(self._render_reviews())
        if self.repairs:
            renderables.append(self._render_repairs())
        if self.recovery is not None:
            renderables.append(self._render_recovery())
        if self.conversation:
            renderables.append(self._render_conversation())
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
            f"[bold]Target[/bold]: {escape(self.target_workspace or '(not set)')}\n"
            f"[bold]Agents[/bold]: {agents_line}\n"
            f"[bold]Rounds[/bold]: {m.rounds}\n"
            f"[bold]Duration[/bold]: {m.duration}\n"
            f"[bold]Tokens[/bold]: {m.tokens}"
        )
        return Panel.fit(content, title="Overview", border_style="cyan")

    def _render_providers(self) -> Table:
        table = Table(title="Providers")
        table.add_column("Agent")
        table.add_column("Provider")
        table.add_column("Model")
        table.add_column("Context", justify="right")
        table.add_column("Session")

        for provider in self.providers:
            model = provider.actual_model or provider.configured_model or "default"
            context = f"{provider.context_window:,}" if provider.context_window else "-"
            session = provider.provider_session_id[:18] if provider.provider_session_id else "-"
            table.add_row(
                escape(provider.name),
                escape(provider.provider or "-"),
                escape(model),
                context,
                escape(session),
            )
        return table

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
        table.add_column("Attempts", justify="right")
        table.add_column("Summary", max_width=120)

        for ex in self.executions:
            theme = get_theme(ex.agent_name)
            agent = f"[{theme.color}]{theme.icon} {ex.agent_name}[/{theme.color}]"
            table.add_row(
                escape(ex.package_id),
                agent,
                ex.status,
                str(ex.files_count),
                str(len(ex.attempt_chain)) if ex.attempt_chain else "-",
                escape(_truncate(ex.summary, 120)),
            )
        return table

    def _render_execution_events(self) -> Table:
        table = Table(title="Execution Timeline")
        table.add_column("Time")
        table.add_column("Event")
        table.add_column("Package")
        table.add_column("Agent")
        table.add_column("Status")
        table.add_column("Summary", max_width=120)

        for event in self.execution_events[-80:]:
            table.add_row(
                format_timestamp(event.timestamp, "%H:%M:%S") if event.timestamp else "-",
                escape(event.event),
                escape(event.package_id or "-"),
                escape(event.agent or "-"),
                escape(event.status or event.state or "-"),
                escape(_truncate(event.summary, 120)),
            )
        return table

    def _render_reviews(self) -> Table:
        table = Table(title="Reviews")
        table.add_column("Review")
        table.add_column("Package")
        table.add_column("Reviewer")
        table.add_column("Status")
        table.add_column("Severity")
        table.add_column("Summary", max_width=120)

        for review in self.reviews:
            table.add_row(
                escape(review.review_package_id or "-"),
                escape(review.package_id or "-"),
                escape(review.reviewer_agent or "-"),
                escape(review.status or "-"),
                escape(review.severity or "-"),
                escape(_truncate(review.summary, 120)),
            )
        return table

    def _render_repairs(self) -> Table:
        table = Table(title="Review Repairs")
        table.add_column("Package")
        table.add_column("Status")
        table.add_column("Attempts", justify="right")
        table.add_column("Summary", max_width=120)

        for repair in self.repairs:
            table.add_row(
                escape(repair.package_id or "-"),
                escape(repair.status or "-"),
                str(repair.attempt_count),
                escape(_truncate(repair.summary, 120)),
            )
        return table

    def _render_recovery(self) -> Panel:
        recovery = self.recovery
        content = (
            f"[bold]Run[/bold]: {escape(recovery.run_id or '(unknown)')}\n"
            f"[bold]State[/bold]: {escape(recovery.state or '(unknown)')}\n"
            f"[bold]Target[/bold]: {escape(recovery.target_workspace or '(not set)')}\n"
            f"[bold]Running[/bold]: {escape(', '.join(recovery.running_packages) or '(none)')}\n"
            f"[bold]Retry candidates[/bold]: {escape(', '.join(recovery.retry_candidates) or '(none)')}\n"
            f"[bold]Done[/bold]: {escape(', '.join(recovery.done_packages) or '(none)')}"
        )
        if recovery.interrupted_reason:
            content = f"{content}\n[bold]Reason[/bold]: {escape(recovery.interrupted_reason)}"
        return Panel.fit(content, title="Execution Recovery", border_style="yellow")

    def _render_conversation(self) -> Panel:
        lines: list[str] = []
        for message in self.conversation[-12:]:
            timestamp = format_timestamp(message.timestamp, "%H:%M:%S") if message.timestamp else "-"
            title = message.title or message.command or message.role
            body = _truncate(" ".join(message.body.split()), 160)
            lines.append(
                f"[dim]{timestamp}[/dim] "
                f"[cyan]{escape(message.role or 'entry')}[/cyan] "
                f"{escape(title)}: {escape(body)}"
            )
        return Panel.fit(
            "\n".join(lines),
            title="Central Agent Conversation",
            border_style="blue",
        )

    # ── Markdown ────────────────────────────────────────────────────────

    def to_markdown(self) -> str:
        """Return a complete Markdown string of the report."""
        lines: list[str] = []
        lines.append(self._md_overview())
        if self.providers:
            lines.append(self._md_providers())
        lines.append(self._md_consensus())
        if self.blueprint is not None:
            lines.append(self._md_blueprint())
        if self.decisions:
            lines.append(self._md_decisions())
        if self.packages:
            lines.append(self._md_packages())
        if self.executions:
            lines.append(self._md_executions())
        if self.execution_events:
            lines.append(self._md_execution_events())
        if self.reviews:
            lines.append(self._md_reviews())
        if self.repairs:
            lines.append(self._md_repairs())
        if self.recovery is not None:
            lines.append(self._md_recovery())
        if self.conversation:
            lines.append(self._md_conversation())
        return "\n".join(lines).rstrip() + "\n"

    def _md_overview(self) -> str:
        m = self.meta
        agents = ", ".join(_escape_md_inline(agent) for agent in m.agents) if m.agents else "(none)"
        return (
            f"# Deliberation Report\n"
            f"\n"
            f"**Session**: {_escape_md_inline(m.session_id)}  \n"
            f"**Goal**: {_escape_md_inline(m.goal)}  \n"
            f"**Created**: {_escape_md_inline(m.created_at)}  \n"
            f"**State**: {_escape_md_inline(m.state)}  \n"
            f"**Target workspace**: {_escape_md_inline(self.target_workspace or '(not set)')}  \n"
            f"**Agents**: {agents}  \n"
            f"**Rounds**: {m.rounds}  \n"
            f"**Duration**: {_escape_md_inline(m.duration)}  \n"
            f"**Tokens**: {_escape_md_inline(m.tokens)}\n"
        )

    def _md_providers(self) -> str:
        lines = [
            "\n## Providers\n",
            "| Agent | Provider | Model | Context | Session | CWD |",
            "|-------|----------|-------|---------|---------|-----|",
        ]
        for provider in self.providers:
            model = provider.actual_model or provider.configured_model or "default"
            context = f"{provider.context_window:,}" if provider.context_window else "unknown"
            session = provider.provider_session_id[:24] if provider.provider_session_id else "none"
            lines.append(
                f"| {_escape_md_table(provider.name)} "
                f"| {_escape_md_table(provider.provider or 'unknown')} "
                f"| {_escape_md_table(model)} "
                f"| {_escape_md_table(context)} "
                f"| {_escape_md_table(session)} "
                f"| {_escape_md_table(provider.cwd or '-')} |"
            )
        lines.append("")
        return "\n".join(lines)

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
            f"**Agreement**: {_escape_md_inline(c.agreement_ratio)}  \n"
            f"**Summary**: {_escape_md_inline(c.summary)}\n"
        )

    def _md_blueprint(self) -> str:
        bp = self.blueprint
        lines = [
            "\n## Blueprint\n",
            f"**Title**: {_escape_md_inline(bp.title)}  ",
            f"**Summary**: {_escape_md_inline(bp.summary)}  ",
            f"**Components**: {bp.architecture_count}  ",
            f"**Risks**: {bp.risk_count}  ",
            f"**Data flows**: {bp.data_flow_count}  ",
            f"**Acceptance criteria**: {bp.acceptance_criteria_count}",
        ]
        lines.extend(_md_list_section("Architecture", bp.architecture))
        lines.extend(_md_list_section("Data Flow", bp.data_flow))
        lines.extend(_md_list_section("External Dependencies", bp.external_dependencies))
        lines.extend(_md_list_section("Risks", bp.risks))
        lines.extend(_md_list_section("Acceptance Criteria", bp.acceptance_criteria))
        lines.append("")
        return "\n".join(lines)

    def _md_decisions(self) -> str:
        lines = ["\n## Decisions\n"]
        for d in self.decisions:
            lines.append(
                f"- **{_escape_md_table(d.id)}**: {_escape_md_inline(d.decision)} "
                f"*(by {_escape_md_inline(d.decided_by)})*"
            )
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
            "| Package | Agent | Status | Files | Attempts | Summary |",
            "|---------|-------|--------|-------|----------|---------|",
        ]
        for ex in self.executions:
            lines.append(
                f"| {_escape_md_table(ex.package_id)} "
                f"| {_escape_md_table(ex.agent_name)} "
                f"| {_escape_md_table(ex.status)} | {ex.files_count} "
                f"| {len(ex.attempt_chain) if ex.attempt_chain else '-'} "
                f"| {_escape_md_table(_truncate(ex.summary, 120))} |"
            )
        for ex in self.executions:
            if not ex.attempt_chain:
                continue
            lines.extend(
                [
                    "",
                    f"### Attempt Chain - {_escape_md_inline(ex.package_id)}",
                    "",
                ]
            )
            lines.extend(f"- {_escape_md_inline(item)}" for item in ex.attempt_chain)
        lines.append("")
        return "\n".join(lines)

    def _md_execution_events(self) -> str:
        lines = [
            "\n## Execution Timeline\n",
            "| Time | Event | Package | Agent | Status | Summary |",
            "|------|-------|---------|-------|--------|---------|",
        ]
        for event in self.execution_events:
            timestamp = (
                format_timestamp(event.timestamp, "%Y-%m-%d %H:%M:%S")
                if event.timestamp
                else ""
            )
            lines.append(
                f"| {_escape_md_table(timestamp)} "
                f"| {_escape_md_table(event.event)} "
                f"| {_escape_md_table(event.package_id or '-')} "
                f"| {_escape_md_table(event.agent or '-')} "
                f"| {_escape_md_table(event.status or event.state or '-')} "
                f"| {_escape_md_table(_truncate(event.summary, 140))} |"
            )
        lines.extend(["", "## Execution Event Details", ""])
        for event in self.execution_events:
            timestamp = (
                format_timestamp(event.timestamp, "%Y-%m-%d %H:%M:%S")
                if event.timestamp
                else "unknown time"
            )
            lines.extend(
                [
                    f"### {_escape_md_inline(event.event)} - {_escape_md_inline(timestamp)}",
                    "",
                    _json_block(event.raw_data),
                    "",
                ]
            )
        return "\n".join(lines)

    def _md_reviews(self) -> str:
        lines = [
            "\n## Reviews\n",
            "| Review | Package | Reviewer | Target | Status | Severity | Summary |",
            "|--------|---------|----------|--------|--------|----------|---------|",
        ]
        for review in self.reviews:
            lines.append(
                f"| {_escape_md_table(review.review_package_id or '-')} "
                f"| {_escape_md_table(review.package_id or '-')} "
                f"| {_escape_md_table(review.reviewer_agent or '-')} "
                f"| {_escape_md_table(review.target_agent or '-')} "
                f"| {_escape_md_table(review.status or '-')} "
                f"| {_escape_md_table(review.severity or '-')} "
                f"| {_escape_md_table(_truncate(review.summary, 140))} |"
            )
            details = list(review.required_changes or review.findings)
            if details:
                lines.extend(
                    [
                        "",
                        f"### Review Details - {_escape_md_inline(review.review_package_id or review.package_id)}",
                        "",
                    ]
                )
                lines.extend(f"- {_escape_md_inline(item)}" for item in details)
        lines.append("")
        return "\n".join(lines)

    def _md_repairs(self) -> str:
        lines = [
            "\n## Review Repairs\n",
            "| Package | Status | Attempts | Summary |",
            "|---------|--------|----------|---------|",
        ]
        for repair in self.repairs:
            lines.append(
                f"| {_escape_md_table(repair.package_id or '-')} "
                f"| {_escape_md_table(repair.status or '-')} "
                f"| {repair.attempt_count} "
                f"| {_escape_md_table(_truncate(repair.summary, 140))} |"
            )
            if repair.notes:
                lines.extend(
                    [
                        "",
                        f"### Repair Notes - {_escape_md_inline(repair.package_id)}",
                        "",
                    ]
                )
                lines.extend(f"- {_escape_md_inline(note)}" for note in repair.notes)
        lines.append("")
        return "\n".join(lines)

    def _md_recovery(self) -> str:
        recovery = self.recovery
        lines = [
            "\n## Execution Recovery\n",
            f"- Run: {_escape_md_inline(recovery.run_id or '(unknown)')}",
            f"- State: {_escape_md_inline(recovery.state or '(unknown)')}",
            f"- Target: {_escape_md_inline(recovery.target_workspace or '(not set)')}",
            f"- Running packages: {_escape_md_inline(', '.join(recovery.running_packages) or '(none)')}",
            f"- Retry candidates: {_escape_md_inline(', '.join(recovery.retry_candidates) or '(none)')}",
            f"- Done packages: {_escape_md_inline(', '.join(recovery.done_packages) or '(none)')}",
        ]
        if recovery.interrupted_reason:
            lines.append(f"- Reason: {_escape_md_inline(recovery.interrupted_reason)}")
        lines.append("")
        return "\n".join(lines)

    def _md_conversation(self) -> str:
        lines = ["\n## Central Agent Conversation\n"]
        for message in self.conversation:
            timestamp = (
                format_timestamp(message.timestamp, "%Y-%m-%d %H:%M:%S")
                if message.timestamp
                else "unknown time"
            )
            title = message.title or message.command or message.role
            heading = (
                f"### {_escape_md_inline(timestamp)} - "
                f"{_escape_md_inline(message.role or 'entry')} - "
                f"{_escape_md_inline(title)}"
            )
            lines.extend([heading, ""])
            meta: list[str] = []
            if message.channel:
                meta.append(f"channel={message.channel}")
            if message.command:
                meta.append(f"command={message.command}")
            if message.related_ids:
                meta.append(f"related={', '.join(message.related_ids)}")
            if message.truncated:
                meta.append("truncated=true")
            if meta:
                lines.extend([f"_Metadata: {_escape_md_inline('; '.join(meta))}_", ""])
            lines.extend([_md_block(message.body), ""])
        return "\n".join(lines).rstrip() + "\n"


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
        *,
        events: Sequence[Mapping[str, Any]] = (),
        snapshot: Any | None = None,
    ) -> None:
        if not isinstance(session, WorkflowSession):
            raise ValueError("DeliberationReportBuilder requires a WorkflowSession.")
        self._session = session
        self._result = result
        self._events = tuple(
            dict(event) for event in events if isinstance(event, Mapping)
        )
        self._snapshot = snapshot

    def build(self) -> DeliberationReport:
        """Assemble a frozen :class:`DeliberationReport`."""
        return DeliberationReport(
            meta=self._build_meta(),
            consensus=self._build_consensus(),
            blueprint=self._build_blueprint(),
            decisions=self._build_decisions(),
            packages=self._build_packages(),
            executions=self._build_executions(),
            target_workspace=str(self._session.target_workspace or ""),
            providers=self._build_providers(),
            conversation=self._build_conversation(),
            execution_events=self._build_execution_events(),
            reviews=self._build_reviews(),
            repairs=self._build_repairs(),
            recovery=self._build_recovery(),
        )

    # ── Section builders ────────────────────────────────────────────────

    def _build_meta(self) -> ReportMeta:
        s = self._session
        r = self._result
        return ReportMeta(
            session_id=s.id,
            goal=s.goal or "(none)",
            created_at=format_timestamp(s.created_at, "%Y-%m-%d %H:%M:%S"),
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
            architecture=tuple(
                self._format_architecture_component(component)
                for component in bp.architecture
            ),
            data_flow=tuple(bp.data_flow),
            external_dependencies=tuple(bp.external_dependencies),
            risks=tuple(self._format_risk(risk) for risk in bp.risks),
            acceptance_criteria=tuple(bp.acceptance_criteria),
            architecture_count=len(bp.architecture),
            risk_count=len(bp.risks),
            data_flow_count=len(bp.data_flow),
            acceptance_criteria_count=len(bp.acceptance_criteria),
        )

    def _build_providers(self) -> tuple[ReportProvider, ...]:
        session_refs = list(self._session.provider_sessions.values())
        runtime_models = list(self._session.runtime_models.values())
        refs_by_agent: dict[str, Any] = {}
        for ref in session_refs:
            name = str(getattr(ref, "agent_name", "") or "").strip()
            if name and name not in refs_by_agent:
                refs_by_agent[name] = ref
        models_by_agent = {
            str(getattr(model, "agent_name", "") or "").strip(): model
            for model in runtime_models
            if str(getattr(model, "agent_name", "") or "").strip()
        }

        ordered_names: list[str] = []
        for name in self._session.active_agents:
            if name not in ordered_names:
                ordered_names.append(name)
        for name in sorted(set(refs_by_agent) | set(models_by_agent)):
            if name not in ordered_names:
                ordered_names.append(name)

        providers: list[ReportProvider] = []
        for name in ordered_names:
            ref = refs_by_agent.get(name)
            model = models_by_agent.get(name)
            providers.append(
                ReportProvider(
                    name=name,
                    provider=str(
                        getattr(model, "provider", "")
                        or getattr(ref, "provider", "")
                        or ""
                    ),
                    configured_model=str(
                        getattr(model, "configured_model", "")
                        or getattr(ref, "configured_model", "")
                        or ""
                    ),
                    actual_model=str(
                        getattr(model, "actual_model", "")
                        or getattr(model, "model_label", "")
                        or getattr(ref, "resolved_model", "")
                        or ""
                    ),
                    context_window=int(getattr(model, "context_window", 0) or 0),
                    budget_source=str(getattr(model, "budget_source", "") or ""),
                    provider_session_id=str(
                        getattr(ref, "provider_session_id", "") or ""
                    ),
                    session_kind=str(getattr(ref, "session_kind", "") or ""),
                    cwd=str(getattr(ref, "cwd", "") or ""),
                )
            )
        return tuple(providers)

    def _build_conversation(self) -> tuple[ReportConversationMessage, ...]:
        messages: list[ReportConversationMessage] = []
        for event in self._events:
            message = self._conversation_message_from_event(event)
            if message is not None:
                messages.append(message)

        snapshot = self._snapshot
        if snapshot is not None:
            messages.extend(self._conversation_from_snapshot(snapshot, messages))

        messages.extend(self._conversation_from_session_questions(messages))
        messages.extend(self._conversation_from_session_decisions(messages))

        if not any(
            message.role == "central"
            and message.title == "Central Agent Response"
            for message in messages
        ):
            fallback = self._central_response_from_session()
            if fallback is not None:
                messages.append(fallback)

        return tuple(messages)

    def _conversation_message_from_event(
        self,
        event: Mapping[str, Any],
    ) -> ReportConversationMessage | None:
        name = str(event.get("event", "") or "")
        data = self._event_data(event)
        timestamp = self._event_timestamp(event)

        if name == "central_conversation_recorded":
            return ReportConversationMessage(
                timestamp=timestamp,
                role=str(data.get("role", "") or "central"),
                channel=str(data.get("channel", "") or "nexus"),
                title=str(data.get("title", "") or "Central Agent"),
                body=str(data.get("body", "") or ""),
                command=str(data.get("command", "") or ""),
                related_ids=self._event_str_tuple(data.get("related_ids")),
                truncated=bool(data.get("truncated", False)),
            )

        if name == "workflow_started":
            return ReportConversationMessage(
                timestamp=timestamp,
                role="user",
                channel="start",
                title="Workflow Started",
                body=str(data.get("goal", "") or self._session.goal or ""),
            )

        if name == "workflow_continued":
            return ReportConversationMessage(
                timestamp=timestamp,
                role="user",
                channel="nexus",
                title="Workflow Continued",
                body=str(data.get("instruction", "") or ""),
            )

        if name in {"decision_recorded", "decision_replaced"}:
            question_id = str(data.get("question_id", "") or "")
            decision = str(data.get("decision", "") or "")
            title = "Decision Replaced" if name == "decision_replaced" else "Decision Recorded"
            body = f"{question_id}\n\n{decision}" if question_id else decision
            return ReportConversationMessage(
                timestamp=timestamp,
                role="user",
                channel="nexus",
                title=title,
                body=body,
                related_ids=tuple(item for item in (question_id,) if item),
            )

        if name in {"implementation_requested", "execution_enabled"}:
            title = (
                "Implementation Requested"
                if name == "implementation_requested"
                else "Execution Enabled"
            )
            packages = self._event_str_tuple(data.get("work_packages"))
            body_parts = []
            instruction = str(data.get("instruction", "") or "").strip()
            if instruction:
                body_parts.append(instruction)
            if packages:
                body_parts.append(f"Work packages: {', '.join(packages)}")
            target = str(data.get("target_workspace", "") or "").strip()
            if target:
                body_parts.append(f"Target workspace: {target}")
            return ReportConversationMessage(
                timestamp=timestamp,
                role="user",
                channel="nexus",
                title=title,
                body="\n".join(body_parts) or title,
                related_ids=packages,
            )

        if name == "post_review_follow_up_requested":
            related_ids = self._event_str_tuple(data.get("related_wp_ids"))
            body = str(data.get("summary") or data.get("title") or data.get("source") or "")
            return ReportConversationMessage(
                timestamp=timestamp,
                role="user",
                channel="nexus",
                title="Post-review Follow-up Requested",
                body=body or "Post-review follow-up requested.",
                related_ids=related_ids,
            )

        return None

    def _conversation_from_session_questions(
        self,
        existing: Sequence[ReportConversationMessage],
    ) -> list[ReportConversationMessage]:
        existing_related = {
            related
            for message in existing
            for related in message.related_ids
        }
        messages: list[ReportConversationMessage] = []
        for question in self._session.pending_questions:
            if question.id in existing_related:
                continue
            lines = [question.question]
            if question.options:
                lines.extend(["", "Options:"])
                lines.extend(f"{index}. {option}" for index, option in enumerate(question.options, 1))
            if question.recommended_option:
                lines.extend(["", f"Recommended: {question.recommended_option}"])
            if question.rationale:
                lines.extend(["", f"Rationale: {question.rationale}"])
            messages.append(
                ReportConversationMessage(
                    timestamp=self._session.updated_at or self._session.created_at,
                    role="central",
                    channel="nexus",
                    title=f"Question {question.id}",
                    body="\n".join(lines),
                    related_ids=(question.id,),
                )
            )
        return messages

    def _conversation_from_session_decisions(
        self,
        existing: Sequence[ReportConversationMessage],
    ) -> list[ReportConversationMessage]:
        existing_related = {
            related
            for message in existing
            for related in message.related_ids
        }
        messages: list[ReportConversationMessage] = []
        for decision in self._session.decisions:
            related_id = decision.question_id or decision.id
            if related_id in existing_related:
                continue
            messages.append(
                ReportConversationMessage(
                    timestamp=decision.timestamp,
                    role="user",
                    channel="nexus",
                    title="Decision Recorded",
                    body=decision.decision,
                    related_ids=tuple(item for item in (related_id,) if item),
                )
            )
        return messages

    def _conversation_from_snapshot(
        self,
        snapshot: Any,
        existing: Sequence[ReportConversationMessage],
    ) -> list[ReportConversationMessage]:
        messages: list[ReportConversationMessage] = []
        existing_keys = {
            (message.command, message.title, message.body)
            for message in existing
        }
        timestamp = self._session.updated_at or self._session.created_at

        synthesis = getattr(snapshot, "synthesis", None)
        synthesis_summary = str(getattr(synthesis, "summary", "") or "")
        if synthesis_summary:
            key = ("", "Synthesis", synthesis_summary)
            if key not in existing_keys:
                messages.append(
                    ReportConversationMessage(
                        timestamp=timestamp,
                        role="central",
                        channel="nexus",
                        title="Synthesis",
                        body=synthesis_summary,
                    )
                )

        central_blueprint = str(getattr(snapshot, "central_blueprint", "") or "")
        if central_blueprint:
            key = ("", "Central Agent Response", central_blueprint)
            if key not in existing_keys:
                messages.append(
                    ReportConversationMessage(
                        timestamp=timestamp,
                        role="central",
                        channel="nexus",
                        title="Central Agent Response",
                        body=central_blueprint,
                    )
                )

        for item in getattr(snapshot, "local_commands", []) or []:
            command = str(getattr(item, "command", "") or "")
            title = str(getattr(item, "title", "") or "Local Command")
            body = str(getattr(item, "body", "") or "")
            key = (command, title, body)
            if key in existing_keys:
                continue
            messages.append(
                ReportConversationMessage(
                    timestamp=timestamp,
                    role="tool",
                    channel="local_command",
                    title=title,
                    body=body,
                    command=command,
                )
            )
        return messages

    def _central_response_from_session(self) -> ReportConversationMessage | None:
        if self._session.blueprint is None:
            return None
        body = self._blueprint_body(self._session.blueprint)
        related_ids = tuple(package.id for package in self._session.work_packages)
        return ReportConversationMessage(
            timestamp=self._session.updated_at or self._session.created_at,
            role="central",
            channel="nexus",
            title="Central Agent Response",
            body=body,
            related_ids=related_ids,
        )

    def _build_execution_events(self) -> tuple[ReportExecutionEvent, ...]:
        return tuple(
            normalized
            for event in self._events
            if str(event.get("event", "") or "") in _EXECUTION_REPORT_EVENTS
            for normalized in (self._execution_event_from_event(event),)
            if normalized is not None
        )

    def _execution_event_from_event(
        self,
        event: Mapping[str, Any],
    ) -> ReportExecutionEvent | None:
        data = self._event_data(event)
        name = str(event.get("event", "") or "")
        run = self._session.execution_run if isinstance(self._session.execution_run, dict) else {}
        return ReportExecutionEvent(
            timestamp=self._event_timestamp(event),
            event=name,
            state=str(event.get("state", "") or ""),
            run_id=str(data.get("run_id") or run.get("run_id", "") or ""),
            package_id=str(data.get("package_id", "") or ""),
            agent=str(
                data.get("agent")
                or data.get("reviewer")
                or data.get("target")
                or ""
            ),
            status=str(data.get("status", "") or ""),
            target_workspace=str(
                data.get("target_workspace")
                or self._session.target_workspace
                or ""
            ),
            summary=self._event_summary(name, data),
            raw_data=data,
        )

    def _build_reviews(self) -> tuple[ReportReview, ...]:
        reviews: list[ReportReview] = []
        for item in self._session.review_results:
            if not isinstance(item, Mapping):
                continue
            reviews.append(
                ReportReview(
                    review_package_id=str(item.get("review_package_id", "") or ""),
                    package_id=str(item.get("package_id", "") or ""),
                    reviewer_agent=str(item.get("reviewer_agent", "") or ""),
                    target_agent=str(item.get("target_agent", "") or ""),
                    status=str(item.get("status", "") or ""),
                    severity=str(item.get("severity", "") or ""),
                    scope=str(item.get("scope", "") or ""),
                    summary=str(item.get("summary", "") or ""),
                    required_changes=self._event_str_tuple(item.get("required_changes")),
                    findings=self._event_str_tuple(item.get("findings")),
                )
            )
        return tuple(reviews)

    def _build_repairs(self) -> tuple[ReportRepair, ...]:
        repairs: list[ReportRepair] = []
        for package in self._session.work_packages:
            notes = tuple(str(item) for item in package.repair_notes if str(item).strip())
            blocked_reason = str(package.repair_blocked_reason or "")
            if not notes and package.repair_attempt_count <= 0 and not blocked_reason:
                continue
            status = "blocked" if blocked_reason else "requested"
            summary = blocked_reason or (notes[-1] if notes else "Repair requested")
            repairs.append(
                ReportRepair(
                    package_id=package.id,
                    status=status,
                    attempt_count=package.repair_attempt_count,
                    blocked_reason=blocked_reason,
                    summary=summary,
                    notes=notes,
                )
            )
        return tuple(repairs)

    def _build_recovery(self) -> ReportRecovery | None:
        run = self._session.execution_run
        if not isinstance(run, dict) or not run:
            return None
        state = str(run.get("state", "") or "")
        if not state:
            return None
        running_packages = tuple(
            package.id
            for package in self._session.work_packages
            if package.requires_execution and package.status == WorkStatus.RUNNING
        )
        done_packages = tuple(
            package.id
            for package in self._session.work_packages
            if package.requires_execution and package.status == WorkStatus.DONE
        )
        retry_candidates = tuple(
            package.id
            for package in self._session.work_packages
            if package.requires_execution
            and package.status in {WorkStatus.RUNNING, WorkStatus.BLOCKED, WorkStatus.FAILED}
        )
        return ReportRecovery(
            run_id=str(run.get("run_id", "") or ""),
            state=state,
            target_workspace=str(
                run.get("target_workspace") or self._session.target_workspace or ""
            ),
            running_packages=running_packages,
            done_packages=done_packages,
            retry_candidates=retry_candidates,
            interrupted_reason=str(run.get("interrupted_reason", "") or ""),
        )

    @staticmethod
    def _event_data(event: Mapping[str, Any]) -> dict[str, object]:
        data = event.get("data", {})
        return dict(data) if isinstance(data, Mapping) else {}

    @staticmethod
    def _event_timestamp(event: Mapping[str, Any]) -> float:
        try:
            return float(event.get("timestamp", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _event_str_tuple(value: object) -> tuple[str, ...]:
        if isinstance(value, (list, tuple, set)):
            return tuple(str(item) for item in value if str(item).strip())
        if value is None:
            return ()
        text = str(value).strip()
        return (text,) if text else ()

    @staticmethod
    def _event_summary(name: str, data: Mapping[str, object]) -> str:
        for key in ("summary", "reason", "instruction", "action", "decision"):
            value = str(data.get(key, "") or "").strip()
            if value:
                return value
        package_id = str(data.get("package_id", "") or "").strip()
        status = str(data.get("status", "") or "").strip()
        target = str(data.get("target_workspace", "") or "").strip()
        work_packages = data.get("work_packages", [])
        if isinstance(work_packages, list) and work_packages:
            return f"{len(work_packages)} packages"
        parts = [part for part in (package_id, status, target) if part]
        return " ".join(parts) or name

    @staticmethod
    def _blueprint_body(blueprint: Blueprint) -> str:
        lines = [f"# {blueprint.title or 'Blueprint'}"]
        if blueprint.summary:
            lines.extend(["", blueprint.summary])
        if blueprint.architecture:
            lines.extend(["", "## Architecture"])
            lines.extend(
                f"- {component.name}: {component.responsibility}"
                for component in blueprint.architecture
            )
        if blueprint.data_flow:
            lines.extend(["", "## Data Flow"])
            lines.extend(f"- {item}" for item in blueprint.data_flow)
        if blueprint.acceptance_criteria:
            lines.extend(["", "## Acceptance Criteria"])
            lines.extend(f"- {item}" for item in blueprint.acceptance_criteria)
        return "\n".join(lines)

    @staticmethod
    def _format_architecture_component(component) -> str:
        owner = f" [{component.owner_agent}]" if component.owner_agent else ""
        dependencies = (
            f" deps: {', '.join(component.dependencies)}"
            if component.dependencies
            else ""
        )
        return f"{component.name}{owner}: {component.responsibility}{dependencies}"

    @staticmethod
    def _format_risk(risk) -> str:
        mitigation = f" mitigation: {risk.mitigation}" if risk.mitigation else ""
        owner = f" owner: {risk.owner_agent}" if risk.owner_agent else ""
        return f"{risk.severity}: {risk.description}{mitigation}{owner}"

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
                attempt_chain=tuple(self._format_attempt_chain(ex.attempt_chain)),
            )
            for ex in self._session.execution_results
        )

    @staticmethod
    def _format_attempt_chain(attempts: object) -> list[str]:
        if not isinstance(attempts, list):
            return []
        lines: list[str] = []
        for index, attempt in enumerate(attempts, start=1):
            if not isinstance(attempt, dict):
                continue
            agent = str(attempt.get("agent") or attempt.get("agent_name") or "-")
            status = str(attempt.get("status") or "-")
            summary = str(attempt.get("summary") or "").strip()
            raw_path = str(attempt.get("raw_response_path") or "").strip()
            blockers = attempt.get("blockers", [])
            blocker_text = ""
            if isinstance(blockers, list):
                blocker_text = "; ".join(
                    str(item).strip() for item in blockers if str(item).strip()
                )
            elif blockers:
                blocker_text = str(blockers).strip()
            parts = [f"{index}. {agent} {status}"]
            if summary:
                parts.append(f"- {summary}")
            if blocker_text:
                parts.append(f"(blockers: {blocker_text})")
            if raw_path:
                parts.append(f"[raw: {raw_path}]")
            lines.append(" ".join(parts))
        return lines
