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
        "answer_inspect_questions_hint": "Run `/questions` to inspect pending questions first.",
        "answer_usage": "Usage: /answer <question-id|index|next> <answer>",
        "central": "central",
        "continue_until_question": "Continue planning until the central agent raises a question.",
        "decision": "Decision",
        "decision_hint": "Answer pending questions with `/answer` to add decisions.",
        "decisions": "Decisions",
        "done_packages": "Done packages",
        "delegated_to": "Delegated To",
        "enabled": "Enabled",
        "execution": "Execution",
        "execution_log_entries": "Execution log entries",
        "execution_recovery": "Execution Recovery",
        "execution_recovery_none": "No interrupted execution is recorded for this workflow.",
        "execution_results": "Execution Results",
        "final_review": "Final Review",
        "follow_up_requests": "Follow-up Requests",
        "goal": "Goal",
        "history_hint": "Run a prompt, execute a workflow, or use local slash commands first.",
        "id": "ID",
        "improve_hint": (
            "Use `/improve high`, `/improve all`, `/improve AI-001`, "
            "or `/improve done`."
        ),
        "item": "Item",
        "kind": "Kind",
        "last_event": "Last event",
        "local_command": "Local command",
        "local_policy_repairs": "Local Policy Repairs",
        "next": "Next",
        "no": "no",
        "no_decisions": "No workflow decisions recorded in the current session.",
        "no_history": "No local history recorded in this Textual session.",
        "no_packages": "No workflow work packages generated in the current session.",
        "no_pending_questions": "No pending workflow questions.",
        "no_pending_questions_select": "No pending workflow questions to select.",
        "no_predefined_options": "This question has no predefined options.",
        "no_subtasks": "No provider delegation subtasks recorded in the current session.",
        "not_checked": "not checked",
        "options": "Options",
        "package": "Package",
        "packages_hint": "Finish planning until a blueprint or local WP graph is generated.",
        "pending_questions": "Pending questions",
        "pending_wp_review": "Pending WP review",
        "post_review_action_items": "Post Review Action Items",
        "post_review_items": "Post-review items",
        "action_items": "Action items",
        "provider": "Provider",
        "questions": "Questions",
        "question": "Question",
        "question_hint": "Use question panel buttons or `/answer <id|index|next> <answer>`.",
        "question_answer_usage": "Use `/answer <id|index|next> <answer>`.",
        "question_select_hint": (
            "Use the option buttons in the question panel, "
            "or run `/answer <option-number>`."
        ),
        "readiness": "Readiness",
        "recent_execution_log": "Recent Execution Log",
        "recent_local_items": "Recent Local Items",
        "recommended": "Recommended",
        "reattach_note": (
            "Provider process reattach is not supported. Retry starts a new "
            "one-shot execution only for interrupted, failed, or blocked packages."
        ),
        "retry_candidates": "Retry candidates",
        "review_hint": "Run `/review wp`, `/review final`, or `/review all`.",
        "reviewed_wp": "Reviewed WP",
        "reviewer": "reviewer",
        "round": "Round",
        "run": "Run",
        "source": "Source",
        "running_packages": "Running packages",
        "running_packages_at_exit": "Running packages at exit",
        "state": "State",
        "status": "Status",
        "summary": "Summary",
        "subtasks": "Subtasks",
        "subtasks_hint": "Subtasks appear after an executing provider reports delegated work.",
        "supplemental_rounds": "Supplemental rounds",
        "synthesis": "Synthesis",
        "target": "Target",
        "value": "Value",
        "workflow": "Workflow",
        "workflow_history": "Workflow History",
        "work_packages": "Work Packages",
        "local": "local",
        "yes": "yes",
        "selected_question": "Selected question",
        "free_text": "(free text)",
    },
    "ko": {
        "answer": "답변",
        "answer_inspect_questions_hint": (
            "먼저 `/questions`를 실행해 대기 중인 질문을 확인하세요."
        ),
        "answer_usage": "사용법: /answer <question-id|index|next> <answer>",
        "central": "중앙",
        "continue_until_question": "중앙 에이전트가 질문을 만들 때까지 계획을 계속 진행하세요.",
        "decision": "결정",
        "decision_hint": "대기 중인 질문에 `/answer`로 답하면 결정이 추가됩니다.",
        "decisions": "결정",
        "done_packages": "완료 WP",
        "delegated_to": "위임 대상",
        "enabled": "활성화",
        "execution": "실행",
        "execution_log_entries": "실행 로그 항목",
        "execution_recovery": "실행 복구",
        "execution_recovery_none": "이 워크플로우에 기록된 중단 실행이 없습니다.",
        "execution_results": "실행 결과",
        "final_review": "최종 리뷰",
        "follow_up_requests": "후속 요청",
        "goal": "목표",
        "history_hint": "프롬프트 실행, 워크플로우 실행, 로컬 slash 명령 사용 후 이력이 표시됩니다.",
        "id": "ID",
        "improve_hint": (
            "`/improve high`, `/improve all`, `/improve AI-001`, "
            "`/improve done` 중 하나를 실행하세요."
        ),
        "item": "항목",
        "kind": "종류",
        "last_event": "최근 이벤트",
        "local_command": "로컬 명령",
        "local_policy_repairs": "로컬 정책 복구",
        "next": "다음",
        "no": "아니오",
        "no_decisions": "현재 세션에 기록된 워크플로우 결정이 없습니다.",
        "no_history": "현재 Textual 세션에 기록된 로컬 이력이 없습니다.",
        "no_packages": "현재 세션에 생성된 워크플로우 작업 패키지가 없습니다.",
        "no_pending_questions": "대기 중인 워크플로우 질문이 없습니다.",
        "no_pending_questions_select": "선택할 대기 질문이 없습니다.",
        "no_predefined_options": "이 질문에는 미리 정의된 선택지가 없습니다.",
        "no_subtasks": "현재 세션에 기록된 프로바이더 위임 하위 작업이 없습니다.",
        "not_checked": "미확인",
        "options": "선택지",
        "package": "작업 패키지",
        "packages_hint": "blueprint 또는 로컬 WP 그래프가 생성될 때까지 계획을 진행하세요.",
        "pending_questions": "대기 중 질문",
        "pending_wp_review": "대기 중 WP 리뷰",
        "post_review_action_items": "리뷰 후 조치",
        "post_review_items": "리뷰 후 조치",
        "action_items": "조치 항목",
        "provider": "프로바이더",
        "questions": "질문",
        "question": "질문",
        "question_hint": "질문 패널 버튼을 사용하거나 `/answer <id|index|next> <answer>`를 실행하세요.",
        "question_answer_usage": "`/answer <id|index|next> <answer>`를 실행하세요.",
        "question_select_hint": (
            "질문 패널의 선택지 버튼을 사용하거나 `/answer <option-number>`를 실행하세요."
        ),
        "readiness": "준비 상태",
        "recent_execution_log": "최근 실행 로그",
        "recent_local_items": "최근 로컬 항목",
        "recommended": "추천",
        "reattach_note": (
            "프로바이더 프로세스 재연결은 지원하지 않습니다. 재시도는 중단, 실패, "
            "차단된 작업에 대해 새 단발 실행을 시작합니다."
        ),
        "retry_candidates": "재시도 후보",
        "review_hint": "`/review wp`, `/review final`, `/review all` 중 하나를 실행하세요.",
        "reviewed_wp": "리뷰된 WP",
        "reviewer": "리뷰어",
        "round": "라운드",
        "run": "실행 ID",
        "source": "출처",
        "running_packages": "실행 중 WP",
        "running_packages_at_exit": "종료 시 실행 중 WP",
        "state": "상태",
        "status": "상태",
        "summary": "요약",
        "subtasks": "하위 작업",
        "subtasks_hint": "실행 중인 프로바이더가 위임 작업을 보고하면 하위 작업이 표시됩니다.",
        "supplemental_rounds": "보충 라운드",
        "synthesis": "종합",
        "target": "대상",
        "value": "값",
        "workflow": "워크플로우",
        "workflow_history": "워크플로우 이력",
        "work_packages": "작업 패키지",
        "local": "로컬",
        "yes": "예",
        "selected_question": "선택된 질문",
        "free_text": "(자유 입력)",
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


def answer_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "answer")


