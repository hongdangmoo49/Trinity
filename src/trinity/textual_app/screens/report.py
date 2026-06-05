"""Report screen — deliberation session overview in Textual TUI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from rich.markup import escape

from trinity.textual_app.snapshot import WorkflowNexusSnapshot


class ReportScreen(Screen[None]):
    """Displays a structured overview of the deliberation session.

    Shows goal, consensus, blueprint summary, decisions, work packages,
    and execution results in a scrollable vertical layout.
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
            with VerticalScroll(id="report-body"):
                yield Static(
                    "워크플로우 데이터를 불러오는 중…",
                    id="report-placeholder",
                )
        yield Footer()

    def on_mount(self) -> None:
        if self.snapshot is not None:
            self._render_report()

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        """Render report content from a workflow snapshot."""
        self.snapshot = snapshot
        if not self.is_mounted:
            return
        self._render_report()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "report-export-btn":
            event.stop()
            self.action_export_report()

    def action_export_report(self) -> None:
        self.post_message(self.ExportRequested(self.snapshot))

    def action_go_back(self) -> None:
        self.app.switch_to("nexus")  # type: ignore[attr-defined]

    def _render_report(self) -> None:
        # Skip re-render if the snapshot hasn't changed
        render_id = f"{self.snapshot.session_id}:{self.snapshot.state}:{self.snapshot.round_num}" if self.snapshot else ""
        if render_id == self._last_rendered_id:
            return
        self._last_rendered_id = render_id

        body = self.query_one("#report-body", VerticalScroll)

        # Remove all existing children safely
        for child in list(body.children):
            child.remove()

        snap = self.snapshot
        if snap is None:
            body.mount(Static("No workflow data available."))
            return

        sections: list[str] = []

        # Overview
        sections.append(self._section("Overview", self._render_overview(snap)))

        # Consensus
        synthesis = snap.synthesis
        if synthesis.summary:
            sections.append(
                self._section("Consensus", self._render_consensus(synthesis))
            )

        # Decisions
        if snap.decisions:
            sections.append(
                self._section("Decisions", self._render_decisions(snap.decisions))
            )

        # Work Packages
        if snap.work_packages:
            sections.append(
                self._section(
                    "Work Packages",
                    self._render_packages(snap.work_packages),
                )
            )

        # Execution Log
        if snap.execution_log:
            sections.append(
                self._section(
                    "Execution Log",
                    self._render_execution_log(snap.execution_log),
                )
            )

        # Questions
        if snap.questions:
            sections.append(
                self._section(
                    "Open Questions",
                    self._render_questions(snap.questions),
                )
            )

        for section_text in sections:
            body.mount(Static(section_text))

    # ── Section Renderers ──────────────────────────────────────────────

    @staticmethod
    def _render_overview(snap: WorkflowNexusSnapshot) -> str:
        lines = [
            f"[bold]Session[/bold]: {escape(snap.session_id or '(none)')}",
            f"[bold]Goal[/bold]: {escape(snap.goal or '(none)')}",
            f"[bold]State[/bold]: {escape(snap.state)}",
            f"[bold]Round[/bold]: {snap.round_num}",
            f"[bold]Providers[/bold]: {len(snap.providers)}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _render_consensus(synthesis) -> str:
        icon = "✅" if "blueprint" in synthesis.consensus_progress else "🔄"
        lines = [
            f"{icon} [bold]{escape(synthesis.consensus_progress)}[/bold]",
            f"[bold]Source[/bold]: {escape(synthesis.source)}",
            f"\n{escape(synthesis.summary)}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _render_decisions(decisions: list[str]) -> str:
        lines: list[str] = []
        for i, decision in enumerate(decisions, 1):
            lines.append(f"  {i}. {escape(decision)}")
        return "\n".join(lines) if lines else "(none)"

    @staticmethod
    def _render_packages(packages: list[str]) -> str:
        lines: list[str] = []
        for pkg in packages:
            lines.append(f"  • {escape(pkg)}")
        return "\n".join(lines) if lines else "(none)"

    @staticmethod
    def _render_execution_log(log: list[str]) -> str:
        lines: list[str] = []
        for entry in log[-20:]:
            lines.append(f"  {escape(entry)}")
        return "\n".join(lines) if lines else "(none)"

    @staticmethod
    def _render_questions(questions) -> str:
        lines: list[str] = []
        for q in questions:
            lines.append(f"  [bold]{escape(q.id)}[/bold]: {escape(q.question)}")
            if q.options:
                for i, opt in enumerate(q.options, 1):
                    marker = " (recommended)" if opt == q.recommended_option else ""
                    lines.append(f"    {i}. {escape(opt)}{marker}")
        return "\n".join(lines) if lines else "(none)"

    @staticmethod
    def _section(title: str, body: str) -> str:
        return f"[bold cyan]━━ {title} ━━[/bold cyan]\n{body}\n"
