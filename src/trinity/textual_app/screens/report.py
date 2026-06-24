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

from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.snapshot import (
    AgentQualitySnapshot,
    ProviderSnapshot,
    WorkflowNexusSnapshot,
    WorkPackageSnapshot,
)
from trinity.textual_app.widgets.status_label import display_review_status_value

if TYPE_CHECKING:
    from trinity.tui.report import DeliberationReport


REPORT_LABELS = {
    "en": {
        "empty": "No workflow data available.",
        "export": "💾 Export Markdown",
        "loading": "Loading workflow data...",
        "saved": "Saved: {path}",
        "title": "📋 Deliberation Report",
    },
    "ko": {
        "empty": "사용 가능한 워크플로우 데이터가 없습니다.",
        "export": "💾 마크다운 내보내기",
        "loading": "워크플로우 데이터를 불러오는 중...",
        "saved": "저장됨: {path}",
        "title": "📋 워크플로우 리포트",
    },
}

REPORT_SECTION_LABELS_KO = {
    "Overview": "개요",
    "Consensus": "합의",
    "Blueprint": "설계안",
    "Decisions": "결정",
    "Work Packages": "작업 패키지",
    "Executions": "실행",
    "Providers": "프로바이더",
    "Execution Timeline": "실행 타임라인",
    "Artifact Manifest": "산출물 목록",
    "Reviews": "리뷰",
    "Review Repairs": "리뷰 복구",
    "Execution Recovery": "실행 복구",
    "Central Agent Conversation": "중앙 에이전트 대화",
    "Advisory Agent Quality": "자문 에이전트 품질",
    "Central WP Graph": "중앙 WP 그래프",
    "Local WP Graph": "로컬 WP 그래프",
    "Work Package Routing": "작업 패키지 라우팅",
    "Local Policy Repairs": "로컬 정책 복구",
    "Execution Log": "실행 로그",
    "Open Questions": "열린 질문",
}

REPORT_FIELD_LABELS_KO = {
    "Acceptance Criteria": "인수 기준",
    "Agreement": "합의율",
    "Architecture": "아키텍처",
    "Data Flow": "데이터 흐름",
    "Done": "완료",
    "Duration": "소요 시간",
    "Goal": "목표",
    "Providers": "프로바이더",
    "Reason": "이유",
    "Retry candidates": "재시도 후보",
    "Risk": "위험",
    "Risks": "위험",
    "Round": "라운드",
    "Rounds": "라운드",
    "Run": "실행",
    "Running": "실행 중",
    "Session": "세션",
    "Source": "출처",
    "State": "상태",
    "Summary": "요약",
    "Target": "대상",
    "Title": "제목",
    "Tokens": "토큰",
}

