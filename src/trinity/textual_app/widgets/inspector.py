"""Workflow side inspector widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.progress_summary import (
    blocked_detail_line,
    blocked_work_packages,
    compact_wp_line,
    current_work_packages,
    next_work_package_entries,
    next_work_package_line,
    progress_bar,
    progress_summary_line,
    waiting_on_detail_line,
    work_package_counts,
    work_package_state,
)
from trinity.display_labels import display_severity_value, display_source_value
from trinity.textual_app.widgets.status_label import display_status_value


INSPECTOR_LABELS = {
    "en": {
        "blocked": "Blocked",
        "current": "Current",
        "decisions": "Decisions",
        "context": "context",
        "default": "default",
        "empty": "(none)",
        "execution_log": "Execution Log",
        "id": "ID",
        "more": "+{count} more",
        "new_workflow": "(new)",
        "next": "Next",
        "post_review": "Post Review",
        "progress": "Progress",
        "providers": "Providers",
        "questions": "Questions",
        "round": "Round",
        "session": "session",
        "state": "State",
        "unknown": "unknown",
        "workflow": "Workflow",
    },
    "ko": {
        "blocked": "차단",
        "current": "현재",
        "decisions": "결정",
        "context": "컨텍스트",
        "default": "기본값",
        "empty": "(없음)",
        "execution_log": "실행 로그",
        "id": "ID",
        "more": "외 {count}개",
        "new_workflow": "(새 워크플로우)",
        "next": "다음",
        "post_review": "사후 리뷰",
        "progress": "진행",
        "providers": "프로바이더",
        "questions": "질문",
        "round": "라운드",
        "session": "세션",
        "state": "상태",
        "unknown": "알 수 없음",
        "workflow": "워크플로우",
    },
}


class WorkflowInspector(Vertical):
    """Compact read-only workflow status side surface."""

    def __init__(self, *, id: str | None = None, lang: str = "en") -> None:
        super().__init__(id=id)
        self.lang = lang
        self.snapshot = WorkflowNexusSnapshot()
        self._section_text: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Static(self._label("progress"), classes="inspector-title")
        yield Static("", id="inspector-progress")
        yield Static(self._label("current"), classes="inspector-title")
        yield Static("", id="inspector-current")
        yield Static(self._label("next"), classes="inspector-title")
        yield Static("", id="inspector-next")
        yield Static(self._label("blocked"), classes="inspector-title")
        yield Static("", id="inspector-blocked")
        yield Static(self._label("workflow"), classes="inspector-title")
        yield Static("", id="inspector-workflow")
        yield Static(self._label("providers"), classes="inspector-title")
        yield Static("", id="inspector-providers")
        yield Static(self._label("questions"), classes="inspector-title")
        yield Static("", id="inspector-questions")
        yield Static(self._label("decisions"), classes="inspector-title")
        yield Static("", id="inspector-decisions")
        yield Static(self._label("post_review"), classes="inspector-title")
        yield Static("", id="inspector-post-review")
        yield Static(self._label("execution_log"), classes="inspector-title")
        yield Static("", id="inspector-log")

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        self.snapshot = snapshot
        if not self.is_mounted:
            return
        self._update_section("#inspector-progress", self._progress_summary(snapshot))
        self._update_section(
            "#inspector-current",
            self._list_or_empty(
                [
                    compact_wp_line(package, lang=self.lang)
                    for package in current_work_packages(snapshot.work_package_details)
                ]
            ),
        )
        self._update_section(
            "#inspector-next",
            self._list_or_empty(self._next_lines(snapshot), limit=8),
        )
        self._update_section(
            "#inspector-blocked",
            self._list_or_empty(self._blocked_lines(snapshot)),
        )
        self._update_section(
            "#inspector-workflow",
            "\n".join(
                [
                    f"{self._label('id')}: {snapshot.session_id or self._label('new_workflow')}",
                    f"{self._label('state')}: {self._status_value(snapshot.state)}",
                    f"{self._label('round')}: {snapshot.round_num}",
                ]
            ),
        )
        self._update_section(
            "#inspector-providers",
            self._list_or_empty(self._provider_lines(snapshot)),
        )
        self._update_section(
            "#inspector-questions",
            self._list_or_empty([question.question for question in snapshot.questions]),
        )
        self._update_section(
            "#inspector-decisions",
            self._list_or_empty(snapshot.decisions),
        )
        self._update_section(
            "#inspector-post-review",
            self._list_or_empty(
                [
                    f"{item.id} "
                    f"[{display_severity_value(item.severity, lang=self.lang)}/"
                    f"{self._status_value(item.status)}] "
                    f"{item.title or item.summary}"
                    for item in snapshot.post_review_items
                ]
            ),
        )
        self._update_section(
            "#inspector-log",
            self._list_or_empty(snapshot.execution_log[-5:]),
        )

    def _update_section(self, selector: str, text: str) -> None:
        if self._section_text.get(selector) == text:
            return
        self.query_one(selector, Static).update(text)
        self._section_text[selector] = text

    def _list_or_empty(self, items: list[str], *, limit: int = 5) -> str:
        if not items:
            return self._label("empty")
        lines: list[str] = []
        for item in items[:limit]:
            if item.startswith("  "):
                lines.append(item)
            else:
                lines.append(f"- {item}")
        return "\n".join(lines)

    def _progress_summary(self, snapshot: WorkflowNexusSnapshot) -> str:
        if not snapshot.work_package_details:
            return self._label("empty")
        return "\n".join(
            [
                progress_summary_line(snapshot.work_package_details, lang=self.lang),
                progress_bar(work_package_counts(snapshot.work_package_details), width=12),
            ]
        )

    def _blocked_lines(self, snapshot: WorkflowNexusSnapshot) -> list[str]:
        lines: list[str] = []
        for package in blocked_work_packages(snapshot.work_package_details, limit=3):
            lines.append(compact_wp_line(package, lang=self.lang))
            detail = blocked_detail_line(package, lang=self.lang)
            if detail:
                lines.append(f"  {detail}")
        blocked_count = len(
            [
                package
                for package in snapshot.work_package_details
                if work_package_state(package) == "blocked"
            ]
        )
        if blocked_count > 3:
            lines.append(self._remaining_line(blocked_count - 3))
        return lines

    def _next_lines(self, snapshot: WorkflowNexusSnapshot) -> list[str]:
        all_entries = next_work_package_entries(snapshot.work_package_details, limit=None)
        entries = all_entries[:3]
        lines: list[str] = []
        for entry in entries:
            lines.append(next_work_package_line(entry, lang=self.lang))
            detail = waiting_on_detail_line(entry, lang=self.lang)
            if detail:
                lines.append(f"  {detail}")
        next_count = len(all_entries)
        if next_count > len(entries):
            lines.append(self._remaining_line(next_count - len(entries)))
        return lines

    def _label(self, key: str) -> str:
        labels = INSPECTOR_LABELS.get(self.lang, INSPECTOR_LABELS["en"])
        return labels.get(key, INSPECTOR_LABELS["en"][key])

    def _status_value(self, status: str) -> str:
        return display_status_value(
            status,
            lang=self.lang,
            empty=self._label("unknown"),
        )

    def _remaining_line(self, count: int) -> str:
        return self._label("more").format(count=count)

    def _provider_lines(self, snapshot: WorkflowNexusSnapshot) -> list[str]:
        lines: list[str] = []
        for provider in snapshot.providers:
            if not provider.enabled:
                continue
            model = provider.actual_model or provider.model_label or provider.configured_model
            context = (
                f"{provider.context_window:,}"
                if provider.context_window > 0
                else self._label("unknown")
            )
            session = (
                provider.session_id[:12]
                if provider.session_id
                else self._label("empty").strip("()")
            )
            source = display_source_value(
                provider.budget_source,
                lang=self.lang,
                empty=self._label("unknown"),
            )
            lines.append(
                f"{provider.name}: {model or self._label('default')}; "
                f"{self._label('context')} {context} "
                f"({source}); {self._label('session')} {session}"
            )
        return lines
