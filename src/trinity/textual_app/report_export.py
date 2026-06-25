"""Markdown export helpers for the Textual report screen."""

from __future__ import annotations

import time
from pathlib import Path

from trinity.textual_app.snapshot import (
    AgentQualitySnapshot,
    ProviderSnapshot,
    WorkflowNexusSnapshot,
    WorkPackageSnapshot,
)
from trinity.display_labels import (
    display_kind_value,
    display_profile_value,
    display_source_value,
)
from trinity.textual_app.widgets.status_label import (
    display_consensus_progress,
    display_review_skip_reason,
    display_review_status_value,
    display_status_value,
)

_MD_SPECIAL_CHARS = "\\`*_{}[]<>()#+-.!|"

REPORT_MARKDOWN_LABELS = {
    "en": {
        "agent_quality": "Advisory Agent Quality",
        "blockers": "blockers",
        "central_wp_graph": "Central WP Graph",
        "consensus": "Consensus",
        "context": "context",
        "decisions": "Decisions",
        "done_packages": "Done packages",
        "execution": "Execution",
        "execution_log": "Execution Log",
        "execution_recovery": "Execution Recovery",
        "executor": "executor",
        "default": "default",
        "goal": "Goal",
        "last_event": "Last event",
        "kind": "kind",
        "lane": "lane",
        "local_policy_repairs": "Local Policy Repairs",
        "local_wp_graph": "Local WP Graph",
        "mission": "mission",
        "modes": "modes",
        "open_questions": "Open Questions",
        "output": "output",
        "owner": "owner",
        "progress": "Progress",
        "profile": "profile",
        "provider_session": "session",
        "providers": "Providers",
        "no_package": "(no package)",
        "none": "(none)",
        "not_set": "(not set)",
        "reason": "Reason",
        "required_changes": "required changes",
        "retry_candidates": "Retry candidates",
        "review": "Review",
        "review_reason": "reason",
        "reviewer": "reviewer",
        "routing": "Routing",
        "round": "Round",
        "run": "Run",
        "running_packages": "Running packages",
        "score": "score",
        "session": "Session",
        "source": "Source",
        "state": "State",
        "status": "Status",
        "strengths": "strengths",
        "subtasks": "Subtasks",
        "success": "success",
        "target": "Target",
        "title": "Deliberation Report",
        "unnamed": "(unnamed)",
        "unknown": "(unknown)",
        "untitled": "(untitled)",
        "work_package_routing": "Work Package Routing",
        "work_packages": "Work Packages",
    },
    "ko": {
        "agent_quality": "자문 에이전트 품질",
        "blockers": "차단",
        "central_wp_graph": "중앙 작업 패키지 그래프",
        "consensus": "합의",
        "context": "컨텍스트",
        "decisions": "결정",
        "done_packages": "완료 작업 패키지",
        "execution": "실행",
        "execution_log": "실행 로그",
        "execution_recovery": "실행 복구",
        "executor": "실행자",
        "default": "기본값",
        "goal": "목표",
        "last_event": "최근 이벤트",
        "kind": "종류",
        "lane": "그룹",
        "local_policy_repairs": "로컬 정책 복구",
        "local_wp_graph": "로컬 작업 패키지 그래프",
        "mission": "미션",
        "modes": "모드",
        "open_questions": "미해결 질문",
        "output": "출력",
        "owner": "소유자",
        "progress": "진행",
        "profile": "프로필",
        "provider_session": "세션",
        "providers": "프로바이더",
        "no_package": "(패키지 없음)",
        "none": "(없음)",
        "not_set": "(미설정)",
        "reason": "이유",
        "required_changes": "변경 요청",
        "retry_candidates": "재시도 후보",
        "review": "리뷰",
        "review_reason": "이유",
        "reviewer": "리뷰어",
        "routing": "라우팅",
        "round": "라운드",
        "run": "실행 ID",
        "running_packages": "실행 중 작업 패키지",
        "score": "점수",
        "session": "세션",
        "source": "출처",
        "state": "상태",
        "status": "상태",
        "strengths": "강점",
        "subtasks": "하위 작업",
        "success": "성공",
        "target": "대상",
        "title": "워크플로우 리포트",
        "unnamed": "(이름 없음)",
        "unknown": "(알 수 없음)",
        "untitled": "(제목 없음)",
        "work_package_routing": "작업 패키지 라우팅",
        "work_packages": "작업 패키지",
    },
}


