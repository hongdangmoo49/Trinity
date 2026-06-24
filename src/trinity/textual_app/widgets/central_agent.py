"""Central synthesis conversation widget."""

from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Grid, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, DataTable, Markdown, Static

from trinity.textual_app.snapshot import (
    LocalCommandSnapshot,
    WorkflowNexusSnapshot,
)
from trinity.textual_app.presenters import (
    central_action_plan,
    should_show_blueprint_actions,
    should_show_repair_actions,
)
from trinity.textual_app.widgets.progress_summary import (
    blocked_work_packages,
    compact_wp_line,
    current_work_packages,
    progress_summary_line,
    work_package_counts,
)
from trinity.textual_app.widgets.status_label import display_status_value


ACTIVITY_FRAMES = ("|", "/", "-", "\\")
DETAIL_SECTION_HEADINGS = {
    "acceptance criteria",
    "architecture",
    "data flow",
    "external dependencies",
    "open questions",
    "risks",
    "work packages",
    "검증 기준",
    "권장 사항",
    "데이터 흐름",
    "리스크",
    "수용 기준",
    "수용 조건",
    "아키텍처",
    "외부 의존성",
    "작업 패키지",
    "핵심 근거",
}


class CentralAgentView(VerticalScroll):
    """Render central-agent conversation, progress, and next actions."""

    class BlueprintActionRequested(Message):
        """Posted when the user chooses a blueprint-ready next action."""

        def __init__(self, action: str) -> None:
            super().__init__()
            self.action = action

    def __init__(self, *, id: str | None = None, lang: str = "en") -> None:
        super().__init__(id=id)
        self.lang = lang
        self.snapshot: WorkflowNexusSnapshot | None = None
        self._button_actions: dict[str, str] = {}
        self._action_render_version = 0
        self._activity_frame = 0
        self._markdown_key = ""
        self._local_commands_key: tuple[object, ...] = ()
        self._actions_key: tuple[object, ...] = ()

    def compose(self) -> ComposeResult:
        yield Static(self._label("title"), id="central-title")
        yield Markdown(self._markdown(), id="central-markdown")
        with Vertical(id="central-local-command-tables"):
            pass
        yield Static("", id="central-action-title")
        with Grid(id="central-actions", classes="blueprint-actions"):
            pass

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        self.snapshot = snapshot
        if not self.is_mounted:
            return
        self.set_class(self._is_running(), "central-running")
        self._refresh_title()
        markdown = self._markdown()
        if markdown != self._markdown_key:
            self.query_one("#central-markdown", Markdown).update(markdown)
            self._markdown_key = markdown
        local_commands_key = self._local_command_key(snapshot.local_commands)
        if local_commands_key != self._local_commands_key:
            self._render_local_command_tables(snapshot.local_commands)
            self._local_commands_key = local_commands_key
        actions_key = self._blueprint_actions_key(snapshot)
        if actions_key != self._actions_key:
            self._render_blueprint_actions(snapshot)
            self._actions_key = actions_key

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        action = self._button_actions.get(button_id)
        if action is not None:
            event.stop()
            self.post_message(self.BlueprintActionRequested(action))
            return
        return

    def set_activity_frame(self, frame: int) -> None:
        self._activity_frame = frame % len(ACTIVITY_FRAMES)
        self._refresh_title()

    def _markdown(self) -> str:
        snapshot = self.snapshot
        if snapshot is None:
            return (
                f"**{self._label('progress')}:** {self._label('waiting')}\n\n"
                f"{self._label('planning_no_workspace')}"
            )

        lines = [f"**{self._label('progress')}:** {self._progress_line(snapshot)}"]
        if snapshot.synthesis.consensus_progress:
            lines.append(
                f"**{self._label('synthesis')}:** `{snapshot.synthesis.consensus_progress}`"
            )
        if snapshot.goal:
            lines.extend(["", f"### {self._label('goal')}", snapshot.goal])
        central_response = self._central_response(snapshot)
        if central_response:
            lines.extend(
                [
                    "",
                    f"### {self._label('central_response')}",
                    central_response,
                ]
            )
        elif not snapshot.goal:
            lines.extend(
                [
                    "",
                    self._label("waiting"),
                    "",
                    self._label("planning_no_workspace"),
                ]
            )
        self._append_work_package_overview(lines, snapshot)
        if snapshot.local_commands:
            self._append_latest_command(lines, snapshot.local_commands[-1])
        if snapshot.final_review is not None:
            review = snapshot.final_review
            lines.extend(
                [
                    "",
                    f"### {self._label('final_review')}",
                    (
                        f"- `{self._status_value(review.status or 'unknown')}` by "
                        f"`{review.reviewer_agent or self._label('unknown')}`"
                    ),
                ]
            )
            if review.summary:
                lines.append(f"- {review.summary}")
        if snapshot.post_review_items:
            lines.extend(["", f"### {self._label('follow_up_work')}"])
            for item in snapshot.post_review_items:
                title = item.title or item.summary or item.id
                status = self._status_value(item.status)
                lines.append(
                    f"- **{item.id}** [{item.severity}][{status}] {title}"
                )
            lines.append("")
            lines.append(self._label("improve_follow_up_hint"))
        elif snapshot.state == "post_review_ready":
            lines.extend(
                [
                    "",
                    f"### {self._label('follow_up_work')}",
                    self._label("no_follow_up_items"),
                    self._label("improve_done_hint"),
                ]
            )
        return "\n".join(lines)

    def _append_work_package_overview(
        self,
        lines: list[str],
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        package_lines = snapshot.work_packages or snapshot.central_work_packages
        package_count = len(snapshot.work_package_details) or len(package_lines)
        if package_count <= 0:
            return

        lines.extend(["", f"### {self._label('work_packages')}"])
        count_text = self._package_count_text(package_count)
        if snapshot.work_package_details:
            lines.append(
                f"- {progress_summary_line(snapshot.work_package_details, lang=self.lang)}"
            )
        else:
            lines.append(f"- {count_text} · {self._label('ready')}")
        current = current_work_packages(snapshot.work_package_details, limit=1)
        if current:
            lines.append(
                f"- {self._label('current')}: "
                f"{compact_wp_line(current[0], lang=self.lang)}"
            )
        blocked = blocked_work_packages(snapshot.work_package_details, limit=1)
        if blocked:
            lines.append(
                f"- {self._label('blocked')}: "
                f"{compact_wp_line(blocked[0], lang=self.lang)}"
            )
        lines.append(f"- {self._label('details_in_inspector')}")

    def _append_execution_overview(
        self,
        lines: list[str],
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        if not snapshot.work_package_details:
            return

        active = [
            package
            for package in snapshot.work_package_details
            if package.status in {"running", "blocked"}
            or package.last_result_status in {"blocked", "failed"}
        ]
        if not active:
            return

        lines.extend(["", f"### {self._label('current_focus')}"])
        for package in active[:5]:
            executor = package.current_executor or package.last_executor or package.owner_agent
            status = package.status or package.last_result_status or "unknown"
            title = package.title or package.id
            lines.append(f"- **{package.id}** [{status}] `{executor}`: {title}")
            if package.last_result_summary:
                lines.append(f"  - {package.last_result_summary}")
            blockers = self._compact_list(package.last_result_blockers, limit=2)
            if blockers:
                lines.append(f"  - Blockers: {blockers}")

    def _append_latest_command(
        self,
        lines: list[str],
        command: LocalCommandSnapshot,
    ) -> None:
        lines.extend(
            [
                "",
                f"### {self._label('command_result')}",
                f"**{command.command} - {command.title}**",
                command.body,
            ]
        )
        if command.action_hint:
            lines.append(f"_{self._label('next')}:_ {command.action_hint}")

    @staticmethod
    def _compact_list(values: list[str], *, limit: int = 5) -> str:
        items = [value for value in values if value]
        if not items:
            return ""
        rendered = ", ".join(items[:limit])
        remaining = len(items) - limit
        if remaining > 0:
            rendered = f"{rendered}, +{remaining} more"
        return rendered

    def _central_response(self, snapshot: WorkflowNexusSnapshot) -> str:
        source = snapshot.central_blueprint.strip() or snapshot.synthesis.summary.strip()
        if not source:
            return ""

        lines: list[str] = []
        visible_count = 0
        for raw_line in source.splitlines():
            line = raw_line.strip()
            if not line:
                if lines and lines[-1] != "":
                    lines.append("")
                continue
            if self._is_detail_section_heading(line):
                break
            if self._is_low_value_blueprint_bullet(line):
                if visible_count:
                    break
                continue
            lines.append(self._strip_markdown_links(line))
            visible_count += 1
            if visible_count >= 4:
                break

        while lines and lines[-1] == "":
            lines.pop()
        compact = "\n".join(lines).strip()
        if not compact:
            compact = snapshot.synthesis.summary.strip()
        return self._truncate_response(compact)

    @staticmethod
    def _is_detail_section_heading(line: str) -> bool:
        normalized = re.sub(r"^[#>\-\*\s•]+", "", line).strip()
        normalized = re.sub(r"^\d+[.)]\s+", "", normalized).strip()
        normalized = normalized.strip("*`：: ")
        lowered = normalized.lower()
        return any(
            lowered == heading or lowered.startswith(f"{heading} ")
            for heading in DETAIL_SECTION_HEADINGS
        )

    @staticmethod
    def _is_low_value_blueprint_bullet(line: str) -> bool:
        normalized = line.lstrip()
        if not normalized.startswith(("- ", "* ", "• ")):
            return False
        return any(
            marker in normalized.lower()
            for marker in ("file://", "expected file", "acceptance", "수용 기준")
        )

    @staticmethod
    def _strip_markdown_links(line: str) -> str:
        return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)

    @staticmethod
    def _truncate_response(text: str, *, limit: int = 700) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    def _package_count_text(self, count: int) -> str:
        if self.lang == "ko":
            return f"{count}개 작업 패키지"
        word = "package" if count == 1 else "packages"
        return f"{count} {word}"

    def _render_local_command_tables(
        self,
        commands: list[LocalCommandSnapshot],
    ) -> None:
        container = self.query_one("#central-local-command-tables", Vertical)
        container.remove_children()
        table_commands = [
            command
            for command in commands[-1:]
            if command.table_columns and command.table_rows
        ]
        if not table_commands:
            return

        for command in table_commands:
            container.mount(
                Static(
                    f"{command.command} - {command.title}",
                    classes="local-command-table-title",
                )
            )
            table = DataTable(
                classes="local-command-table",
                show_header=True,
                show_cursor=False,
                cursor_type="none",
            )
            container.mount(table)
            table.add_columns(*command.table_columns)
            table.add_rows(command.table_rows)

    @staticmethod
    def _local_command_key(commands: list[LocalCommandSnapshot]) -> tuple[object, ...]:
        return tuple(
            (
                command.command,
                command.title,
                command.body,
                command.action_hint,
                command.empty,
                tuple(command.table_columns),
                tuple(tuple(row) for row in command.table_rows),
            )
            for command in commands[-1:]
        )

    def _progress_line(self, snapshot: WorkflowNexusSnapshot) -> str:
        open_questions = sum(1 for question in snapshot.questions if not question.answer)
        if open_questions:
            return f"{self._label('awaiting_answers')} ({open_questions})"
        if snapshot.state in {"preflight", "deliberating"}:
            return self._label("collecting_provider_responses")
        if snapshot.synthesis.status in {"running", "waiting"}:
            return self._label("synthesizing")
        if snapshot.state == "blueprint_ready":
            return self._label("blueprint_ready")
        if snapshot.state == "executing":
            return self._execution_progress(snapshot)
        if snapshot.state == "reviewing":
            return self._label("reviewing")
        if snapshot.state == "post_review_ready":
            return self._label("post_review_ready")
        if snapshot.state == "needs_user_decision":
            return self._label("awaiting_decision")
        if snapshot.state == "completed":
            return self._label("completed")
        return snapshot.state or self._label("idle")

    def _execution_progress(self, snapshot: WorkflowNexusSnapshot) -> str:
        counts = work_package_counts(snapshot.work_package_details)
        if not counts:
            return self._label("executing")
        done = counts.get("done", 0)
        running = counts.get("running", 0)
        blocked = counts.get("blocked", 0)
        waiting = counts.get("waiting", 0)
        parts = [
            self._progress_count(done, "done"),
            self._progress_count(running, "running"),
            self._progress_count(waiting, "waiting"),
        ]
        if blocked:
            parts.append(self._progress_count(blocked, "blocked"))
        return (
            f"{self._label('executing')}: "
            + " / ".join(parts)
        )

    def _status_value(self, value: str) -> str:
        return display_status_value(value, lang=self.lang)

    def _progress_count(self, count: int, key: str) -> str:
        return f"{count} {self._label(f'progress_{key}')}"

    @staticmethod
    def _blueprint_actions_key(snapshot: WorkflowNexusSnapshot) -> tuple[object, ...]:
        return (
            snapshot.state,
            tuple(snapshot.central_work_packages),
            tuple(snapshot.work_packages),
            (
                snapshot.execution_recovery.state
                if snapshot.execution_recovery is not None
                else ""
            ),
            (
                tuple(snapshot.execution_recovery.retry_candidates)
                if snapshot.execution_recovery is not None
                else ()
            ),
            tuple(
                (
                    package.id,
                    package.status,
                    package.repair_blocked_reason,
                    package.repair_attempt_count,
                )
                for package in snapshot.work_package_details
            ),
        )

    @staticmethod
    def _should_show_repair_actions(snapshot: WorkflowNexusSnapshot) -> bool:
        return should_show_repair_actions(snapshot)

    @staticmethod
    def _should_show_blueprint_actions(snapshot: WorkflowNexusSnapshot) -> bool:
        return should_show_blueprint_actions(snapshot)

    def _render_blueprint_actions(self, snapshot: WorkflowNexusSnapshot) -> None:
        title = self.query_one("#central-action-title", Static)
        container = self.query_one("#central-actions", Grid)
        container.remove_children()
        self._button_actions = {}
        self._action_render_version += 1
        render_version = self._action_render_version

        plan = central_action_plan(snapshot)
        if not plan.buttons:
            title.update("")
            return

        title.update(self._label(plan.title_key))
        for button in plan.buttons:
            button_id = f"central-action-{render_version}-{button.action}"
            self._button_actions[button_id] = button.action
            container.mount(
                Button(
                    self._label(button.label_key),
                    id=button_id,
                    variant=button.variant,
                    tooltip=self._label(button.tooltip_key),
                )
            )

    def _label(self, key: str) -> str:
        ko = {
            "awaiting_answers": "사용자 답변 대기",
            "awaiting_decision": "사용자 결정 대기",
            "blueprint_ready": "설계가 준비되었습니다",
            "central_response": "중앙 에이전트 응답",
            "collecting_provider_responses": "프로바이더 응답을 모으는 중",
            "command_result": "명령 결과",
            "completed": "완료",
            "blocked": "막힘",
            "current": "현재",
            "current_focus": "현재 진행/주의 항목",
            "details_in_inspector": "상세 설계와 WP 목록은 Inspector 또는 Report에서 확인하세요.",
            "executing": "실행 중",
            "final_review": "최종 리뷰",
            "follow_up_work": "후속 보강 작업",
            "goal": "목표",
            "idle": "대기",
            "improve_done_hint": "`/improve done`으로 워크플로우를 종료하세요.",
            "improve_follow_up_hint": (
                "`/improve high`, `/improve all`, `/improve AI-001`, "
                "`/improve done` 중 하나를 실행하세요."
            ),
            "next": "다음",
            "next_action": "다음 작업",
            "no_follow_up_items": "최종 리뷰에서 추가 작업 항목이 추출되지 않았습니다.",
            "planning_no_workspace": "기획은 작업 폴더 없이 진행할 수 있습니다. 실행 시 작업 폴더를 선택합니다.",
            "post_review_ready": "최종 리뷰 이후 보강 선택 대기",
            "provider_error_action": "프로바이더 오류 결정",
            "provider_error_retry": "실패 재시도",
            "provider_error_continue": "제외하고 계속",
            "provider_error_stop": "중단",
            "progress": "진행",
            "progress_blocked": "막힘",
            "progress_done": "완료",
            "progress_running": "실행중",
            "progress_waiting": "대기",
            "ready": "준비됨",
            "reviewing": "리뷰 중",
            "repair_action": "리뷰 수리 결정",
            "synthesis": "종합",
            "synthesizing": "중앙 에이전트 종합 중",
            "title": "중앙 에이전트",
            "unknown": "(알 수 없음)",
            "waiting": "종합 대기 중",
            "work_packages": "작업 패키지",
            "execute": "실행",
            "execution_recovery_action": "실행 재시도 결정",
            "execution_retry": "실패 WP 재시도",
            "refine_features": "기능 보강",
            "refine_risks": "리스크 보강",
            "refine_work_packages": "WP 재분배",
            "repair_retry_once": "한 번 더 재시도",
            "repair_mark_done": "완료 처리",
            "repair_open_review": "리뷰 보기",
            "repair_stop": "중단",
            "execute_tooltip": "현재 WP를 실행합니다.",
            "execution-retry_tooltip": "실패, 막힘, 중단 상태의 WP를 선택해서 다시 실행합니다.",
            "refine-features_tooltip": "기능 범위와 사용자 경험을 더 구체화합니다.",
            "refine-risks_tooltip": "실행 리스크와 검증 기준을 더 구체화합니다.",
            "refine-work-packages_tooltip": "WP 분해, 담당자, 의존성을 다시 정리합니다.",
            "repair-retry-once_tooltip": "리뷰 수리로 막힌 WP만 한 번 더 실행합니다.",
            "repair-mark-done_tooltip": "막힌 리뷰 수리를 사용자가 수용하고 WP를 완료 처리합니다.",
            "repair-open-review_tooltip": "현재 리뷰 수리 차단 상세를 봅니다.",
            "repair-stop_tooltip": "현재 워크플로우를 중단합니다.",
            "provider-error-retry_tooltip": "오류가 난 프로바이더 응답만 다시 요청합니다.",
            "provider-error-continue_tooltip": "오류 응답을 제외하고 현재 중앙 집계를 적용합니다.",
            "provider-error-stop_tooltip": "프로바이더 오류 이후 워크플로우를 중단합니다.",
        }
        en = {
            "awaiting_answers": "Waiting for your answer",
            "awaiting_decision": "Waiting for your decision",
            "blueprint_ready": "Blueprint ready",
            "central_response": "Central Agent Response",
            "collecting_provider_responses": "Collecting provider responses",
            "command_result": "Command Result",
            "completed": "Completed",
            "blocked": "Blocked",
            "current": "Current",
            "current_focus": "Current Focus",
            "details_in_inspector": "Open Inspector or Report for the full design and WP list.",
            "executing": "Executing",
            "final_review": "Final Review",
            "follow_up_work": "Suggested Follow-up Work",
            "goal": "Goal",
            "idle": "Idle",
            "improve_done_hint": "Use `/improve done` to close the workflow.",
            "improve_follow_up_hint": (
                "Use `/improve high`, `/improve all`, `/improve AI-001`, "
                "or `/improve done`."
            ),
            "next": "Next",
            "next_action": "Next action",
            "no_follow_up_items": "No action items were extracted from the final review.",
            "planning_no_workspace": "Planning does not require a workspace. Execute will ask for one.",
            "post_review_ready": "Post-review follow-up ready",
            "provider_error_action": "Provider error decision",
            "provider_error_retry": "Retry failed",
            "provider_error_continue": "Continue without",
            "provider_error_stop": "Stop",
            "progress": "Progress",
            "progress_blocked": "blocked",
            "progress_done": "done",
            "progress_running": "running",
            "progress_waiting": "waiting",
            "ready": "ready",
            "reviewing": "Reviewing",
            "repair_action": "Review repair decision",
            "synthesis": "Synthesis",
            "synthesizing": "Central agent is synthesizing",
            "title": "Central Agent",
            "unknown": "(unknown)",
            "waiting": "Waiting for synthesis",
            "work_packages": "Work Packages",
            "execute": "Execute",
            "execution_recovery_action": "Execution retry decision",
            "execution_retry": "Retry failed WPs",
            "refine_features": "Refine features",
            "refine_risks": "Refine risks",
            "refine_work_packages": "Rebalance WPs",
            "repair_retry_once": "Retry once",
            "repair_mark_done": "Mark done",
            "repair_open_review": "Open review",
            "repair_stop": "Stop",
            "execute_tooltip": "Run the current work packages.",
            "execution-retry_tooltip": "Choose failed, blocked, or interrupted WPs to run again.",
            "refine-features_tooltip": "Clarify feature scope and user experience.",
            "refine-risks_tooltip": "Clarify execution risks and validation criteria.",
            "refine-work-packages_tooltip": "Revise WP ownership, scope, and dependencies.",
            "repair-retry-once_tooltip": "Retry only the WPs paused by review repair guards.",
            "repair-mark-done_tooltip": "Accept the blocked repair and mark the WP done.",
            "repair-open-review_tooltip": "Show the current review repair details.",
            "repair-stop_tooltip": "Stop the current workflow.",
            "provider-error-retry_tooltip": "Retry only providers that returned errors.",
            "provider-error-continue_tooltip": "Apply the current synthesis without failed providers.",
            "provider-error-stop_tooltip": "Stop the workflow after provider errors.",
        }
        labels = ko if self.lang == "ko" else en
        return labels.get(key, key)

    def _refresh_title(self) -> None:
        if not self.is_mounted:
            return
        title = self._label("title")
        if self._is_running():
            title = f"{title} {ACTIVITY_FRAMES[self._activity_frame]}"
        self.query_one("#central-title", Static).update(title)

    def _is_running(self) -> bool:
        snapshot = self.snapshot
        return bool(
            snapshot
            and (
                snapshot.synthesis.status in {"running", "waiting"}
                or snapshot.state in {"preflight", "deliberating", "executing", "reviewing"}
            )
        )
