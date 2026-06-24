"""Pure presentation helpers for Textual workflow snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
from typing import Sequence

from trinity.slash_commands import COMMAND_SPECS
from trinity.textual_app.snapshot import WorkflowNexusSnapshot

NO_CURRENT_CONTEXT_MESSAGE = (
    "No current session context. Start a prompt or resume a workflow first."
)

STATUS_CONTEXT_LABELS = {
    "en": {
        "answer": "Answer",
        "decisions": "Decisions",
        "done_packages": "Done packages",
        "enabled": "Enabled",
        "execution": "Execution",
        "execution_log_entries": "Execution log entries",
        "execution_recovery": "Execution Recovery",
        "execution_recovery_none": "No interrupted execution is recorded for this workflow.",
        "execution_results": "Execution Results",
        "final_review": "Final Review",
        "follow_up_requests": "Follow-up Requests",
        "goal": "Goal",
        "id": "ID",
        "item": "Item",
        "last_event": "Last event",
        "local_policy_repairs": "Local Policy Repairs",
        "next": "Next",
        "no": "no",
        "not_checked": "not checked",
        "pending_questions": "Pending questions",
        "post_review_action_items": "Post Review Action Items",
        "post_review_items": "Post-review items",
        "provider": "Provider",
        "questions": "Questions",
        "readiness": "Readiness",
        "reattach_note": (
            "Provider process reattach is not supported. Retry starts a new "
            "one-shot execution only for interrupted, failed, or blocked packages."
        ),
        "retry_candidates": "Retry candidates",
        "reviewer": "reviewer",
        "round": "Round",
        "run": "Run",
        "running_packages": "Running packages",
        "running_packages_at_exit": "Running packages at exit",
        "state": "State",
        "status": "Status",
        "subtasks": "Subtasks",
        "supplemental_rounds": "Supplemental rounds",
        "synthesis": "Synthesis",
        "target": "Target",
        "value": "Value",
        "workflow": "Workflow",
        "workflow_history": "Workflow History",
        "work_packages": "Work Packages",
        "yes": "yes",
    },
    "ko": {
        "answer": "답변",
        "decisions": "결정",
        "done_packages": "완료 WP",
        "enabled": "활성화",
        "execution": "실행",
        "execution_log_entries": "실행 로그 항목",
        "execution_recovery": "실행 복구",
        "execution_recovery_none": "이 워크플로우에 기록된 중단 실행이 없습니다.",
        "execution_results": "실행 결과",
        "final_review": "최종 리뷰",
        "follow_up_requests": "후속 요청",
        "goal": "목표",
        "id": "ID",
        "item": "항목",
        "last_event": "최근 이벤트",
        "local_policy_repairs": "로컬 정책 복구",
        "next": "다음",
        "no": "아니오",
        "not_checked": "미확인",
        "pending_questions": "대기 중 질문",
        "post_review_action_items": "리뷰 후 조치",
        "post_review_items": "리뷰 후 조치",
        "provider": "프로바이더",
        "questions": "질문",
        "readiness": "준비 상태",
        "reattach_note": (
            "프로바이더 프로세스 재연결은 지원하지 않습니다. 재시도는 중단, 실패, "
            "차단된 작업에 대해 새 단발 실행을 시작합니다."
        ),
        "retry_candidates": "재시도 후보",
        "reviewer": "리뷰어",
        "round": "라운드",
        "run": "실행 ID",
        "running_packages": "실행 중 WP",
        "running_packages_at_exit": "종료 시 실행 중 WP",
        "state": "상태",
        "status": "상태",
        "subtasks": "하위 작업",
        "supplemental_rounds": "보충 라운드",
        "synthesis": "종합",
        "target": "대상",
        "value": "값",
        "workflow": "워크플로우",
        "workflow_history": "워크플로우 이력",
        "work_packages": "작업 패키지",
        "yes": "예",
    },
}


@dataclass(frozen=True)
class CentralActionButton:
    """One central Nexus action button to render."""

    action: str
    label_key: str
    variant: str = "default"
    tooltip_key: str = ""


@dataclass(frozen=True)
class CentralActionPlan:
    """Pure presenter result for central Nexus action buttons."""

    title_key: str = ""
    buttons: tuple[CentralActionButton, ...] = ()


def central_action_plan(snapshot: WorkflowNexusSnapshot) -> CentralActionPlan:
    """Return the highest-priority central action group for a snapshot."""
    provider_error_options = provider_error_gate_options(snapshot)
    if provider_error_options:
        buttons = [
            CentralActionButton(
                "provider-error-retry",
                "provider_error_retry",
                "primary",
                "provider-error-retry_tooltip",
            )
        ]
        if "Continue without failed providers" in provider_error_options:
            buttons.append(
                CentralActionButton(
                    "provider-error-continue",
                    "provider_error_continue",
                    "default",
                    "provider-error-continue_tooltip",
                )
            )
        buttons.append(
            CentralActionButton(
                "provider-error-stop",
                "provider_error_stop",
                "error",
                "provider-error-stop_tooltip",
            )
        )
        return CentralActionPlan("provider_error_action", tuple(buttons))

    if should_show_repair_actions(snapshot):
        return CentralActionPlan(
            "repair_action",
            (
                CentralActionButton(
                    "repair-retry-once",
                    "repair_retry_once",
                    "primary",
                    "repair-retry-once_tooltip",
                ),
                CentralActionButton(
                    "repair-mark-done",
                    "repair_mark_done",
                    "default",
                    "repair-mark-done_tooltip",
                ),
                CentralActionButton(
                    "repair-open-review",
                    "repair_open_review",
                    "default",
                    "repair-open-review_tooltip",
                ),
                CentralActionButton(
                    "repair-stop",
                    "repair_stop",
                    "error",
                    "repair-stop_tooltip",
                ),
            ),
        )

    if should_show_execution_retry_action(snapshot):
        return CentralActionPlan(
            "execution_recovery_action",
            (
                CentralActionButton(
                    "execution-retry",
                    "execution_retry",
                    "primary",
                    "execution-retry_tooltip",
                ),
            ),
        )

    if should_show_blueprint_actions(snapshot):
        return CentralActionPlan(
            "next_action",
            (
                CentralActionButton("execute", "execute", "primary", "execute_tooltip"),
                CentralActionButton(
                    "refine-features",
                    "refine_features",
                    "default",
                    "refine-features_tooltip",
                ),
                CentralActionButton(
                    "refine-risks",
                    "refine_risks",
                    "default",
                    "refine-risks_tooltip",
                ),
                CentralActionButton(
                    "refine-work-packages",
                    "refine_work_packages",
                    "default",
                    "refine-work-packages_tooltip",
                ),
            ),
        )

    return CentralActionPlan()


def should_show_blueprint_actions(snapshot: WorkflowNexusSnapshot) -> bool:
    return snapshot.state == "blueprint_ready" and bool(
        snapshot.work_packages or snapshot.central_work_packages
    )


def should_show_repair_actions(snapshot: WorkflowNexusSnapshot) -> bool:
    recovery = snapshot.execution_recovery
    if recovery and recovery.state == "repair_blocked":
        return True
    if snapshot.state != "needs_user_decision":
        return False
    return any(
        package.status == "blocked" and package.repair_blocked_reason
        for package in snapshot.work_package_details
    )


def should_show_execution_retry_action(snapshot: WorkflowNexusSnapshot) -> bool:
    recovery = snapshot.execution_recovery
    if recovery is None:
        return False
    if recovery.state == "repair_blocked":
        return False
    return bool(recovery.retry_candidates)


def provider_error_gate_options(snapshot: WorkflowNexusSnapshot) -> set[str]:
    for question in snapshot.questions:
        if question.id == "q-provider-error-retry" and not question.answer:
            return set(question.options)
    return set()


def review_repair_blocked_ids(snapshot: WorkflowNexusSnapshot) -> tuple[str, ...]:
    package_ids: list[str] = []
    seen: set[str] = set()
    for package in snapshot.work_package_details:
        if package.status != "blocked" or not package.repair_blocked_reason:
            continue
        package_id = package.id.strip()
        if package_id and package_id not in seen:
            package_ids.append(package_id)
            seen.add(package_id)
    recovery = snapshot.execution_recovery
    if recovery is not None and recovery.state == "repair_blocked":
        for package_id in recovery.retry_candidates:
            normalized = str(package_id).strip()
            if normalized and normalized not in seen:
                package_ids.append(normalized)
                seen.add(normalized)
    return tuple(package_ids)


def review_repair_details_markdown(snapshot: WorkflowNexusSnapshot) -> str:
    rows = review_repair_rows(snapshot)
    if not rows:
        return "No review-repair blocked work packages are recorded."
    lines = ["Review-repair loop guard has paused these work packages:"]
    for package_id, detail in rows:
        lines.append(f"- **{package_id}**: {detail}")
    if snapshot.work_package_repairs:
        lines.extend(["", "### Recent repair notes"])
        lines.extend(f"- {item}" for item in snapshot.work_package_repairs)
    return "\n".join(lines)


def review_repair_rows(snapshot: WorkflowNexusSnapshot) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for package in snapshot.work_package_details:
        if package.status != "blocked" or not package.repair_blocked_reason:
            continue
        seen.add(package.id)
        rows.append(
            (
                package.id,
                (
                    f"{package.repair_blocked_reason}; "
                    f"attempts={package.repair_attempt_count}/"
                    f"{package.repair_max_attempts}; "
                    f"review={package.review_status or '(none)'}"
                ),
            )
        )
    recovery = snapshot.execution_recovery
    if recovery is not None and recovery.state == "repair_blocked":
        for package_id in recovery.retry_candidates:
            normalized = str(package_id).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            rows.append(
                (
                    normalized,
                    "repair_blocked; attempts=(unknown); review=(recovery)",
                )
            )
    return tuple(rows)


def status_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return (_sc_label(lang, "item"), _sc_label(lang, "value"))


def execution_recovery_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    recovery = snapshot.execution_recovery
    if recovery is None:
        return _sc_label(lang, "execution_recovery_none")
    lines = [
        f"- {_sc_label(lang, 'execution')}: `{recovery.state}`",
        f"- {_sc_label(lang, 'run')}: `{recovery.run_id or '(unknown)'}`",
        f"- {_sc_label(lang, 'target')}: `{recovery.target_workspace or '(not set)'}`",
        (
            f"- {_sc_label(lang, 'running_packages_at_exit')}: "
            f"`{', '.join(recovery.running_packages) or '(none)'}`"
        ),
        f"- {_sc_label(lang, 'retry_candidates')}: "
        f"`{', '.join(recovery.retry_candidates) or '(none)'}`",
        f"- {_sc_label(lang, 'done_packages')}: "
        f"`{', '.join(recovery.done_packages) or '(none)'}`",
        f"- {_sc_label(lang, 'last_event')}: `{recovery.last_event or '(none)'}`",
        "",
        _sc_label(lang, "reattach_note"),
    ]
    return "\n".join(lines)


def execution_recovery_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    recovery = snapshot.execution_recovery
    if recovery is None:
        return ((_sc_label(lang, "execution"), "none"),)
    return (
        (_sc_label(lang, "execution"), recovery.state),
        (_sc_label(lang, "run"), recovery.run_id or "(unknown)"),
        (_sc_label(lang, "target"), recovery.target_workspace or "(not set)"),
        (
            _sc_label(lang, "running_packages"),
            ", ".join(recovery.running_packages) or "(none)",
        ),
        (
            _sc_label(lang, "retry_candidates"),
            ", ".join(recovery.retry_candidates) or "(none)",
        ),
        (_sc_label(lang, "done_packages"), ", ".join(recovery.done_packages) or "(none)"),
        (_sc_label(lang, "last_event"), recovery.last_event or "(none)"),
        (_sc_label(lang, "next"), "/execute-retry | /execute mark-interrupted | /execute abort"),
    )


def snapshot_status_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    state = snapshot.state or "idle"
    goal = snapshot.goal or "(none)"
    lines = [
        f"- {_sc_label(lang, 'workflow')}: `{snapshot.session_id or '(new)'}`",
        f"- {_sc_label(lang, 'state')}: `{state}`",
        f"- {_sc_label(lang, 'round')}: `{snapshot.round_num}`",
        f"- {_sc_label(lang, 'goal')}: {goal}",
        "",
        (
            f"| {_sc_label(lang, 'provider')} | {_sc_label(lang, 'enabled')} "
            f"| {_sc_label(lang, 'status')} | {_sc_label(lang, 'readiness')} |"
        ),
        "| :--- | :--- | :--- | :--- |",
    ]
    if snapshot.providers:
        lines.extend(
            (
                f"| {provider.name} | {_yes_no(provider.enabled, lang=lang)} "
                f"| {provider.status} | {readiness_label(provider.readiness, lang=lang)} |"
            )
            for provider in snapshot.providers
        )
    else:
        lines.append("| - | - | - | - |")
    if snapshot.execution_recovery is not None:
        lines.extend(["", f"### {_sc_label(lang, 'execution_recovery')}"])
        lines.append(execution_recovery_markdown(snapshot, lang=lang))
    return "\n".join(lines)


def snapshot_status_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    rows = [
        (_sc_label(lang, "workflow"), snapshot.session_id or "(new)"),
        (_sc_label(lang, "state"), snapshot.state or "idle"),
        (_sc_label(lang, "round"), str(snapshot.round_num)),
        (_sc_label(lang, "goal"), snapshot.goal or "(none)"),
    ]
    for provider in snapshot.providers:
        rows.append(
            (
                f"{_sc_label(lang, 'provider')}: {provider.name}",
                (
                    f"{provider.status}; {_sc_label(lang, 'enabled').lower()}="
                    f"{_yes_no(provider.enabled, lang=lang)}; "
                    f"{_sc_label(lang, 'readiness').lower()}="
                    f"{readiness_label(provider.readiness, lang=lang)}"
                ),
            )
        )
    if snapshot.execution_recovery is not None:
        rows.extend(execution_recovery_rows(snapshot, lang=lang))
    return tuple(rows)


def readiness_label(readiness: str, *, lang: str = "en") -> str:
    if readiness == "unknown":
        return _sc_label(lang, "not_checked")
    return readiness


def _sc_label(lang: str, key: str) -> str:
    labels = STATUS_CONTEXT_LABELS.get(lang, STATUS_CONTEXT_LABELS["en"])
    return labels.get(key, STATUS_CONTEXT_LABELS["en"][key])


def _yes_no(value: bool, *, lang: str = "en") -> str:
    return _sc_label(lang, "yes" if value else "no")


def slash_command_suggestions(token: str) -> tuple[str, ...]:
    names = tuple(name for spec in COMMAND_SPECS for name in spec.names)
    return tuple(get_close_matches(token.lower(), names, n=3, cutoff=0.45))


def unknown_command_markdown(token: str, suggestions: tuple[str, ...]) -> str:
    lines = [f"`{token}` is not a Trinity slash command."]
    if suggestions:
        lines.extend(["", "Did you mean:"])
        lines.extend(f"- `{name}`" for name in suggestions)
    else:
        lines.extend(["", "Run `/help` to see Trinity-owned commands."])
    return "\n".join(lines)


def unknown_command_rows(suggestions: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    summary_by_name = {name: spec.summary for spec in COMMAND_SPECS for name in spec.names}
    return tuple((name, summary_by_name.get(name, "")) for name in suggestions)


def help_markdown() -> str:
    """Return registry-backed help text for Trinity-owned slash commands."""
    category_counts: dict[str, int] = {}
    for spec in COMMAND_SPECS:
        category = spec.category.value
        category_counts[category] = category_counts.get(category, 0) + 1
    lines = [
        "Trinity-owned slash commands are handled before provider prompts.",
        "Local UI, settings, and file commands do not call agents.",
        "",
        "### Categories",
    ]
    lines.extend(f"- `{category}`: {count}" for category, count in sorted(category_counts.items()))
    lines.extend(
        [
            "",
            "Use Tab to complete a command without running it. "
            "Use Enter to run an exact command.",
        ]
    )
    return "\n".join(lines)


def help_rows(*, use_korean: bool = False) -> tuple[tuple[str, str, str, str], ...]:
    """Return slash command registry rows for read-only help tables."""
    rows: list[tuple[str, str, str, str]] = []
    for spec in COMMAND_SPECS:
        command = spec.name
        if spec.aliases:
            command = f"{command} ({', '.join(spec.aliases)})"
        rows.append(
            (
                command,
                spec.category.value,
                spec.agent_call.value,
                spec.summary_ko if use_korean else spec.summary,
            )
        )
    return tuple(rows)


def snapshot_workflow_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    state = snapshot.state or "idle"
    goal = snapshot.goal or "(none)"
    lines = [
        f"- {_sc_label(lang, 'id')}: `{snapshot.session_id or '(new)'}`",
        f"- {_sc_label(lang, 'state')}: `{state}`",
        f"- {_sc_label(lang, 'goal')}: {goal}",
        f"- {_sc_label(lang, 'round')}: `{snapshot.round_num}`",
        f"- {_sc_label(lang, 'pending_questions')}: `{len(snapshot.questions)}`",
        f"- {_sc_label(lang, 'decisions')}: `{len(snapshot.decisions)}`",
        f"- {_sc_label(lang, 'work_packages')}: `{len(snapshot.work_packages)}`",
        f"- {_sc_label(lang, 'subtasks')}: `{len(snapshot.subtasks)}`",
        f"- {_sc_label(lang, 'local_policy_repairs')}: `{len(snapshot.work_package_repairs)}`",
        f"- {_sc_label(lang, 'post_review_items')}: `{len(snapshot.post_review_items)}`",
        f"- {_sc_label(lang, 'supplemental_rounds')}: `{snapshot.supplemental_round}`",
        f"- {_sc_label(lang, 'execution_log_entries')}: `{len(snapshot.execution_log)}`",
    ]
    if snapshot.execution_recovery is not None:
        lines.extend(["", f"### {_sc_label(lang, 'execution_recovery')}"])
        lines.append(execution_recovery_markdown(snapshot, lang=lang))
    return "\n".join(lines)


def snapshot_workflow_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    rows = [
        (_sc_label(lang, "id"), snapshot.session_id or "(new)"),
        (_sc_label(lang, "state"), snapshot.state or "idle"),
        (_sc_label(lang, "goal"), snapshot.goal or "(none)"),
        (_sc_label(lang, "round"), str(snapshot.round_num)),
        (_sc_label(lang, "pending_questions"), str(len(snapshot.questions))),
        (_sc_label(lang, "decisions"), str(len(snapshot.decisions))),
        (_sc_label(lang, "work_packages"), str(len(snapshot.work_packages))),
        (_sc_label(lang, "subtasks"), str(len(snapshot.subtasks))),
        (_sc_label(lang, "local_policy_repairs"), str(len(snapshot.work_package_repairs))),
        (_sc_label(lang, "post_review_items"), str(len(snapshot.post_review_items))),
        (_sc_label(lang, "supplemental_rounds"), str(snapshot.supplemental_round)),
        (_sc_label(lang, "execution_log_entries"), str(len(snapshot.execution_log))),
    ]
    if snapshot.execution_recovery is not None:
        rows.extend(execution_recovery_rows(snapshot, lang=lang))
    return tuple(rows)


def snapshot_has_current_context(snapshot: WorkflowNexusSnapshot) -> bool:
    return bool(
        snapshot.session_id
        or snapshot.goal
        or snapshot.round_num
        or snapshot.synthesis.summary
        or snapshot.synthesis.consensus_progress
        or snapshot.questions
        or snapshot.decisions
        or snapshot.central_work_packages
        or snapshot.work_packages
        or snapshot.subtasks
        or snapshot.work_package_repairs
        or snapshot.post_review_items
        or snapshot.follow_up_requests
        or snapshot.workflow_events
        or snapshot.execution_log
    )


def snapshot_context_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    if not snapshot_has_current_context(snapshot):
        return NO_CURRENT_CONTEXT_MESSAGE

    lines = [
        f"- {_sc_label(lang, 'workflow')}: `{snapshot.session_id or '(new)'}`",
        f"- {_sc_label(lang, 'state')}: `{snapshot.state or 'idle'}`",
        f"- {_sc_label(lang, 'goal')}: {snapshot.goal or '(none)'}",
        f"- {_sc_label(lang, 'round')}: `{snapshot.round_num}`",
    ]
    if snapshot.synthesis.consensus_progress:
        lines.append(
            f"- {_sc_label(lang, 'synthesis')}: "
            f"`{snapshot.synthesis.consensus_progress}`"
        )
    if snapshot.synthesis.summary:
        lines.extend(["", f"### {_sc_label(lang, 'synthesis')}", snapshot.synthesis.summary])
    if snapshot.questions:
        lines.extend(["", f"### {_sc_label(lang, 'questions')}"])
        for question in snapshot.questions:
            status = question.status or "open"
            lines.append(f"- **{question.id}** [{status}] {question.question}")
            if question.answer:
                lines.append(f"  - {_sc_label(lang, 'answer')}: {question.answer}")
    if snapshot.decisions:
        lines.extend(["", f"### {_sc_label(lang, 'decisions')}"])
        lines.extend(f"- {item}" for item in snapshot.decisions)
    packages = snapshot.work_packages or snapshot.central_work_packages
    if packages:
        lines.extend(["", f"### {_sc_label(lang, 'work_packages')}"])
        lines.extend(f"- {item}" for item in packages)
    if snapshot.subtasks:
        lines.extend(["", f"### {_sc_label(lang, 'subtasks')}"])
        for subtask in snapshot.subtasks:
            summary = subtask.result_summary or subtask.objective
            lines.append(
                f"- **{subtask.id or '(unnamed)'}** "
                f"[{subtask.status}] "
                f"{subtask.parent_package_id or '(no package)'} -> "
                f"{subtask.delegated_to or '(unknown)'}: {summary}"
            )
    if snapshot.work_package_repairs:
        lines.extend(["", f"### {_sc_label(lang, 'local_policy_repairs')}"])
        lines.extend(f"- {item}" for item in snapshot.work_package_repairs)
    if snapshot.final_review is not None:
        lines.extend(["", f"### {_sc_label(lang, 'final_review')}"])
        if lang == "ko":
            lines.append(
                f"- `{snapshot.final_review.status}` / "
                f"{_sc_label(lang, 'reviewer')} `{snapshot.final_review.reviewer_agent}`"
            )
        else:
            lines.append(
                f"- `{snapshot.final_review.status}` by "
                f"`{snapshot.final_review.reviewer_agent}`"
            )
        if snapshot.final_review.summary:
            lines.append(f"- {snapshot.final_review.summary}")
    if snapshot.post_review_items:
        lines.extend(["", f"### {_sc_label(lang, 'post_review_action_items')}"])
        for item in snapshot.post_review_items:
            lines.append(
                f"- **{item.id}** [{item.severity}][{item.status}] "
                f"{item.title or item.summary}"
            )
    if snapshot.follow_up_requests:
        lines.extend(["", f"### {_sc_label(lang, 'follow_up_requests')}"])
        lines.extend(f"- {item}" for item in snapshot.follow_up_requests)
    if snapshot.workflow_events:
        lines.extend(["", f"### {_sc_label(lang, 'workflow_history')}"])
        lines.extend(f"- {item}" for item in snapshot.workflow_events)
    extra_execution_log = [
        item for item in snapshot.execution_log if item not in snapshot.workflow_events
    ]
    if extra_execution_log:
        lines.extend(["", f"### {_sc_label(lang, 'execution_results')}"])
        lines.extend(f"- {item}" for item in extra_execution_log)
    return "\n".join(lines)


def questions_markdown(snapshot: WorkflowNexusSnapshot) -> str:
    if not snapshot.questions:
        return "No pending workflow questions."
    lines: list[str] = []
    for index, question in enumerate(snapshot.questions, start=1):
        lines.append(f"{index}. **{question.id}** [{question.status}] {question.question}")
        if question.answer:
            lines.append(f"   - Answer: {question.answer}")
        if question.recommended_option:
            lines.append(f"   - Recommended: {question.recommended_option}")
        for option_index, option in enumerate(question.options, start=1):
            lines.append(f"   - {option_index}. {option}")
    lines.append("")
    lines.append("Use question panel buttons or `/answer <id|index|next> <answer>`.")
    return "\n".join(lines)


def questions_select_markdown(snapshot: WorkflowNexusSnapshot) -> str:
    if not snapshot.questions:
        return "No pending workflow questions to select."
    question = snapshot.questions[0]
    lines = [
        f"Selected question: **{question.id}**",
        question.question,
    ]
    if question.options:
        lines.append("")
        lines.append(
            "Use the option buttons in the question panel, "
            "or run `/answer <option-number>`."
        )
        for index, option in enumerate(question.options, start=1):
            lines.append(f"- {index}. {option}")
    else:
        lines.append("")
        lines.append("This question has no predefined options.")
        lines.append("Use `/answer <id|index|next> <answer>`.")
    return "\n".join(lines)


def questions_rows(snapshot: WorkflowNexusSnapshot) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (
            question.id,
            question.status or "open",
            question.question,
            ", ".join(question.options) if question.options else "(free text)",
        )
        for question in snapshot.questions
    )


def decisions_markdown(snapshot: WorkflowNexusSnapshot) -> str:
    if not snapshot.decisions:
        return "No workflow decisions recorded in the current session."
    return "\n".join(
        f"{index}. {decision}" for index, decision in enumerate(snapshot.decisions, start=1)
    )


def decisions_rows(snapshot: WorkflowNexusSnapshot) -> tuple[tuple[str, str], ...]:
    return tuple(
        (str(index), decision) for index, decision in enumerate(snapshot.decisions, start=1)
    )


def packages_markdown(snapshot: WorkflowNexusSnapshot) -> str:
    rows = packages_rows(snapshot)
    if not rows:
        return "No workflow work packages generated in the current session."
    lines = []
    for index, source, package in rows:
        lines.append(f"{index}. **{source}** {package}")
    return "\n".join(lines)


def packages_rows(snapshot: WorkflowNexusSnapshot) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    for package in snapshot.central_work_packages:
        rows.append((str(len(rows) + 1), "central", package))
    for package in snapshot.work_packages:
        rows.append((str(len(rows) + 1), "local", package))
    return tuple(rows)


def review_rows(snapshot: WorkflowNexusSnapshot) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = [
        ("Workflow", snapshot.session_id or "(new)"),
        ("State", snapshot.state or "idle"),
        ("Work packages", str(len(snapshot.work_package_details))),
    ]
    pending = [
        package.id for package in snapshot.work_package_details if not package.review_status
    ]
    reviewed = [
        f"{package.id}:{package.review_status}"
        for package in snapshot.work_package_details
        if package.review_status
    ]
    rows.append(("Pending WP review", ", ".join(pending) or "(none)"))
    rows.append(("Reviewed WP", ", ".join(reviewed) or "(none)"))
    if snapshot.final_review is not None:
        rows.append(
            (
                "Final review",
                (
                    f"{snapshot.final_review.status} by "
                    f"{snapshot.final_review.reviewer_agent or '(unknown)'}"
                ),
            )
        )
    else:
        rows.append(("Final review", "(none)"))
    return tuple(rows)


def improve_rows(snapshot: WorkflowNexusSnapshot) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = [
        ("Workflow", snapshot.session_id or "(new)"),
        ("State", snapshot.state or "idle"),
        ("Supplemental rounds", str(snapshot.supplemental_round)),
    ]
    if not snapshot.post_review_items:
        rows.append(("Action items", "(none)"))
        return tuple(rows)
    for item in snapshot.post_review_items:
        rows.append(
            (
                item.id,
                (
                    f"{item.status}; severity={item.severity}; "
                    f"kind={item.kind}; title={item.title or item.summary}"
                ),
            )
        )
    return tuple(rows)


def subtasks_markdown(snapshot: WorkflowNexusSnapshot) -> str:
    if not snapshot.subtasks:
        return "No provider delegation subtasks recorded in the current session."
    lines = []
    for index, subtask in enumerate(snapshot.subtasks, start=1):
        summary = subtask.result_summary or subtask.objective
        lines.append(
            f"{index}. **{subtask.id or '(unnamed)'}** "
            f"[{subtask.status}] "
            f"{subtask.parent_package_id or '(no package)'} -> "
            f"{subtask.delegated_to or '(unknown)'}: {summary}"
        )
    return "\n".join(lines)


def subtasks_rows(
    snapshot: WorkflowNexusSnapshot,
) -> tuple[tuple[str, str, str, str, str], ...]:
    return tuple(
        (
            subtask.id or "(unnamed)",
            subtask.parent_package_id or "(none)",
            subtask.delegated_to or "(unknown)",
            subtask.status,
            subtask.result_summary or subtask.objective or "(none)",
        )
        for subtask in snapshot.subtasks
    )


def history_rows(
    snapshot: WorkflowNexusSnapshot,
    local_command_results: Sequence[object] = (),
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    if snapshot.session_id or snapshot.goal:
        rows.append(("Workflow", snapshot.session_id or "(new)"))
        rows.append(("State", snapshot.state or "idle"))
        rows.append(("Round", str(snapshot.round_num)))
        if snapshot.goal:
            rows.append(("Goal", snapshot.goal))
    for command in local_command_results[-10:]:
        rows.append(
            (
                "Local command",
                f"{getattr(command, 'command', '')} - {getattr(command, 'title', '')}",
            )
        )
    for entry in snapshot.execution_log[-10:]:
        rows.append(("Execution", entry))
    return tuple(rows)


def history_markdown(
    snapshot: WorkflowNexusSnapshot,
    rows: tuple[tuple[str, str], ...],
) -> str:
    if not rows:
        return "No local history recorded in this Textual session."
    lines = [
        f"- Workflow: `{snapshot.session_id or '(new)'}`",
        f"- State: `{snapshot.state or 'idle'}`",
        f"- Round: `{snapshot.round_num}`",
    ]
    if snapshot.goal:
        lines.append(f"- Goal: {snapshot.goal}")
    if snapshot.execution_log:
        lines.extend(["", "### Recent Execution Log"])
        lines.extend(f"- {entry}" for entry in snapshot.execution_log[-10:])
    if rows:
        lines.extend(["", "### Recent Local Items"])
        lines.extend(f"- **{kind}**: {item}" for kind, item in rows[-12:])
    return "\n".join(lines)


def resume_archives_markdown(archives: list[object]) -> str:
    lines = ["Saved workflow sessions available to resume."]
    for archive in archives:
        selector = str(getattr(archive, "selector", ""))
        session_id = str(getattr(archive, "session_id", ""))
        state = str(getattr(archive, "state", ""))
        goal = str(getattr(archive, "goal", "")).strip() or "(no goal)"
        lines.append(f"- `{selector}` {session_id} [{state}] {goal}")
    return "\n".join(lines)


def resume_archive_rows(archives: list[object]) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (
            str(getattr(archive, "selector", "")),
            str(getattr(archive, "session_id", "")),
            str(getattr(archive, "state", "")),
            str(getattr(archive, "goal", "")).strip() or "(no goal)",
        )
        for archive in archives
    )


def resume_result_rows(snapshot: WorkflowNexusSnapshot) -> tuple[tuple[str, str], ...]:
    return (
        ("Workflow", snapshot.session_id or "(new)"),
        ("State", snapshot.state or "idle"),
        ("Goal", snapshot.goal or "(none)"),
        ("Round", str(snapshot.round_num)),
    )
