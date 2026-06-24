"""Work package design detail modal."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Markdown, Static

from trinity.display_labels import display_risk_value, display_severity_value
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.snapshot import WorkPackageSnapshot
from trinity.textual_app.widgets.status_label import display_status_value

_LABELS = {
    "ko": {
        "acceptance_criteria": "수락 기준",
        "action_context": "액션 컨텍스트",
        "additional_blockers": "추가 차단 요소",
        "agent": "에이전트",
        "available": "가능",
        "blocked_reason": "차단 사유",
        "blockers": "차단 요소",
        "blocking_evidence": "차단 근거",
        "close": "닫기",
        "dependencies": "의존성",
        "execution_lane": "실행 레인",
        "executor": "실행자",
        "expected_files": "예상 파일",
        "fallback_attempts": "폴백 시도",
        "files_changed": "변경 파일",
        "no_execution_result": "(아직 실행 결과 없음)",
        "no_review": "(기록된 리뷰 없음)",
        "none": "(없음)",
        "not_available": "불가",
        "no_retry_candidate": "기록된 재시도 후보가 없습니다.",
        "objective": "목표",
        "out_of_scope": "제외 범위",
        "owner": "소유자",
        "peer_review_skipped": "Peer review가 생략되었습니다. 신뢰도를 낮게 보세요.",
        "profile_revision": "프로필 리비전",
        "repair_attempts": "복구 시도",
        "repair_loop_blocked": "복구 루프가 `{attempts}` 시도 후 차단됨",
        "repair_notes": "복구 메모",
        "requires_execution": "실행 필요",
        "required_changes": "필수 변경",
        "result": "결과",
        "retry": "재시도",
        "retry_candidate": "재시도 후보",
        "retry_unavailable": "재시도 불가",
        "review": "리뷰",
        "review_blocked": "리뷰가 `{status}` 상태입니다. 리뷰 메모를 확인하세요.",
        "review_changes": "리뷰가 완료 전 {count}개 변경을 요청했습니다.",
        "review_changes_no_count": "리뷰가 완료 전 변경을 요청했습니다.",
        "review_plan": "리뷰 계획",
        "review_skipped_reason": "리뷰 생략 사유",
        "reviewer_count": "리뷰어 수",
        "reviewer": "리뷰어",
        "second_review_pending": "2차 리뷰가 대기 중입니다.",
        "serial_lane": "직렬",
        "risk": "리스크",
        "routing_reason": "라우팅 사유",
        "routing_score": "라우팅 점수",
        "scope": "범위",
        "severity": "심각도",
        "spec": "명세",
        "status": "상태",
        "summary": "요약",
        "task_kind": "작업 유형",
        "title": "제목",
        "topic": "주제",
        "unspecified_lane": "미지정",
        "unknown": "알 수 없음",
        "yes": "예",
        "no": "아니오",
    },
    "en": {
        "acceptance_criteria": "Acceptance Criteria",
        "action_context": "Action Context",
        "additional_blockers": "Additional blockers",
        "agent": "Agent",
        "available": "available",
        "blocked_reason": "Blocked reason",
        "blockers": "Blockers",
        "blocking_evidence": "Blocking evidence",
        "close": "Close",
        "dependencies": "Dependencies",
        "execution_lane": "Execution lane",
        "executor": "Executor",
        "expected_files": "Expected Files",
        "fallback_attempts": "Fallback Attempts",
        "files_changed": "Files Changed",
        "no_execution_result": "(no execution result yet)",
        "no_review": "(no review recorded)",
        "none": "(none)",
        "not_available": "not available",
        "no_retry_candidate": "no retry candidate is recorded.",
        "objective": "Objective",
        "out_of_scope": "Out of Scope",
        "owner": "Owner",
        "peer_review_skipped": "Peer review was skipped; treat confidence as lower.",
        "profile_revision": "Profile revision",
        "repair_attempts": "Repair attempts",
        "repair_loop_blocked": "Repair loop blocked after `{attempts}` attempts",
        "repair_notes": "Repair Notes",
        "requires_execution": "Requires execution",
        "required_changes": "Required Changes",
        "result": "Result",
        "retry": "Retry",
        "retry_candidate": "Retry candidate",
        "retry_unavailable": "Retry unavailable",
        "review": "Review",
        "review_blocked": "Review is `{status}`; inspect review notes.",
        "review_changes": "Review requested {count} change{plural} before completion.",
        "review_changes_no_count": "Review requested changes before completion.",
        "review_plan": "Review Plan",
        "review_skipped_reason": "Review skipped reason",
        "reviewer_count": "Reviewer count",
        "reviewer": "Reviewer",
        "second_review_pending": "Second review is pending.",
        "serial_lane": "serial",
        "risk": "Risk",
        "routing_reason": "Routing reason",
        "routing_score": "Routing score",
        "scope": "Scope",
        "severity": "Severity",
        "spec": "Spec",
        "status": "Status",
        "summary": "Summary",
        "task_kind": "Task kind",
        "title": "Title",
        "topic": "Topic",
        "unspecified_lane": "unspecified",
        "unknown": "unknown",
        "yes": "yes",
        "no": "no",
    },
}

class WorkPackageDetailModal(ModalScreen[None]):
    """Show the full design and latest execution state for one work package."""

    DEFAULT_CSS = """
    WorkPackageDetailModal {
        align: center middle;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    LOCALIZED_BINDINGS = {
        ("escape", "close"): ("binding_close", None),
    }

    def __init__(self, package: WorkPackageSnapshot, *, lang: str = "en") -> None:
        super().__init__()
        self.package = package
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        with Vertical(id="work-package-detail-modal"):
            yield Static(
                self._title_text(),
                id="work-package-detail-title",
            )
            with VerticalScroll(id="work-package-detail-body"):
                yield Markdown(self._markdown())
            yield Button(self._label("close"), id="close-work-package-detail")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "close-work-package-detail":
            return
        event.stop()
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

    def _markdown(self) -> str:
        package = self.package
        lines = [
            f"## {self._label('summary')}",
            f"- {self._label('title')}: {package.title or package.topic or package.id}",
            f"- {self._label('status')}: `{self._status_value(package.status or 'pending')}`",
            f"- {self._label('owner')}: `{package.owner_agent or '-'}`",
            f"- {self._label('executor')}: `{package.current_executor or package.last_executor or '-'}`",
            f"- {self._label('review')}: `{self._status_value(package.review_status)}`",
            f"- {self._label('risk')}: `{self._risk_value(package.risk)}`",
            f"- {self._label('execution_lane')}: `{self._execution_lane_label(package)}`",
            f"- {self._label('requires_execution')}: `{self._yes_no(package.requires_execution)}`",
            f"- {self._label('retry')}: `{self._retry_summary(package)}`",
        ]
        if package.topic and package.topic != package.title:
            lines.insert(2, f"- {self._label('topic')}: {package.topic}")
        if package.repair_attempt_count or package.repair_blocked_reason:
            attempts = (
                f"{package.repair_attempt_count}/{package.repair_max_attempts}"
                if package.repair_max_attempts
                else str(package.repair_attempt_count)
            )
            lines.append(f"- {self._label('repair_attempts')}: `{attempts}`")
        if package.repair_blocked_reason:
            lines.append(f"- {self._label('blocked_reason')}: `{package.repair_blocked_reason}`")
        if package.task_kind or package.routing_reason:
            lines.extend(
                [
                    f"- {self._label('task_kind')}: `{package.task_kind or '-'}`",
                    f"- {self._label('routing_score')}: `{package.routing_score:.1f}`",
                    f"- {self._label('routing_reason')}: {package.routing_reason or self._label('none')}",
                    f"- {self._label('profile_revision')}: `{package.profile_revision or '-'}`",
                ]
            )

        lines.extend(["", f"## {self._label('action_context')}"])
        lines.extend(self._action_context_lines(package))

        lines.extend(["", f"## {self._label('result')}"])
        if package.last_result_status or package.last_result_summary:
            lines.extend(
                [
                    f"- {self._label('agent')}: `{package.last_result_agent or '-'}`",
                    f"- {self._label('status')}: `{self._status_value(package.last_result_status)}`",
                    f"- {self._label('summary')}: {package.last_result_summary or self._label('none')}",
                ]
            )
            self._append_list(lines, "files_changed", package.last_result_files_changed)
            self._append_list(lines, "blockers", package.last_result_blockers)
            self._append_list(
                lines,
                "fallback_attempts",
                package.last_result_attempt_chain,
            )
        else:
            lines.append(self._label("no_execution_result"))

        review_plan_lines = self._review_plan_lines(package)
        if review_plan_lines:
            lines.extend(["", f"## {self._label('review_plan')}"])
            lines.extend(review_plan_lines)

        lines.extend(["", f"## {self._label('review')}"])
        if package.review_status or package.review_summary:
            lines.extend(
                [
                    f"- {self._label('reviewer')}: `{package.reviewer_agent or '-'}`",
                    f"- {self._label('status')}: `{self._status_value(package.review_status)}`",
                    f"- {self._label('severity')}: `{self._severity_value(package.review_severity)}`",
                    f"- {self._label('summary')}: {package.review_summary or self._label('none')}",
                ]
            )
            self._append_list(
                lines,
                "required_changes",
                package.review_required_changes,
            )
        else:
            lines.append(self._label("no_review"))

        lines.extend(
            [
                "",
                f"## {self._label('spec')}",
                f"### {self._label('objective')}",
                package.objective or self._label("none"),
            ]
        )
        self._append_list(lines, "scope", package.scope)
        self._append_list(lines, "out_of_scope", package.out_of_scope)
        self._append_list(lines, "dependencies", package.dependencies)
        self._append_list(lines, "expected_files", package.expected_files)
        self._append_list(lines, "acceptance_criteria", package.acceptance_criteria)
        self._append_list(lines, "repair_notes", package.repair_notes)
        return "\n".join(lines)

    def _append_list(self, lines: list[str], title_key: str, values: list[str]) -> None:
        if not values:
            return
        lines.extend(["", f"## {self._label(title_key)}"])
        lines.extend(f"- {value}" for value in values)

    def _action_context_lines(self, package: WorkPackageSnapshot) -> list[str]:
        lines: list[str] = []
        if package.retryable:
            lines.append(f"- {self._label('retry_candidate')}: `{package.id}`")
        elif package.retry_disabled_reason:
            lines.append(
                f"- {self._label('retry_unavailable')}: "
                f"{package.retry_disabled_reason}"
            )
        else:
            lines.append(
                f"- {self._label('retry_unavailable')}: "
                f"{self._label('no_retry_candidate')}"
            )

        blockers = [value for value in package.last_result_blockers if value]
        if blockers:
            lines.append(f"- {self._label('blocking_evidence')}: {blockers[0]}")
            if len(blockers) > 1:
                lines.append(f"- {self._label('additional_blockers')}: {len(blockers) - 1}")

        if package.repair_blocked_reason:
            attempts = (
                f"{package.repair_attempt_count}/{package.repair_max_attempts}"
                if package.repair_max_attempts
                else str(package.repair_attempt_count)
            )
            lines.append(
                f"- {self._label('repair_loop_blocked').format(attempts=attempts)}: "
                f"{package.repair_blocked_reason}"
            )

        if package.review_status == "changes_requested":
            change_count = len(package.review_required_changes)
            if change_count:
                plural = "" if change_count == 1 else "s"
                lines.append(
                    "- "
                    + self._label("review_changes").format(
                        count=change_count,
                        plural=plural,
                    )
                )
            else:
                lines.append(f"- {self._label('review_changes_no_count')}")
        elif package.review_status in {"blocked", "failed"}:
            lines.append(
                "- "
                + self._label("review_blocked").format(
                    status=self._status_value(package.review_status)
                )
            )
        elif package.review_status == "skipped":
            if package.review_summary:
                lines.append(
                    f"- {self._label('review_skipped_reason')}: "
                    f"{package.review_summary}"
                )
            else:
                lines.append(f"- {self._label('peer_review_skipped')}")

        return lines

    def _review_plan_lines(self, package: WorkPackageSnapshot) -> list[str]:
        if not (package.review_status or package.reviewer_agent or package.review_summary):
            return []

        reviewer_names = _reviewer_names(package.reviewer_agent)
        lines = [
            f"- {self._label('status')}: `{self._status_value(package.review_status)}`",
            f"- {self._label('reviewer')}: `{package.reviewer_agent or '-'}`",
            f"- {self._label('reviewer_count')}: `{len(reviewer_names)}`",
        ]
        if package.review_status == "skipped" and package.review_summary:
            lines.append(
                f"- {self._label('review_skipped_reason')}: "
                f"{package.review_summary}"
            )
        if package.review_status == "needs_second_review":
            lines.append(f"- {self._label('second_review_pending')}")
        return lines

    def _retry_summary(self, package: WorkPackageSnapshot) -> str:
        if package.retryable:
            return self._label("available")
        return package.retry_disabled_reason or self._label("not_available")

    def _title_text(self) -> str:
        return _clip(f"{self.package.id}: {self.package.title or self.package.topic}", 86)

    def _yes_no(self, value: bool) -> str:
        return self._label("yes" if value else "no")

    def _status_value(self, value: str) -> str:
        return display_status_value(value, lang=self.lang)

    def _risk_value(self, value: str) -> str:
        return display_risk_value(value, lang=self.lang, empty=self._label("unknown"))

    def _severity_value(self, value: str) -> str:
        return display_severity_value(value, lang=self.lang)

    def _label(self, key: str) -> str:
        labels = _LABELS.get(self.lang, _LABELS["en"])
        return labels.get(key, _LABELS["en"].get(key, key))

    def _execution_lane_label(self, package: WorkPackageSnapshot) -> str:
        if not package.parallelizable:
            return self._label("serial_lane")
        if package.parallel_group is not None:
            return f"g{package.parallel_group}"
        return self._label("unspecified_lane")


def _clip(value: str, width: int) -> str:
    clean = " ".join(str(value).split())
    if len(clean) <= width:
        return clean
    if width <= 3:
        return clean[:width]
    return clean[: width - 3] + "..."


def _reviewer_names(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]