def snapshot_has_report_data(snapshot: WorkflowNexusSnapshot) -> bool:
    """Return whether a snapshot has enough user-visible data to export."""
    return any(
        (
            snapshot.session_id,
            snapshot.goal,
            snapshot.agent_quality,
            snapshot.synthesis.summary,
            snapshot.decisions,
            snapshot.central_work_packages,
            snapshot.work_packages,
            snapshot.work_package_details,
            snapshot.subtasks,
            snapshot.work_package_repairs,
            snapshot.execution_log,
            snapshot.execution_recovery,
            snapshot.questions,
        )
    )


def snapshot_report_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    """Build a minimal Markdown report from an in-memory UI snapshot."""
    lines = [
        f"# {_label(lang, 'title')}",
        "",
        f"**{_label(lang, 'session')}**: {_md_inline(snapshot.session_id or _none(lang))}  ",
        f"**{_label(lang, 'goal')}**: {_md_inline(snapshot.goal or _none(lang))}  ",
        f"**{_label(lang, 'state')}**: {_md_inline(_status_value(snapshot.state, lang=lang))}  ",
        f"**{_label(lang, 'round')}**: {snapshot.round_num}  ",
        f"**{_label(lang, 'providers')}**: {len(snapshot.providers)}",
    ]

    provider_lines = _provider_lines(snapshot, lang=lang)
    if provider_lines:
        lines.extend(["", f"## {_label(lang, 'providers')}", ""])
        lines.extend(provider_lines)
    quality_lines = _agent_quality_lines(snapshot, lang=lang)
    if quality_lines:
        lines.extend(["", f"## {_label(lang, 'agent_quality')}", ""])
        lines.extend(quality_lines)
    if snapshot.synthesis.summary:
        progress = display_consensus_progress(
            snapshot.synthesis.consensus_progress,
            lang=lang,
            empty=_none(lang),
        )
        lines.extend(
            [
                "",
                f"## {_label(lang, 'consensus')}",
                "",
                f"**{_label(lang, 'progress')}**: {_md_inline(progress)}  ",
                f"**{_label(lang, 'source')}**: {_md_inline(snapshot.synthesis.source)}",
                "",
                _md_block(snapshot.synthesis.summary),
            ]
        )
    if snapshot.decisions:
        lines.extend(["", f"## {_label(lang, 'decisions')}", ""])
        lines.extend(f"- {_md_inline(decision)}" for decision in snapshot.decisions)
    if snapshot.central_work_packages:
        lines.extend(["", f"## {_label(lang, 'central_wp_graph')}", ""])
        lines.extend(f"- {_md_inline(package)}" for package in snapshot.central_work_packages)
    if snapshot.work_packages:
        heading = (
            f"## {_label(lang, 'local_wp_graph')}"
            if snapshot.central_work_packages
            else f"## {_label(lang, 'work_packages')}"
        )
        lines.extend(["", heading, ""])
        lines.extend(f"- {_md_inline(package)}" for package in snapshot.work_packages)
    package_detail_lines = _work_package_detail_lines(snapshot, lang=lang)
    if package_detail_lines:
        lines.extend(["", f"## {_label(lang, 'work_package_routing')}", ""])
        lines.extend(package_detail_lines)
    if snapshot.subtasks:
        lines.extend(["", f"## {_label(lang, 'subtasks')}", ""])
        lines.extend(
            (
                f"- **{_md_inline(subtask.id or _unnamed(lang))}** "
                f"[{_md_inline(_status_value(subtask.status, lang=lang))}] "
                f"{_md_inline(subtask.parent_package_id or _no_package(lang))} -> "
                f"{_md_inline(subtask.delegated_to or _unknown(lang))}: "
                f"{_md_inline(subtask.result_summary or subtask.objective)}"
            )
            for subtask in snapshot.subtasks
        )
    if snapshot.work_package_repairs:
        lines.extend(["", f"## {_label(lang, 'local_policy_repairs')}", ""])
        lines.extend(f"- {_md_inline(note)}" for note in snapshot.work_package_repairs)
    if snapshot.execution_log:
        lines.extend(["", f"## {_label(lang, 'execution_log')}", ""])
        lines.extend(f"- {_md_inline(entry)}" for entry in snapshot.execution_log)
    if snapshot.execution_recovery is not None:
        recovery = snapshot.execution_recovery
        lines.extend(
            [
                "",
                f"## {_label(lang, 'execution_recovery')}",
                "",
                f"- {_label(lang, 'execution')}: "
                f"{_md_inline(_status_value(recovery.state, lang=lang))}",
                f"- {_label(lang, 'run')}: {_md_inline(recovery.run_id or _unknown(lang))}",
                (
                    f"- {_label(lang, 'target')}: "
                    f"{_md_inline(recovery.target_workspace or _not_set(lang))}"
                ),
                (
                    f"- {_label(lang, 'running_packages')}: "
                    f"{_md_inline(', '.join(recovery.running_packages) or _none(lang))}"
                ),
                (
                    f"- {_label(lang, 'retry_candidates')}: "
                    f"{_md_inline(', '.join(recovery.retry_candidates) or _none(lang))}"
                ),
                (
                    f"- {_label(lang, 'done_packages')}: "
                    f"{_md_inline(', '.join(recovery.done_packages) or _none(lang))}"
                ),
                f"- {_label(lang, 'last_event')}: {_md_inline(recovery.last_event or _none(lang))}",
            ]
        )
    if snapshot.questions:
        lines.extend(["", f"## {_label(lang, 'open_questions')}", ""])
        lines.extend(
            f"- **{_md_inline(q.id)}**: {_md_inline(q.question)}" for q in snapshot.questions
        )

    return "\n".join(lines).rstrip() + "\n"


