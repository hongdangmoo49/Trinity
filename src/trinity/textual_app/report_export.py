"""Markdown export helpers for the Textual report screen."""

from __future__ import annotations

import time
from pathlib import Path

from trinity.textual_app.snapshot import WorkflowNexusSnapshot

_MD_SPECIAL_CHARS = "\\`*_{}[]<>()#+-.!|"


def snapshot_has_report_data(snapshot: WorkflowNexusSnapshot) -> bool:
    """Return whether a snapshot has enough user-visible data to export."""
    return any(
        (
            snapshot.session_id,
            snapshot.goal,
            snapshot.synthesis.summary,
            snapshot.decisions,
            snapshot.central_work_packages,
            snapshot.work_packages,
            snapshot.work_package_repairs,
            snapshot.execution_log,
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
        lines.extend(
            f"- {_md_inline(package)}" for package in snapshot.central_work_packages
        )
    if snapshot.work_packages:
        heading = (
            "## Local WP Graph"
            if snapshot.central_work_packages
            else "## Work Packages"
        )
        lines.extend(["", heading, ""])
        lines.extend(f"- {_md_inline(package)}" for package in snapshot.work_packages)
    if snapshot.work_package_repairs:
        lines.extend(["", "## Local Policy Repairs", ""])
        lines.extend(f"- {_md_inline(note)}" for note in snapshot.work_package_repairs)
    if snapshot.execution_log:
        lines.extend(["", "## Execution Log", ""])
        lines.extend(f"- {_md_inline(entry)}" for entry in snapshot.execution_log)
    if snapshot.questions:
        lines.extend(["", "## Open Questions", ""])
        lines.extend(
            f"- **{_md_inline(q.id)}**: {_md_inline(q.question)}"
            for q in snapshot.questions
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


def _safe_filename_part(value: str) -> str:
    cleaned = []
    for char in value:
        if char.isalnum() or char in {"-", "_"}:
            cleaned.append(char)
        else:
            cleaned.append("-")
    return "".join(cleaned).strip("-") or "unknown"