def answer_usage_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "answer_usage")


def answer_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "answer_inspect_questions_hint")


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


def questions_action_hint(*, has_questions: bool, lang: str = "en") -> str:
    key = "question_hint" if has_questions else "continue_until_question"
    return _sc_label(lang, key)


def questions_table_columns(*, lang: str = "en") -> tuple[str, str, str, str]:
    return (
        _sc_label(lang, "id"),
        _sc_label(lang, "status"),
        _sc_label(lang, "question"),
        _sc_label(lang, "options"),
    )


def questions_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    if not snapshot.questions:
        return _sc_label(lang, "no_pending_questions")
    lines: list[str] = []
    for index, question in enumerate(snapshot.questions, start=1):
        lines.append(f"{index}. **{question.id}** [{question.status}] {question.question}")
        if question.answer:
            lines.append(f"   - {_sc_label(lang, 'answer')}: {question.answer}")
        if question.recommended_option:
            lines.append(
                f"   - {_sc_label(lang, 'recommended')}: {question.recommended_option}"
            )
        for option_index, option in enumerate(question.options, start=1):
            lines.append(f"   - {option_index}. {option}")
    lines.append("")
    lines.append(_sc_label(lang, "question_hint"))
    return "\n".join(lines)


def questions_select_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    if not snapshot.questions:
        return _sc_label(lang, "no_pending_questions_select")
    question = snapshot.questions[0]
    lines = [
        f"{_sc_label(lang, 'selected_question')}: **{question.id}**",
        question.question,
    ]
    if question.options:
        lines.append("")
        lines.append(_sc_label(lang, "question_select_hint"))
        for index, option in enumerate(question.options, start=1):
            lines.append(f"- {index}. {option}")
    else:
        lines.append("")
        lines.append(_sc_label(lang, "no_predefined_options"))
        lines.append(_sc_label(lang, "question_answer_usage"))
    return "\n".join(lines)


