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
from trinity.textual_app.widgets.status_label import display_review_status_value

_MD_SPECIAL_CHARS = "\\`*_{}[]<>()#+-.!|"


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


def snapshot_report_markdown(snapshot: WorkflowNexusSnapshot) -> str:
    """Build a minimal Markdown report from an in-memory UI snapshot."""
    lines = [
        "# Deliberation Report",
        "",
        f"**Session**: {_md_inline(snapshot.session_id or '(none)')}  ",
        f"**Goal**: {_md_inline(snapshot.goal or '(none)')}  ",
        f"**State**: {_md_inline(snapshot.state)}  ",
        f"**Round**: {snapshot.round_num}  ",
        f"**Providers**: {len(snapshot.providers)}",
    ]

    provider_lines = _provider_lines(snapshot)
    if provider_lines:
        lines.extend(["", "## Providers", ""])
        lines.extend(provider_lines)
    quality_lines = _agent_quality_lines(snapshot)
    if quality_lines:
        lines.extend(["", "## Advisory Agent Quality", ""])
        lines.extend(quality_lines)
    if snapshot.synthesis.summary:
        lines.extend(
            [
                "",
                "## Consensus",
                "",
                f"**Progress**: {_md_inline(snapshot.synthesis.consensus_progress or '(none)')}  ",
                f"**Source**: {_md_inline(snapshot.synthesis.source)}",
                "",
                _md_block(snapshot.synthesis.summary),
            ]
        )
    if snapshot.decisions:
        lines.extend(["", "## Decisions", ""])
        lines.extend(f"- {_md_inline(decision)}" for decision in snapshot.decisions)
    if snapshot.central_work_packages:
        lines.extend(["", "## Central WP Graph", ""])
        lines.extend(f"- {_md_inline(package)}" for package in snapshot.central_work_packages)
    if snapshot.work_packages:
        heading = "## Local WP Graph" if snapshot.central_work_packages else "## Work Packages"
        lines.extend(["", heading, ""])
        lines.extend(f"- {_md_inline(package)}" for package in snapshot.work_packages)
    package_detail_lines = _work_package_detail_lines(snapshot)
    if package_detail_lines:
        lines.extend(["", "## Work Package Routing", ""])
        lines.extend(package_detail_lines)
    if snapshot.subtasks:
        lines.extend(["", "## Subtasks", ""])
        lines.extend(
            (
                f"- **{_md_inline(subtask.id or '(unnamed)')}** "
                f"[{_md_inline(subtask.status)}] "
                f"{_md_inline(subtask.parent_package_id or '(no package)')} -> "
                f"{_md_inline(subtask.delegated_to or '(unknown)')}: "
                f"{_md_inline(subtask.result_summary or subtask.objective)}"
            )
            for subtask in snapshot.subtasks
        )
    if snapshot.work_package_repairs:
        lines.extend(["", "## Local Policy Repairs", ""])
        lines.extend(f"- {_md_inline(note)}" for note in snapshot.work_package_repairs)
    if snapshot.execution_log:
        lines.extend(["", "## Execution Log", ""])
        lines.extend(f"- {_md_inline(entry)}" for entry in snapshot.execution_log)
    if snapshot.execution_recovery is not None:
        recovery = snapshot.execution_recovery
        lines.extend(
            [
                "",
                "## Execution Recovery",
                "",
                f"- Execution: {_md_inline(recovery.state)}",
                f"- Run: {_md_inline(recovery.run_id or '(unknown)')}",
                f"- Target: {_md_inline(recovery.target_workspace or '(not set)')}",
                (
                    "- Running packages: "
                    f"{_md_inline(', '.join(recovery.running_packages) or '(none)')}"
                ),
                (
                    "- Retry candidates: "
                    f"{_md_inline(', '.join(recovery.retry_candidates) or '(none)')}"
                ),
                f"- Done packages: {_md_inline(', '.join(recovery.done_packages) or '(none)')}",
                f"- Last event: {_md_inline(recovery.last_event or '(none)')}",
            ]
        )
    if snapshot.questions:
        lines.extend(["", "## Open Questions", ""])
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