REPORT_TERM_LABELS_KO = {
    "attempts": "시도",
    "blockers": "차단",
    "components": "컴포넌트",
    "context": "컨텍스트",
    "default": "기본값",
    "executor": "실행자",
    "files": "파일",
    "identified": "식별",
    "items": "항목",
    "kind": "종류",
    "lane": "레인",
    "missing": "누락",
    "mission": "미션",
    "modes": "모드",
    "none": "(없음)",
    "output": "출력",
    "owner": "소유자",
    "profile": "프로필",
    "reason": "이유",
    "recommended": "추천",
    "required changes": "변경 요청",
    "review": "리뷰",
    "score": "점수",
    "session": "세션",
    "steps": "단계",
    "strengths": "강점",
    "success": "성공",
    "unknown": "알 수 없음",
    "unspecified": "미지정",
}


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

    LOCALIZED_BINDINGS = {
        ("ctrl+s", "export_report"): ("binding_export_markdown", None),
        ("escape", "go_back"): ("binding_back", None),
    }

    def __init__(self, *, lang: str = "en") -> None:
        super().__init__(name="report")
        self.lang = lang
        self.snapshot: WorkflowNexusSnapshot | None = None
        self._report: DeliberationReport | None = None
        self._last_rendered_id: str = ""
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="report-screen"):
            with Vertical(id="report-header"):
                yield Static(self._label("title"), id="report-title")
                yield Button(
                    self._label("export"),
                    id="report-export-btn",
                    variant="primary",
                )
                yield Static("", id="report-export-status")
            with VerticalScroll(id="report-body"):
                yield Static(
                    self._label("loading"),
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
            f"[dim]{self._label('saved').format(path=escape(str(path)))}[/dim]"
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
            self._render_from_report(body, self._report, lang=self.lang)
        elif self.snapshot is not None:
            self._render_from_snapshot(body, self.snapshot, lang=self.lang)
        else:
            body.mount(Static(self._label("empty")))

    def _compute_render_id(self) -> str:
        if self._report is not None:
            digest = hashlib.sha1(repr(self._report).encode("utf-8")).hexdigest()
            return f"report:{digest}"
        if self.snapshot is not None:
            digest = hashlib.sha1(repr(self.snapshot).encode("utf-8")).hexdigest()
            return f"snap:{digest}"
        return ""

    def _label(self, key: str) -> str:
        labels = REPORT_LABELS.get(self.lang, REPORT_LABELS["en"])
        return labels.get(key, REPORT_LABELS["en"][key])

    # ── Structured report path (preferred) ──────────────────────────────

    @staticmethod
    def _render_from_report(
        body: VerticalScroll,
        report: DeliberationReport,
        *,
        lang: str = "en",
    ) -> None:
        """Render from a full DeliberationReport with structured data."""
        sections: list[str] = []
        meta = report.meta

        # Overview
        sections.append(
            _section("Overview", _render_overview_meta(meta, lang=lang), lang=lang)
        )

        # Consensus
        if report.consensus is not None:
            sections.append(
                _section(
                    "Consensus",
                    _render_consensus(report.consensus, lang=lang),
                    lang=lang,
                )
            )

        # Blueprint
        if report.blueprint is not None:
            sections.append(
                _section(
                    "Blueprint",
                    _render_blueprint(report.blueprint, lang=lang),
                    lang=lang,
                )
            )

        # Decisions
        if report.decisions:
            sections.append(
                _section(
                    "Decisions",
                    _render_decisions(report.decisions, lang=lang),
                    lang=lang,
                )
            )

        # Work Packages
        if report.packages:
            sections.append(
                _section(
                    "Work Packages",
                    _render_packages(report.packages, lang=lang),
                    lang=lang,
                )
            )

        # Executions
        if report.executions:
            sections.append(
                _section(
                    "Executions",
                    _render_executions(report.executions, lang=lang),
                    lang=lang,
                )
            )

        if report.providers:
            sections.append(
                _section(
                    "Providers",
                    _render_providers(report.providers, lang=lang),
                    lang=lang,
                )
            )

        if report.execution_events:
            sections.append(
                _section(
                    "Execution Timeline",
                    _render_execution_events(report.execution_events[-80:]),
                    lang=lang,
                )
            )

        if report.artifacts:
            sections.append(
                _section(
                    "Artifact Manifest",
                    _render_artifacts(report.artifacts, lang=lang),
                    lang=lang,
                )
            )

        if report.reviews:
            sections.append(
                _section("Reviews", _render_reviews(report.reviews), lang=lang)
            )

        if report.repairs:
            sections.append(
                _section(
                    "Review Repairs",
                    _render_repairs(report.repairs, lang=lang),
                    lang=lang,
                )
            )

        if report.recovery is not None:
            sections.append(
                _section(
                    "Execution Recovery",
                    _render_recovery(report.recovery, lang=lang),
                    lang=lang,
                )
            )

        if report.conversation:
            sections.append(
                _section(
                    "Central Agent Conversation",
                    _render_conversation(report.conversation[-12:]),
                    lang=lang,
                )
            )

        for section_text in sections:
            body.mount(Static(section_text))

    # ── Snapshot fallback path ──────────────────────────────────────────

    @staticmethod
    def _render_from_snapshot(
        body: VerticalScroll,
        snap: WorkflowNexusSnapshot,
        *,
        lang: str = "en",
    ) -> None:
        """Render from a flat WorkflowNexusSnapshot (limited data)."""
        sections: list[str] = []

        sections.append(
            _section("Overview", _render_overview_snap(snap, lang=lang), lang=lang)
        )

        if snap.providers:
            sections.append(
                _section(
                    "Providers",
                    _render_snapshot_providers(snap.providers, lang=lang),
                    lang=lang,
                )
            )

        if snap.agent_quality:
            sections.append(
                _section(
                    "Advisory Agent Quality",
                    _render_agent_quality(snap.agent_quality, lang=lang),
                    lang=lang,
                )
            )

        synthesis = snap.synthesis
        if synthesis.summary:
            sections.append(
                _section(
                    "Consensus",
                    _render_synthesis(synthesis, lang=lang),
                    lang=lang,
                )
            )

        if snap.decisions:
            sections.append(
                _section(
                    "Decisions",
                    _render_list(snap.decisions, lang=lang),
                    lang=lang,
                )
            )

        if snap.central_work_packages:
            sections.append(
                _section(
                    "Central WP Graph",
                    _render_bullets(snap.central_work_packages, lang=lang),
                    lang=lang,
                )
            )

        if snap.work_packages:
            title = "Local WP Graph" if snap.central_work_packages else "Work Packages"
            sections.append(
                _section(
                    title,
                    _render_bullets(snap.work_packages, lang=lang),
                    lang=lang,
                )
            )

        if snap.work_package_details:
            sections.append(
                _section(
                    "Work Package Routing",
                    _render_package_routing(snap.work_package_details, lang=lang),
                    lang=lang,
                )
            )

        if snap.work_package_repairs:
            sections.append(
                _section(
                    "Local Policy Repairs",
                    _render_bullets(snap.work_package_repairs, lang=lang),
                    lang=lang,
                )
            )

        if snap.execution_log:
            sections.append(
                _section(
                    "Execution Log",
                    _render_list(snap.execution_log[-20:], lang=lang),
                    lang=lang,
                )
            )

        if snap.questions:
            sections.append(
                _section(
                    "Open Questions",
                    _render_questions(snap.questions, lang=lang),
                    lang=lang,
                )
            )

        for section_text in sections:
            body.mount(Static(section_text))


# ─── Shared render helpers (used by both paths) ─────────────────────────


def _section(title: str, body: str, *, lang: str = "en") -> str:
    label = _section_label(title, lang=lang)
    return f"[bold cyan]━━ {label} ━━[/bold cyan]\n{body}\n"


def _section_label(title: str, *, lang: str = "en") -> str:
    if lang == "ko":
        return REPORT_SECTION_LABELS_KO.get(title, title)
    return title


def _field_label(title: str, *, lang: str = "en") -> str:
    if lang == "ko":
        return REPORT_FIELD_LABELS_KO.get(title, title)
    return title


def _term_label(term: str, *, lang: str = "en") -> str:
    if lang == "ko":
        return REPORT_TERM_LABELS_KO.get(term, term)
    return term


def _empty_value(*, lang: str = "en") -> str:
    return _term_label("none", lang=lang) if lang == "ko" else "(none)"


def _unknown_value(*, lang: str = "en") -> str:
    return _term_label("unknown", lang=lang) if lang == "ko" else "(unknown)"


def _render_overview_meta(meta, *, lang: str = "en") -> str:
    lines = [
        f"[bold]{_field_label('Session', lang=lang)}[/bold]: {escape(meta.session_id)}",
        f"[bold]{_field_label('Goal', lang=lang)}[/bold]: {escape(meta.goal)}",
        f"[bold]{_field_label('State', lang=lang)}[/bold]: {escape(meta.state)}",
        f"[bold]{_field_label('Rounds', lang=lang)}[/bold]: {meta.rounds}",
        f"[bold]{_field_label('Duration', lang=lang)}[/bold]: {meta.duration}",
        f"[bold]{_field_label('Tokens', lang=lang)}[/bold]: {meta.tokens}",
    ]
    return "\n".join(lines)


def _render_overview_snap(snap: WorkflowNexusSnapshot, *, lang: str = "en") -> str:
    lines = [
        f"[bold]{_field_label('Session', lang=lang)}[/bold]: "
        f"{escape(snap.session_id or _empty_value(lang=lang))}",
        f"[bold]{_field_label('Goal', lang=lang)}[/bold]: "
        f"{escape(snap.goal or _empty_value(lang=lang))}",
        f"[bold]{_field_label('State', lang=lang)}[/bold]: {escape(snap.state)}",
        f"[bold]{_field_label('Round', lang=lang)}[/bold]: {snap.round_num}",
        f"[bold]{_field_label('Providers', lang=lang)}[/bold]: {len(snap.providers)}",
    ]
    return "\n".join(lines)


def _render_consensus(consensus, *, lang: str = "en") -> str:
    icon = "✅" if consensus.reached else "⚠️"
    state = (
        "합의 도달"
        if consensus.reached and lang == "ko"
        else "합의 없음"
        if lang == "ko"
        else "Consensus reached"
        if consensus.reached
        else "No consensus"
    )
    lines = [
        f"{icon} [bold]{state}[/bold]",
        f"[bold]{_field_label('Agreement', lang=lang)}[/bold]: "
        f"{escape(consensus.agreement_ratio)}",
        f"\n{escape(consensus.summary)}",
    ]
    return "\n".join(lines)


def _render_synthesis(synthesis, *, lang: str = "en") -> str:
    icon = "✅" if "blueprint" in synthesis.consensus_progress else "🔄"
    lines = [
        f"{icon} [bold]{escape(synthesis.consensus_progress)}[/bold]",
        f"[bold]{_field_label('Source', lang=lang)}[/bold]: {escape(synthesis.source)}",
        f"\n{escape(synthesis.summary)}",
    ]
    return "\n".join(lines)


def _render_blueprint(blueprint, *, lang: str = "en") -> str:
    lines = [
        f"[bold]{_field_label('Title', lang=lang)}[/bold]: {escape(blueprint.title)}",
        f"[bold]{_field_label('Summary', lang=lang)}[/bold]: {escape(blueprint.summary)}",
        f"  🏗 {_field_label('Architecture', lang=lang)}: "
        f"{blueprint.architecture_count} {_term_label('components', lang=lang)}",
        f"  📊 {_field_label('Data Flow', lang=lang)}: "
        f"{blueprint.data_flow_count} {_term_label('steps', lang=lang)}",
        f"  ⚠ {_field_label('Risks', lang=lang)}: "
        f"{blueprint.risk_count} {_term_label('identified', lang=lang)}",
        f"  ✅ {_field_label('Acceptance Criteria', lang=lang)}: "
        f"{blueprint.acceptance_criteria_count} {_term_label('items', lang=lang)}",
    ]
    return "\n".join(lines)


def _render_decisions(decisions, *, lang: str = "en") -> str:
    lines: list[str] = []
    for d in decisions:
        by = "작성" if lang == "ko" else "by"
        lines.append(
            f"  [cyan]{escape(d.id)}[/cyan] → {escape(d.decision)} "
            f"[dim]({by} {escape(d.decided_by)})[/dim]"
        )
    return "\n".join(lines) if lines else _empty_value(lang=lang)


def _render_packages(packages, *, lang: str = "en") -> str:
    lines: list[str] = []
    for pkg in packages:
        status = f" ({pkg.status})" if pkg.requires_execution else ""
        lines.append(
            f"  • [cyan]{escape(pkg.id)}[/cyan] {escape(pkg.title)} "
            f"[dim]({escape(pkg.owner_agent)}){status}[/dim]"
        )
    return "\n".join(lines) if lines else _empty_value(lang=lang)


def _render_package_routing(
    packages: list[WorkPackageSnapshot],
    *,
    lang: str = "en",
) -> str:
    lines: list[str] = []
    for package in packages:
        routing = _package_routing_summary(package, lang=lang)
        if routing:
            routing = f" · {routing}"
        review = ""
        if package.review_status or package.reviewer_agent:
            review_reason = ""
            if package.review_status == "skipped" and package.review_summary:
                review_reason = f"; reason {escape(package.review_summary)}"
            review_status = display_review_status_value(
                package.review_status,
                reviewer_agent=package.reviewer_agent,
                summary=package.review_summary,
            )
            review = (
                f" · {_term_label('review', lang=lang)} {escape(review_status)}"
                f"/{escape(package.reviewer_agent or _empty_value(lang=lang))}"
                f"{review_reason}"
            )
        lines.append(
            f"  • [cyan]{escape(package.id or _unknown_value(lang=lang))}[/cyan] "
            f"{escape(package.title or _unknown_value(lang=lang))} "
            f"[dim]{_term_label('owner', lang=lang)} "
            f"{escape(package.owner_agent or _unknown_value(lang=lang))} · "
            f"{_term_label('executor', lang=lang)} "
            f"{escape(_package_executor(package, lang=lang))} · "
            f"{_term_label('lane', lang=lang)} "
            f"{escape(_package_lane(package, lang=lang))}{routing}{review}[/dim]"
        )
        if package.routing_reason:
            lines.append(
                f"    [dim]{_term_label('reason', lang=lang)}: "
                f"{escape(package.routing_reason)}[/dim]"
            )
    return "\n".join(lines) if lines else _empty_value(lang=lang)


def _package_executor(package: WorkPackageSnapshot, *, lang: str = "en") -> str:
    return (
        package.current_executor
        or package.last_executor
        or package.last_result_agent
        or _empty_value(lang=lang)
    )


def _package_lane(package: WorkPackageSnapshot, *, lang: str = "en") -> str:
    if not package.parallelizable:
        return "serial"
    if package.parallel_group is not None:
        return f"g{package.parallel_group}"
    return _term_label("unspecified", lang=lang)


def _package_routing_summary(
    package: WorkPackageSnapshot,
    *,
    lang: str = "en",
) -> str:
    parts: list[str] = []
    if package.task_kind:
        parts.append(f"{_term_label('kind', lang=lang)} {escape(package.task_kind)}")
    if package.profile_revision:
        parts.append(
            f"{_term_label('profile', lang=lang)} {escape(package.profile_revision)}"
        )
    if package.routing_score:
        parts.append(
            f"{_term_label('score', lang=lang)} "
            f"{escape(_format_score(package.routing_score))}"
        )
    return " · ".join(parts)


def _format_score(score: float) -> str:
    text = f"{score:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _render_executions(executions, *, lang: str = "en") -> str:
    lines: list[str] = []
    for ex in executions:
        files = (
            f" · {ex.files_count} {_term_label('files', lang=lang)}"
            if ex.files_count
            else ""
        )
        lines.append(f"  • [cyan]{escape(ex.package_id)}[/cyan] {escape(ex.agent_name)}: {escape(ex.status)}{files}")
    return "\n".join(lines) if lines else _empty_value(lang=lang)


def _render_providers(providers, *, lang: str = "en") -> str:
    lines: list[str] = []
    for provider in providers:
        model = provider.actual_model or provider.configured_model or _term_label("default", lang=lang)
        context = (
            f"{provider.context_window:,}"
            if provider.context_window
            else _term_label("unknown", lang=lang)
        )
        session = (
            provider.provider_session_id[:18]
            if provider.provider_session_id
            else _empty_value(lang=lang)
        )
        lines.append(
            f"  • [cyan]{escape(provider.name)}[/cyan] "
            f"{escape(provider.provider or 'unknown')} · "
            f"{escape(model)} · {_term_label('context', lang=lang)} "
            f"{escape(context)} · {_term_label('session', lang=lang)} "
            f"{escape(session)}"
        )
    return "\n".join(lines) if lines else _empty_value(lang=lang)


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


def _render_artifacts(artifacts, *, lang: str = "en") -> str:
    lines: list[str] = []
    for artifact in artifacts:
        size = (
            f"{artifact.size_bytes:,} bytes"
            if artifact.exists
            else _term_label("missing", lang=lang)
        )
        lines.append(
            f"  • [cyan]{escape(artifact.source or '-')}[/cyan] "
            f"{escape(artifact.package_id or '-')} "
            f"{escape(artifact.agent_name or '-')} · {escape(size)}\n"
            f"    [dim]{escape(artifact.path)}[/dim]"
        )
    return "\n".join(lines) if lines else _empty_value(lang=lang)


def _render_snapshot_providers(
    providers: list[ProviderSnapshot],
    *,
    lang: str = "en",
) -> str:
    lines: list[str] = []
    for provider in providers:
        if not provider.enabled:
            continue
        model = (
            provider.actual_model
            or provider.model_label
            or provider.configured_model
            or _term_label("default", lang=lang)
        )
        context = (
            f"{provider.context_window:,}"
            if provider.context_window
            else _term_label("unknown", lang=lang)
        )
        source = provider.budget_source or _term_label("unknown", lang=lang)
        session = provider.session_id[:12] if provider.session_id else _empty_value(lang=lang)
        profile = _provider_profile_summary(provider, lang=lang)
        if profile:
            profile = f" · {profile}"
        lines.append(
            f"  • [cyan]{escape(provider.name)}[/cyan] "
            f"{escape(model)} · {_term_label('context', lang=lang)} "
            f"{escape(context)} ({escape(source)}) · "
            f"{_term_label('session', lang=lang)} {escape(session)}{profile}"
        )
    return "\n".join(lines) if lines else _empty_value(lang=lang)


def _provider_profile_summary(
    provider: ProviderSnapshot,
    *,
    lang: str = "en",
) -> str:
    parts: list[str] = []
    if provider.context_profile:
        parts.append(f"{_term_label('profile', lang=lang)} {escape(provider.context_profile)}")
    if provider.profile_modes:
        parts.append(f"{_term_label('modes', lang=lang)} {escape(', '.join(provider.profile_modes))}")
    if provider.output_contract:
        parts.append(f"{_term_label('output', lang=lang)} {escape(provider.output_contract)}")
    if provider.profile_strengths:
        strengths = ", ".join(provider.profile_strengths[:3])
        if len(provider.profile_strengths) > 3:
            strengths = f"{strengths}, +{len(provider.profile_strengths) - 3}"
        parts.append(f"{_term_label('strengths', lang=lang)} {escape(strengths)}")
    if provider.profile_mission:
        parts.append(f"{_term_label('mission', lang=lang)} {escape(provider.profile_mission)}")
    return " · ".join(parts)


def _render_agent_quality(
    items: list[AgentQualitySnapshot],
    *,
    lang: str = "en",
) -> str:
    lines: list[str] = []
    for item in items:
        lines.append(
            f"  • [cyan]{escape(item.agent_name or '(unknown)')}[/cyan] "
            f"{_term_label('score', lang=lang)} {escape(_format_score(item.score))} · "
            f"{_term_label('success', lang=lang)} {item.success_count}/{item.signal_count} · "
            f"{_term_label('blockers', lang=lang)} {item.blocker_count} · "
            f"{_term_label('required changes', lang=lang)} "
            f"{item.required_change_count}"
        )
    return "\n".join(lines) if lines else _empty_value(lang=lang)


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


def _render_repairs(repairs, *, lang: str = "en") -> str:
    lines: list[str] = []
    for repair in repairs:
        lines.append(
            f"  • [cyan]{escape(repair.package_id)}[/cyan] "
            f"{escape(repair.status or '-')} · "
            f"{_term_label('attempts', lang=lang)} {repair.attempt_count}: "
            f"{escape(repair.summary or '')}"
        )
    return "\n".join(lines) if lines else _empty_value(lang=lang)


def _render_recovery(recovery, *, lang: str = "en") -> str:
    lines = [
        f"[bold]{_field_label('Run', lang=lang)}[/bold]: "
        f"{escape(recovery.run_id or _unknown_value(lang=lang))}",
        f"[bold]{_field_label('State', lang=lang)}[/bold]: "
        f"{escape(recovery.state or _unknown_value(lang=lang))}",
        f"[bold]{_field_label('Target', lang=lang)}[/bold]: "
        f"{escape(recovery.target_workspace or _empty_value(lang=lang))}",
        f"[bold]{_field_label('Running', lang=lang)}[/bold]: "
        f"{escape(', '.join(recovery.running_packages) or _empty_value(lang=lang))}",
        f"[bold]{_field_label('Retry candidates', lang=lang)}[/bold]: "
        f"{escape(', '.join(recovery.retry_candidates) or _empty_value(lang=lang))}",
        f"[bold]{_field_label('Done', lang=lang)}[/bold]: "
        f"{escape(', '.join(recovery.done_packages) or _empty_value(lang=lang))}",
    ]
    if recovery.interrupted_reason:
        lines.append(
            f"[bold]{_field_label('Reason', lang=lang)}[/bold]: "
            f"{escape(recovery.interrupted_reason)}"
        )
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


def _render_list(items: list[str], *, lang: str = "en") -> str:
    lines = [f"  {i}. {escape(item)}" for i, item in enumerate(items, 1)]
    return "\n".join(lines) if lines else _empty_value(lang=lang)


def _render_bullets(items: list[str], *, lang: str = "en") -> str:
    lines = [f"  • {escape(item)}" for item in items]
    return "\n".join(lines) if lines else _empty_value(lang=lang)


def _render_questions(questions, *, lang: str = "en") -> str:
    lines: list[str] = []
    for q in questions:
        lines.append(f"  [bold]{escape(q.id)}[/bold]: {escape(q.question)}")
        if q.options:
            for i, opt in enumerate(q.options, 1):
                marker = (
                    f" ({_term_label('recommended', lang=lang)})"
                    if opt == q.recommended_option
                    else ""
                )
                lines.append(f"    {i}. {escape(opt)}{marker}")
    return "\n".join(lines) if lines else _empty_value(lang=lang)