def questions_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (
            question.id,
            question.status or "open",
            question.question,
            ", ".join(question.options) if question.options else _sc_label(lang, "free_text"),
        )
        for question in snapshot.questions
    )


def decisions_action_hint(*, has_decisions: bool, lang: str = "en") -> str:
    return "" if has_decisions else _sc_label(lang, "decision_hint")


def decisions_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return ("#", _sc_label(lang, "decision"))


def decisions_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    if not snapshot.decisions:
        return _sc_label(lang, "no_decisions")
    return "\n".join(
        f"{index}. {decision}" for index, decision in enumerate(snapshot.decisions, start=1)
    )


def decisions_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (str(index), decision) for index, decision in enumerate(snapshot.decisions, start=1)
    )


def packages_action_hint(*, has_packages: bool, lang: str = "en") -> str:
    return "" if has_packages else _sc_label(lang, "packages_hint")


def packages_table_columns(*, lang: str = "en") -> tuple[str, str, str]:
    return ("#", _sc_label(lang, "source"), _sc_label(lang, "package"))


def packages_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    rows = packages_rows(snapshot, lang=lang)
    if not rows:
        return _sc_label(lang, "no_packages")
    lines = []
    for index, source, package in rows:
        lines.append(f"{index}. **{source}** {package}")
    return "\n".join(lines)


def packages_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    for package in snapshot.central_work_packages:
        rows.append((str(len(rows) + 1), _sc_label(lang, "central"), package))
    for package in snapshot.work_packages:
        rows.append((str(len(rows) + 1), _sc_label(lang, "local"), package))
    return tuple(rows)


def review_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "review_hint")


def review_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return status_table_columns(lang=lang)