def _provider_lines(snapshot: WorkflowNexusSnapshot) -> list[str]:
    lines: list[str] = []
    for provider in snapshot.providers:
        if not provider.enabled:
            continue
        model = provider.actual_model or provider.model_label or provider.configured_model or "default"
        context = (
            f"{provider.context_window:,}"
            if provider.context_window > 0
            else "unknown"
        )
        source = provider.budget_source or "unknown"
        session = provider.session_id[:12] if provider.session_id else "none"
        profile = _provider_profile_summary(provider)
        if profile:
            profile = f"; {profile}"
        lines.append(
            "- "
            f"**{_md_inline(provider.name)}**: "
            f"{_md_inline(model)}; "
            f"context {_md_inline(context)} ({_md_inline(source)}); "
            f"session {_md_inline(session)}"
            f"{profile}"
        )
    return lines


def _provider_profile_summary(provider: ProviderSnapshot) -> str:
    parts: list[str] = []
    if provider.context_profile:
        parts.append(f"profile {_md_inline(provider.context_profile)}")
    if provider.profile_modes:
        parts.append(f"modes {_md_inline(', '.join(provider.profile_modes))}")
    if provider.output_contract:
        parts.append(f"output {_md_inline(provider.output_contract)}")
    if provider.profile_strengths:
        strengths = ", ".join(provider.profile_strengths[:3])
        if len(provider.profile_strengths) > 3:
            strengths = f"{strengths}, +{len(provider.profile_strengths) - 3}"
        parts.append(f"strengths {_md_inline(strengths)}")
    if provider.profile_mission:
        parts.append(f"mission {_md_inline(provider.profile_mission)}")
    return "; ".join(parts)


def _agent_quality_lines(snapshot: WorkflowNexusSnapshot) -> list[str]:
    return [_agent_quality_line(item) for item in snapshot.agent_quality]


def _agent_quality_line(item: AgentQualitySnapshot) -> str:
    return (
        f"- **{_md_inline(item.agent_name or '(unknown)')}**: "
        f"score {_md_inline(_format_score(item.score))}; "
        f"success {item.success_count}/{item.signal_count}; "
        f"blockers {item.blocker_count}; "
        f"required changes {item.required_change_count}"
    )


def _work_package_detail_lines(snapshot: WorkflowNexusSnapshot) -> list[str]:
    lines: list[str] = []
    for package in snapshot.work_package_details:
        lines.extend(_work_package_lines(package))
    return lines


def _work_package_lines(package: WorkPackageSnapshot) -> list[str]:
    title = package.title or "(untitled)"
    lines = [
        f"- **{_md_inline(package.id or '(unnamed)')}** {_md_inline(title)}",
        (
            "  - Status: "
            f"{_md_inline(package.status or 'unknown')}; "
            f"owner {_md_inline(package.owner_agent or '(unknown)')}; "
            f"executor {_md_inline(_package_executor(package))}; "
            f"lane {_md_inline(_package_lane(package))}"
        ),
    ]
    routing = _package_routing_summary(package)
    if routing:
        lines.append(f"  - Routing: {routing}")
    if package.routing_reason:
        lines.append(f"  - Reason: {_md_inline(package.routing_reason)}")
    if package.review_status or package.reviewer_agent:
        review_status = display_review_status_value(
            package.review_status,
            reviewer_agent=package.reviewer_agent,
            summary=package.review_summary,
        )
        review = (
            f"{_md_inline(review_status)}; "
            f"reviewer {_md_inline(package.reviewer_agent or '(none)')}"
        )
        if package.review_status == "skipped" and package.review_summary:
            review = f"{review}; reason {_md_inline(package.review_summary)}"
        lines.append(f"  - Review: {review}")
    return lines


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
        parts.append(f"kind {_md_inline(package.task_kind)}")
    if package.profile_revision:
        parts.append(f"profile {_md_inline(package.profile_revision)}")
    if package.routing_score:
        parts.append(f"score {_md_inline(_format_score(package.routing_score))}")
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
