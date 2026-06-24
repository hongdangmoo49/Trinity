"""Report screen — deliberation session overview in Textual TUI."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from rich.markup import escape

from trinity.textual_app.snapshot import (
    AgentQualitySnapshot,
    ProviderSnapshot,
    WorkflowNexusSnapshot,
    WorkPackageSnapshot,
)

if TYPE_CHECKING:
    from trinity.tui.report import DeliberationReport


class ReportScreen(Screen[None]):
    """Displays a structured overview of the deliberation session.

    Supports two data sources:
    - ``apply_report``: Rich structured data from DeliberationReport (preferred).
    - ``apply_snapshot``: Flattened data from WorkflowNexusSnapshot (fallback).
    """

    class ExportRequested(Message):
        """Posted when the user clicks the export button."""

        def __init__(self, snapshot: WorkflowNexusSnapshot | None) -> None:
            super().__init__()
            self.snapshot = snapshot

    BINDINGS = [
        Binding("ctrl+s", "export_report", "Export Markdown"),
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__(name="report")
        self.snapshot: WorkflowNexusSnapshot | None = None
        self._report: DeliberationReport | None = None
        self._last_rendered_id: str = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="report-screen"):
            with Vertical(id="report-header"):
                yield Static("📋 Deliberation Report", id="report-title")
                yield Button(
                    "💾 Export Markdown",
                    id="report-export-btn",
                    variant="primary",
                )
                yield Static("", id="report-export-status")
            with VerticalScroll(id="report-body"):
                yield Static(
                    "워크플로우 데이터를 불러오는 중…",
                    id="report-placeholder",
                )
        yield Footer()

    def on_mount(self) -> None:
        if self._report is not None or self.snapshot is not None:
            self._render_report()

    def apply_report(self, report: DeliberationReport) -> None:
        """Render from a structured DeliberationReport (preferred path)."""
        self._report = report
        if not self.is_mounted:
            return
        self._render_report()

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        """Render report content from a workflow snapshot (fallback path)."""
        self.snapshot = snapshot
        if not self.is_mounted:
            return
        self._render_report()

    def show_export_path(self, path: Path) -> None:
        """Show the last Markdown export destination in the report header."""
        if not self.is_mounted:
            return
        self.query_one("#report-export-status", Static).update(
            f"[dim]Saved: {escape(str(path))}[/dim]"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "report-export-btn":
            event.stop()
            self.action_export_report()

    def action_export_report(self) -> None:
        self.post_message(self.ExportRequested(self.snapshot))

    def action_go_back(self) -> None:
        self.app.switch_to("nexus")  # type: ignore[attr-defined]

    def _render_report(self) -> None:
        # Skip re-render if data hasn't changed
        render_id = self._compute_render_id()
        if render_id == self._last_rendered_id:
            return
        self._last_rendered_id = render_id

        body = self.query_one("#report-body", VerticalScroll)

        # Remove all existing children safely
        for child in list(body.children):
            child.remove()

        # Prefer structured report over flat snapshot
        if self._report is not None:
            self._render_from_report(body, self._report)
        elif self.snapshot is not None:
            self._render_from_snapshot(body, self.snapshot)
        else:
            body.mount(Static("No workflow data available."))

    def _compute_render_id(self) -> str:
        if self._report is not None:
            digest = hashlib.sha1(repr(self._report).encode("utf-8")).hexdigest()
            return f"report:{digest}"
        if self.snapshot is not None:
            digest = hashlib.sha1(repr(self.snapshot).encode("utf-8")).hexdigest()
            return f"snap:{digest}"
        return ""

    # ── Structured report path (preferred) ──────────────────────────────

    @staticmethod
    def _render_from_report(body: VerticalScroll, report: DeliberationReport) -> None:
        """Render from a full DeliberationReport with structured data."""
        sections: list[str] = []
        meta = report.meta

        # Overview
        sections.append(_section("Overview", _render_overview_meta(meta)))

        # Consensus
        if report.consensus is not None:
            sections.append(_section("Consensus", _render_consensus(report.consensus)))

        # Blueprint
        if report.blueprint is not None:
            sections.append(_section("Blueprint", _render_blueprint(report.blueprint)))

        # Decisions
        if report.decisions:
            sections.append(_section("Decisions", _render_decisions(report.decisions)))

        # Work Packages
        if report.packages:
            sections.append(_section("Work Packages", _render_packages(report.packages)))

        # Executions
        if report.executions:
            sections.append(_section("Executions", _render_executions(report.executions)))

        if report.providers:
            sections.append(_section("Providers", _render_providers(report.providers)))

        if report.execution_events:
            sections.append(
                _section(
                    "Execution Timeline",
                    _render_execution_events(report.execution_events[-80:]),
                )
            )

        if report.artifacts:
            sections.append(_section("Artifact Manifest", _render_artifacts(report.artifacts)))

        if report.reviews:
            sections.append(_section("Reviews", _render_reviews(report.reviews)))

        if report.repairs:
            sections.append(_section("Review Repairs", _render_repairs(report.repairs)))

        if report.recovery is not None:
            sections.append(_section("Execution Recovery", _render_recovery(report.recovery)))

        if report.conversation:
            sections.append(
                _section(
                    "Central Agent Conversation",
                    _render_conversation(report.conversation[-12:]),
                )
            )

        for section_text in sections:
            body.mount(Static(section_text))

    # ── Snapshot fallback path ──────────────────────────────────────────

    @staticmethod
    def _render_from_snapshot(body: VerticalScroll, snap: WorkflowNexusSnapshot) -> None:
        """Render from a flat WorkflowNexusSnapshot (limited data)."""
        sections: list[str] = []

        sections.append(_section("Overview", _render_overview_snap(snap)))

        if snap.providers:
            sections.append(_section("Providers", _render_snapshot_providers(snap.providers)))

        if snap.agent_quality:
            sections.append(
                _section(
                    "Advisory Agent Quality",
                    _render_agent_quality(snap.agent_quality),
                )
            )

        synthesis = snap.synthesis
        if synthesis.summary:
            sections.append(_section("Consensus", _render_synthesis(synthesis)))

        if snap.decisions:
            sections.append(_section("Decisions", _render_list(snap.decisions)))

        if snap.central_work_packages:
            sections.append(
                _section("Central WP Graph", _render_bullets(snap.central_work_packages))
            )

        if snap.work_packages:
            title = "Local WP Graph" if snap.central_work_packages else "Work Packages"
            sections.append(_section(title, _render_bullets(snap.work_packages)))

        if snap.work_package_details:
            sections.append(
                _section(
                    "Work Package Routing",
                    _render_package_routing(snap.work_package_details),
                )
            )

        if snap.work_package_repairs:
            sections.append(
                _section(
                    "Local Policy Repairs",
                    _render_bullets(snap.work_package_repairs),
                )
            )

        if snap.execution_log:
            sections.append(_section("Execution Log", _render_list(snap.execution_log[-20:])))

        if snap.questions:
            sections.append(_section("Open Questions", _render_questions(snap.questions)))

        for section_text in sections:
            body.mount(Static(section_text))


# ─── Shared render helpers (used by both paths) ─────────────────────────


def _section(title: str, body: str) -> str:
    return f"[bold cyan]━━ {title} ━━[/bold cyan]\n{body}\n"


def _render_overview_meta(meta) -> str:
    lines = [
        f"[bold]Session[/bold]: {escape(meta.session_id)}",
        f"[bold]Goal[/bold]: {escape(meta.goal)}",
        f"[bold]State[/bold]: {escape(meta.state)}",
        f"[bold]Rounds[/bold]: {meta.rounds}",
        f"[bold]Duration[/bold]: {meta.duration}",
        f"[bold]Tokens[/bold]: {meta.tokens}",
    ]
    return "\n".join(lines)


def _render_overview_snap(snap: WorkflowNexusSnapshot) -> str:
    lines = [
        f"[bold]Session[/bold]: {escape(snap.session_id or '(none)')}",
        f"[bold]Goal[/bold]: {escape(snap.goal or '(none)')}",
        f"[bold]State[/bold]: {escape(snap.state)}",
        f"[bold]Round[/bold]: {snap.round_num}",
        f"[bold]Providers[/bold]: {len(snap.providers)}",
    ]
    return "\n".join(lines)


def _render_consensus(consensus) -> str:
    icon = "✅" if consensus.reached else "⚠️"
    lines = [
        f"{icon} [bold]{'Consensus reached' if consensus.reached else 'No consensus'}[/bold]",
        f"[bold]Agreement[/bold]: {escape(consensus.agreement_ratio)}",
        f"\n{escape(consensus.summary)}",
    ]
    return "\n".join(lines)


def _render_synthesis(synthesis) -> str:
    icon = "✅" if "blueprint" in synthesis.consensus_progress else "🔄"
    lines = [
        f"{icon} [bold]{escape(synthesis.consensus_progress)}[/bold]",
        f"[bold]Source[/bold]: {escape(synthesis.source)}",
        f"\n{escape(synthesis.summary)}",
    ]
    return "\n".join(lines)


def _render_blueprint(blueprint) -> str:
    lines = [
        f"[bold]Title[/bold]: {escape(blueprint.title)}",
        f"[bold]Summary[/bold]: {escape(blueprint.summary)}",
        f"  🏗 Architecture: {blueprint.architecture_count} components",
        f"  📊 Data Flow: {blueprint.data_flow_count} steps",
        f"  ⚠ Risks: {blueprint.risk_count} identified",
        f"  ✅ Acceptance Criteria: {blueprint.acceptance_criteria_count} items",
    ]
    return "\n".join(lines)


def _render_decisions(decisions) -> str:
    lines: list[str] = []
    for d in decisions:
        lines.append(f"  [cyan]{escape(d.id)}[/cyan] → {escape(d.decision)} [dim](by {escape(d.decided_by)})[/dim]")
    return "\n".join(lines) if lines else "(none)"


def _render_packages(packages) -> str:
    lines: list[str] = []
    for pkg in packages:
        status = f" ({pkg.status})" if pkg.requires_execution else ""
        lines.append(f"  • [cyan]{escape(pkg.id)}[/cyan] {escape(pkg.title)} [dim]({escape(pkg.owner_agent)}){status}[/dim]")
    return "\n".join(lines) if lines else "(none)"


def _render_package_routing(packages: list[WorkPackageSnapshot]) -> str:
    lines: list[str] = []
    for package in packages:
        routing = _package_routing_summary(package)
        if routing:
            routing = f" · {routing}"
        review = ""
        if package.review_status or package.reviewer_agent:
            review_reason = ""
            if package.review_status == "skipped" and package.review_summary:
                review_reason = f"; reason {escape(package.review_summary)}"
            review = (
                f" · review {escape(package.review_status or '(none)')}"
                f"/{escape(package.reviewer_agent or '(none)')}"
                f"{review_reason}"
            )
        lines.append(
            f"  • [cyan]{escape(package.id or '(unnamed)')}[/cyan] "
            f"{escape(package.title or '(untitled)')} "
            f"[dim]owner {escape(package.owner_agent or '(unknown)')} · "
            f"executor {escape(_package_executor(package))} · "
            f"lane {escape(_package_lane(package))}{routing}{review}[/dim]"
        )
        if package.routing_reason:
            lines.append(f"    [dim]reason: {escape(package.routing_reason)}[/dim]")
    return "\n".join(lines) if lines else "(none)"


def _package_executor(package: WorkPackageSnapshot) -> str:
    return (
        package.current_executor
        or package.last_executor
        or package.last_result_agent
        or "(none)"
    )


def _package_lane(package: WorkPackageSnapshot) -> str:
    if not package.parallelizable:
        return "serial"
    if package.parallel_group is not None:
        return f"g{package.parallel_group}"
    return "unspecified"


def _package_routing_summary(package: WorkPackageSnapshot) -> str:
    parts: list[str] = []
    if package.task_kind:
        parts.append(f"kind {escape(package.task_kind)}")
    if package.profile_revision:
        parts.append(f"profile {escape(package.profile_revision)}")
    if package.routing_score:
        parts.append(f"score {escape(_format_score(package.routing_score))}")
    return " · ".join(parts)


def _format_score(score: float) -> str:
    text = f"{score:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _render_executions(executions) -> str:
    lines: list[str] = []
    for ex in executions:
        files = f" · {ex.files_count} files" if ex.files_count else ""
        lines.append(f"  • [cyan]{escape(ex.package_id)}[/cyan] {escape(ex.agent_name)}: {escape(ex.status)}{files}")
    return "\n".join(lines) if lines else "(none)"


def _render_providers(providers) -> str:
    lines: list[str] = []
    for provider in providers:
        model = provider.actual_model or provider.configured_model or "default"
        context = f"{provider.context_window:,}" if provider.context_window else "unknown"
        session = provider.provider_session_id[:18] if provider.provider_session_id else "none"
        lines.append(
            f"  • [cyan]{escape(provider.name)}[/cyan] "
            f"{escape(provider.provider or 'unknown')} · "
            f"{escape(model)} · context {escape(context)} · session {escape(session)}"
        )
    return "\n".join(lines) if lines else "(none)"


def _render_execution_events(events) -> str:
    lines: list[str] = []
    for event in events:
        package = event.package_id or "-"
        agent = event.agent or "-"
        status = event.status or event.state or "-"
        summary = " ".join(event.summary.split())
        if len(summary) > 120:
            summary = f"{summary[:117]}..."
        lines.append(
            f"  • [cyan]{escape(event.event)}[/cyan] "
            f"{escape(package)} {escape(agent)} {escape(status)}"
            f" [dim]{escape(summary)}[/dim]"
        )
    return "\n".join(lines) if lines else "(none)"


def _render_artifacts(artifacts) -> str:
    lines: list[str] = []
    for artifact in artifacts:
        size = f"{artifact.size_bytes:,} bytes" if artifact.exists else "missing"
        lines.append(
            f"  • [cyan]{escape(artifact.source or '-')}[/cyan] "
            f"{escape(artifact.package_id or '-')} "
            f"{escape(artifact.agent_name or '-')} · {escape(size)}\n"
            f"    [dim]{escape(artifact.path)}[/dim]"
        )
    return "\n".join(lines) if lines else "(none)"


def _render_snapshot_providers(providers: list[ProviderSnapshot]) -> str:
    lines: list[str] = []
    for provider in providers:
        if not provider.enabled:
            continue
        model = provider.actual_model or provider.model_label or provider.configured_model or "default"
        context = f"{provider.context_window:,}" if provider.context_window else "unknown"
        source = provider.budget_source or "unknown"
        session = provider.session_id[:12] if provider.session_id else "none"
        profile = _provider_profile_summary(provider)
        if profile:
            profile = f" · {profile}"
        lines.append(
            f"  • [cyan]{escape(provider.name)}[/cyan] "
            f"{escape(model)} · context {escape(context)} "
            f"({escape(source)}) · session {escape(session)}{profile}"
        )
    return "\n".join(lines) if lines else "(none)"


def _provider_profile_summary(provider: ProviderSnapshot) -> str:
    parts: list[str] = []
    if provider.context_profile:
        parts.append(f"profile {escape(provider.context_profile)}")
    if provider.profile_modes:
        parts.append(f"modes {escape(', '.join(provider.profile_modes))}")
    if provider.output_contract:
        parts.append(f"output {escape(provider.output_contract)}")
    if provider.profile_strengths:
        strengths = ", ".join(provider.profile_strengths[:3])
        if len(provider.profile_strengths) > 3:
            strengths = f"{strengths}, +{len(provider.profile_strengths) - 3}"
        parts.append(f"strengths {escape(strengths)}")
    if provider.profile_mission:
        parts.append(f"mission {escape(provider.profile_mission)}")
    return " · ".join(parts)


def _render_agent_quality(items: list[AgentQualitySnapshot]) -> str:
    lines: list[str] = []
    for item in items:
        lines.append(
            f"  • [cyan]{escape(item.agent_name or '(unknown)')}[/cyan] "
            f"score {escape(_format_score(item.score))} · "
            f"success {item.success_count}/{item.signal_count} · "
            f"blockers {item.blocker_count} · "
            f"required changes {item.required_change_count}"
        )
    return "\n".join(lines) if lines else "(none)"


def _render_reviews(reviews) -> str:
    lines: list[str] = []
    for review in reviews:
        lines.append(
            f"  • [cyan]{escape(review.review_package_id or review.package_id)}[/cyan] "
            f"{escape(review.reviewer_agent or '-')} → "
            f"{escape(review.target_agent or '-')} · {escape(review.status or '-')}: "
            f"{escape(review.summary or '')}"
        )
    return "\n".join(lines) if lines else "(none)"


def _render_repairs(repairs) -> str:
    lines: list[str] = []
    for repair in repairs:
        lines.append(
            f"  • [cyan]{escape(repair.package_id)}[/cyan] "
            f"{escape(repair.status or '-')} · attempts {repair.attempt_count}: "
            f"{escape(repair.summary or '')}"
        )
    return "\n".join(lines) if lines else "(none)"


def _render_recovery(recovery) -> str:
    lines = [
        f"[bold]Run[/bold]: {escape(recovery.run_id or '(unknown)')}",
        f"[bold]State[/bold]: {escape(recovery.state or '(unknown)')}",
        f"[bold]Target[/bold]: {escape(recovery.target_workspace or '(not set)')}",
        f"[bold]Running[/bold]: {escape(', '.join(recovery.running_packages) or '(none)')}",
        f"[bold]Retry candidates[/bold]: {escape(', '.join(recovery.retry_candidates) or '(none)')}",
        f"[bold]Done[/bold]: {escape(', '.join(recovery.done_packages) or '(none)')}",
    ]
    if recovery.interrupted_reason:
        lines.append(f"[bold]Reason[/bold]: {escape(recovery.interrupted_reason)}")
    return "\n".join(lines)


def _render_conversation(messages) -> str:
    lines: list[str] = []
    for message in messages:
        body = " ".join(message.body.split())
        if len(body) > 140:
            body = f"{body[:137]}..."
        title = message.title or message.command or message.role
        lines.append(
            f"  • [cyan]{escape(message.role or 'entry')}[/cyan] "
            f"{escape(title)}: [dim]{escape(body)}[/dim]"
        )
    return "\n".join(lines) if lines else "(none)"


def _render_list(items: list[str]) -> str:
    lines = [f"  {i}. {escape(item)}" for i, item in enumerate(items, 1)]
    return "\n".join(lines) if lines else "(none)"


def _render_bullets(items: list[str]) -> str:
    lines = [f"  • {escape(item)}" for item in items]
    return "\n".join(lines) if lines else "(none)"


def _render_questions(questions) -> str:
    lines: list[str] = []
    for q in questions:
        lines.append(f"  [bold]{escape(q.id)}[/bold]: {escape(q.question)}")
        if q.options:
            for i, opt in enumerate(q.options, 1):
                marker = " (recommended)" if opt == q.recommended_option else ""
                lines.append(f"    {i}. {escape(opt)}{marker}")
    return "\n".join(lines) if lines else "(none)"