def unique_report_path(report_dir: Path, session_id: str) -> Path:
    """Return a report path that will not overwrite an existing export."""
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    millis = int((time.time() % 1) * 1000)
    sid = _safe_filename_part(session_id[:8] if session_id else "unknown")
    stem = f"report-{sid}-{timestamp}-{millis:03d}"
    path = report_dir / f"{stem}.md"
    counter = 1
    while path.exists():
        path = report_dir / f"{stem}-{counter}.md"
        counter += 1
    return path


def _md_inline(value: str) -> str:
    text = " ".join(str(value).split())
    return "".join(f"\\{char}" if char in _MD_SPECIAL_CHARS else char for char in text)


def _md_block(value: str) -> str:
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}\n{text}\n{fence}"


def _label(lang: str, key: str) -> str:
    labels = REPORT_MARKDOWN_LABELS.get(lang, REPORT_MARKDOWN_LABELS["en"])
    return labels.get(key, REPORT_MARKDOWN_LABELS["en"][key])


def _none(lang: str = "en") -> str:
    return _label(lang, "none")


def _unknown(lang: str = "en") -> str:
    return _label(lang, "unknown")


def _status_value(status: str, *, lang: str = "en") -> str:
    return display_status_value(status, lang=lang, empty=_unknown(lang))


def _not_set(lang: str = "en") -> str:
    return _label(lang, "not_set")


def _unnamed(lang: str = "en") -> str:
    return _label(lang, "unnamed")


def _untitled(lang: str = "en") -> str:
    return _label(lang, "untitled")


def _no_package(lang: str = "en") -> str:
    return _label(lang, "no_package")