def review_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = [
        (_sc_label(lang, "workflow"), snapshot.session_id or "(new)"),
        (_sc_label(lang, "state"), snapshot.state or "idle"),
        (_sc_label(lang, "work_packages"), str(len(snapshot.work_package_details))),
    ]
    pending = [
        package.id for package in snapshot.work_package_details if not package.review_status
    ]
    reviewed = [
        f"{package.id}:{package.review_status}"
        for package in snapshot.work_package_details
        if package.review_status
    ]
    rows.append((_sc_label(lang, "pending_wp_review"), ", ".join(pending) or "(none)"))
    rows.append((_sc_label(lang, "reviewed_wp"), ", ".join(reviewed) or "(none)"))
    if snapshot.final_review is not None:
        reviewer = snapshot.final_review.reviewer_agent or "(unknown)"
        final_review_value = (
            f"{snapshot.final_review.status} / {_sc_label(lang, 'reviewer')} {reviewer}"
            if lang == "ko"
            else f"{snapshot.final_review.status} by {reviewer}"
        )
        rows.append(
            (
                _sc_label(lang, "final_review"),
                final_review_value,
            )
        )
    else:
        rows.append((_sc_label(lang, "final_review"), "(none)"))
    return tuple(rows)


def improve_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "improve_hint")


def improve_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return status_table_columns(lang=lang)


def improve_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = [
        (_sc_label(lang, "workflow"), snapshot.session_id or "(new)"),
        (_sc_label(lang, "state"), snapshot.state or "idle"),
        (_sc_label(lang, "supplemental_rounds"), str(snapshot.supplemental_round)),
    ]
    if not snapshot.post_review_items:
        rows.append((_sc_label(lang, "action_items"), "(none)"))
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


def subtasks_action_hint(*, has_subtasks: bool, lang: str = "en") -> str:
    return "" if has_subtasks else _sc_label(lang, "subtasks_hint")


def subtasks_table_columns(*, lang: str = "en") -> tuple[str, str, str, str, str]:
    return (
        _sc_label(lang, "id"),
        _sc_label(lang, "package"),
        _sc_label(lang, "delegated_to"),
        _sc_label(lang, "status"),
        _sc_label(lang, "summary"),
    )


def subtasks_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    if not snapshot.subtasks:
        return _sc_label(lang, "no_subtasks")
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
    *,
    lang: str = "en",
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


def history_action_hint(*, has_history: bool, lang: str = "en") -> str:
    return "" if has_history else _sc_label(lang, "history_hint")


def history_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return (_sc_label(lang, "kind"), _sc_label(lang, "item"))


def history_rows(
    snapshot: WorkflowNexusSnapshot,
    local_command_results: Sequence[object] = (),
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    if snapshot.session_id or snapshot.goal:
        rows.append((_sc_label(lang, "workflow"), snapshot.session_id or "(new)"))
        rows.append((_sc_label(lang, "state"), snapshot.state or "idle"))
        rows.append((_sc_label(lang, "round"), str(snapshot.round_num)))
        if snapshot.goal:
            rows.append((_sc_label(lang, "goal"), snapshot.goal))
    for command in local_command_results[-10:]:
        rows.append(
            (
                _sc_label(lang, "local_command"),
                f"{getattr(command, 'command', '')} - {getattr(command, 'title', '')}",
            )
        )
    for entry in snapshot.execution_log[-10:]:
        rows.append((_sc_label(lang, "execution"), entry))
    return tuple(rows)


def history_markdown(
    snapshot: WorkflowNexusSnapshot,
    rows: tuple[tuple[str, str], ...],
    *,
    lang: str = "en",
) -> str:
    if not rows:
        return _sc_label(lang, "no_history")
    lines = [
        f"- {_sc_label(lang, 'workflow')}: `{snapshot.session_id or '(new)'}`",
        f"- {_sc_label(lang, 'state')}: `{snapshot.state or 'idle'}`",
        f"- {_sc_label(lang, 'round')}: `{snapshot.round_num}`",
    ]
    if snapshot.goal:
        lines.append(f"- {_sc_label(lang, 'goal')}: {snapshot.goal}")
    if snapshot.execution_log:
        lines.extend(["", f"### {_sc_label(lang, 'recent_execution_log')}"])
        lines.extend(f"- {entry}" for entry in snapshot.execution_log[-10:])
    if rows:
        lines.extend(["", f"### {_sc_label(lang, 'recent_local_items')}"])
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