def _provider_lines(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> list[str]:
    lines: list[str] = []
    for provider in snapshot.providers:
        if not provider.enabled:
            continue
        model = (
            provider.actual_model
            or provider.model_label
            or provider.configured_model
            or _label(lang, "default")
        )
        context = (
            f"{provider.context_window:,}"
            if provider.context_window > 0
            else _unknown(lang)
        )
        source = display_source_value(
            provider.budget_source,
            lang=lang,
            empty=_unknown(lang),
        )
        session = provider.session_id[:12] if provider.session_id else _none(lang)
        profile = _provider_profile_summary(provider, lang=lang)
        if profile:
            profile = f"; {profile}"
        lines.append(
            "- "
            f"**{_md_inline(provider.name)}**: "
            f"{_md_inline(model)}; "
            f"{_label(lang, 'context')} {_md_inline(context)} ({_md_inline(source)}); "
            f"{_label(lang, 'provider_session')} {_md_inline(session)}"
            f"{profile}"
        )
    return lines


def _provider_profile_summary(
    provider: ProviderSnapshot,
    *,
    lang: str = "en",
) -> str:
    parts: list[str] = []
    if provider.context_profile:
        parts.append(
            f"{_label(lang, 'profile')} "
            f"{_md_inline(display_profile_value(provider.context_profile, lang=lang))}"
        )
    if provider.profile_modes:
        parts.append(
            f"{_label(lang, 'modes')} "
            f"{_md_inline(_profile_values(provider.profile_modes, lang=lang))}"
        )
    if provider.output_contract:
        parts.append(
            f"{_label(lang, 'output')} "
            f"{_md_inline(display_profile_value(provider.output_contract, lang=lang))}"
        )
    if provider.profile_strengths:
        strengths = _profile_values(provider.profile_strengths[:3], lang=lang)
        if len(provider.profile_strengths) > 3:
            strengths = f"{strengths}, +{len(provider.profile_strengths) - 3}"
        parts.append(f"{_label(lang, 'strengths')} {_md_inline(strengths)}")
    if provider.profile_mission:
        parts.append(f"{_label(lang, 'mission')} {_md_inline(provider.profile_mission)}")
    return "; ".join(parts)


def _profile_values(values: list[str], *, lang: str = "en") -> str:
    return ", ".join(display_profile_value(value, lang=lang) for value in values)


def _agent_quality_lines(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> list[str]:
    return [_agent_quality_line(item, lang=lang) for item in snapshot.agent_quality]


def _agent_quality_line(item: AgentQualitySnapshot, *, lang: str = "en") -> str:
    return (
        f"- **{_md_inline(item.agent_name or _unknown(lang))}**: "
        f"{_label(lang, 'score')} {_md_inline(_format_score(item.score))}; "
        f"{_label(lang, 'success')} {item.success_count}/{item.signal_count}; "
        f"{_label(lang, 'blockers')} {item.blocker_count}; "
        f"{_label(lang, 'required_changes')} {item.required_change_count}"
    )


def _work_package_detail_lines(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> list[str]:
    lines: list[str] = []
    for package in snapshot.work_package_details:
        lines.extend(_work_package_lines(package, lang=lang))
    return lines


def _work_package_lines(
    package: WorkPackageSnapshot,
    *,
    lang: str = "en",
) -> list[str]:
    title = package.title or _untitled(lang)
    lines = [
        f"- **{_md_inline(package.id or _unnamed(lang))}** {_md_inline(title)}",
        (
            f"  - {_label(lang, 'status')}: "
            f"{_md_inline(_status_value(package.status, lang=lang))}; "
            f"{_label(lang, 'owner')} {_md_inline(package.owner_agent or _unknown(lang))}; "
            f"{_label(lang, 'executor')} {_md_inline(_package_executor(package, lang=lang))}; "
            f"{_label(lang, 'lane')} {_md_inline(_package_lane(package, lang=lang))}"
        ),
    ]
    routing = _package_routing_summary(package, lang=lang)
    if routing:
        lines.append(f"  - {_label(lang, 'routing')}: {routing}")
    if package.routing_reason:
        lines.append(
            f"  - {_label(lang, 'reason')}: "
            f"{_md_inline(display_profile_value(package.routing_reason, lang=lang))}"
        )
    if package.review_status or package.reviewer_agent:
        review_status = display_review_status_value(
            package.review_status,
            reviewer_agent=package.reviewer_agent,
            summary=package.review_summary,
            lang=lang,
        )
        review = (
            f"{_md_inline(review_status)}; "
            f"{_label(lang, 'reviewer')} {_md_inline(package.reviewer_agent or _none(lang))}"
        )
        if package.review_status == "skipped" and package.review_summary:
            reason = display_review_skip_reason(package.review_summary, lang=lang)
            review = (
                f"{review}; {_label(lang, 'review_reason')} "
                f"{_md_inline(reason)}"
            )
        lines.append(f"  - {_label(lang, 'review')}: {review}")
    return lines


def _package_executor(package: WorkPackageSnapshot, *, lang: str = "en") -> str:
    return (
        package.current_executor
        or package.last_executor
        or package.last_result_agent
        or _none(lang)
    )


def _package_lane(package: WorkPackageSnapshot, *, lang: str = "en") -> str:
    if not package.parallelizable:
        return "직렬" if lang == "ko" else "serial"
    if package.parallel_group is not None:
        return f"g{package.parallel_group}"
    return "미지정" if lang == "ko" else "unspecified"


def _package_routing_summary(
    package: WorkPackageSnapshot,
    *,
    lang: str = "en",
) -> str:
    parts: list[str] = []
    if package.task_kind:
        parts.append(
            f"{_label(lang, 'kind')} "
            f"{_md_inline(display_kind_value(package.task_kind, lang=lang))}"
        )
    if package.profile_revision:
        parts.append(f"{_label(lang, 'profile')} {_md_inline(package.profile_revision)}")
    if package.routing_score:
        parts.append(f"{_label(lang, 'score')} {_md_inline(_format_score(package.routing_score))}")
    return "; ".join(parts)


def _format_score(score: float) -> str:
    text = f"{score:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _safe_filename_part(value: str) -> str:
    cleaned = []
    for char in value:
        if char.isalnum() or char in {"-", "_"}:
            cleaned.append(char)
        else:
            cleaned.append("-")
    return "".join(cleaned).strip("-") or "unknown"
