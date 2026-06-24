"""Compact work-package progress projections for Nexus widgets."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from trinity.textual_app.snapshot import WorkPackageSnapshot


PROGRESS_ORDER = ("done", "running", "waiting", "blocked", "unknown")
PROGRESS_CHARS = {
    "blocked": "!",
    "done": "#",
    "running": ">",
    "unknown": "?",
    "waiting": ".",
}
DONE_STATUSES = {"completed", "done", "success"}
RUNNING_STATUSES = {"executing", "reviewing", "running"}
WAITING_STATUSES = {"pending", "queued", "waiting"}
BLOCKED_STATUSES = {"blocked", "failed"}


@dataclass(frozen=True)
class NextWorkPackageEntry:
    """Dependency-aware projection for the Inspector Next section."""

    package: WorkPackageSnapshot
    waiting_on: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.waiting_on

    @property
    def parallel_group(self) -> int | None:
        return self.package.parallel_group


def work_package_state(package: WorkPackageSnapshot) -> str:
    """Return the compact UI state bucket for a work package."""
    status = (package.status or "").strip().lower()
    result_status = (package.last_result_status or "").strip().lower()
    if (
        status in BLOCKED_STATUSES
        or result_status in BLOCKED_STATUSES
        or bool(package.repair_blocked_reason)
    ):
        return "blocked"
    if status in DONE_STATUSES or result_status == "done":
        return "done"
    if status in RUNNING_STATUSES or bool(package.current_executor):
        return "running"
    if status in WAITING_STATUSES:
        return "waiting"
    return "unknown"


def work_package_counts(
    packages: Iterable[WorkPackageSnapshot],
) -> dict[str, int]:
    """Count work packages by compact progress bucket."""
    counts = {key: 0 for key in PROGRESS_ORDER}
    for package in packages:
        counts[work_package_state(package)] += 1
    return {key: value for key, value in counts.items() if value}


def current_work_packages(
    packages: Iterable[WorkPackageSnapshot],
    *,
    limit: int = 3,
) -> list[WorkPackageSnapshot]:
    """Return packages actively running now."""
    return [
        package
        for package in packages
        if work_package_state(package) == "running"
    ][:limit]


def next_work_packages(
    packages: Iterable[WorkPackageSnapshot],
    *,
    limit: int = 3,
) -> list[WorkPackageSnapshot]:
    """Return dependency-ready waiting packages first, then dependency-waiting ones."""
    return [
        entry.package
        for entry in next_work_package_entries(packages, limit=limit)
    ]


def next_work_package_entries(
    packages: Iterable[WorkPackageSnapshot],
    *,
    limit: int | None = 3,
) -> list[NextWorkPackageEntry]:
    """Return dependency-aware Next entries for waiting work packages."""
    package_list = list(packages)
    packages_by_id = {package.id: package for package in package_list if package.id}
    entries = [
        NextWorkPackageEntry(
            package=package,
            waiting_on=tuple(blocked_dependency_ids(package, packages_by_id)),
        )
        for package in package_list
        if package.requires_execution and work_package_state(package) == "waiting"
    ]
    entries.sort(key=lambda entry: (0 if entry.ready else 1))
    if limit is None:
        return entries
    return entries[:limit]


def blocked_dependency_ids(
    package: WorkPackageSnapshot,
    packages_by_id: dict[str, WorkPackageSnapshot],
) -> list[str]:
    """Return internal dependencies that have not reached the compact done state."""
    return [
        dep_id
        for dep_id in package.dependencies
        if packages_by_id.get(dep_id)
        and work_package_state(packages_by_id[dep_id]) != "done"
    ]


def blocked_work_packages(
    packages: Iterable[WorkPackageSnapshot],
    *,
    limit: int = 3,
) -> list[WorkPackageSnapshot]:
    """Return blocked or failed packages that need attention."""
    return [
        package
        for package in packages
        if work_package_state(package) == "blocked"
    ][:limit]


def progress_bar(
    counts: dict[str, int],
    *,
    width: int = 12,
) -> str:
    """Render a tiny textual progress bar for compact terminals."""
    chars: list[str] = []
    for key in PROGRESS_ORDER:
        chars.extend(PROGRESS_CHARS[key] for _ in range(counts.get(key, 0)))
    if not chars:
        return "[none]"
    if len(chars) <= width:
        return "[" + "".join(chars) + "]"

    total = len(chars)
    allocations: dict[str, int] = {}
    for key in PROGRESS_ORDER:
        count = counts.get(key, 0)
        if count:
            allocations[key] = max(1, round(count / total * width))
    while sum(allocations.values()) > width:
        key = max(allocations, key=lambda item: allocations[item])
        if allocations[key] > 1:
            allocations[key] -= 1
        else:
            break
    while sum(allocations.values()) < width:
        key = max(counts, key=lambda item: counts[item])
        allocations[key] = allocations.get(key, 0) + 1
    compact: list[str] = []
    for key in PROGRESS_ORDER:
        compact.extend(PROGRESS_CHARS[key] for _ in range(allocations.get(key, 0)))
    return "[" + "".join(compact[:width]) + "]"


def progress_summary_line(
    packages: Iterable[WorkPackageSnapshot],
    *,
    lang: str = "en",
) -> str:
    """Return a one-line count summary."""
    package_list = list(packages)
    counts = work_package_counts(package_list)
    total = sum(counts.values())
    if total <= 0:
        return "WP 없음" if lang == "ko" else "No WPs"
    if lang == "ko":
        labels = {
            "blocked": "막힘",
            "done": "완료",
            "running": "실행",
            "unknown": "알 수 없음",
            "waiting": "대기",
        }
        parts = [f"{total} WP"]
        parts.extend(
            f"{labels[key]} {counts[key]}"
            for key in PROGRESS_ORDER
            if counts.get(key)
        )
        return " · ".join(parts)
    parts = [f"{total} WP"]
    parts.extend(
        f"{counts[key]} {key}"
        for key in PROGRESS_ORDER
        if counts.get(key)
    )
    return " · ".join(parts)


def compact_wp_line(package: WorkPackageSnapshot, *, lang: str = "en") -> str:
    """Render a compact WP identity line."""
    actor = (
        package.current_executor
        or package.last_executor
        or package.owner_agent
    )
    actor_label = actor.title() if actor else ("미지정" if lang == "ko" else "Unassigned")
    title = package.title or package.topic or package.id
    return f"{package.id} {actor_label} · {title}"


def next_work_package_line(
    entry: NextWorkPackageEntry,
    *,
    lang: str = "en",
) -> str:
    """Render a compact Next entry line with parallel-group hints."""
    line = compact_wp_line(entry.package, lang=lang)
    if entry.ready and entry.parallel_group is not None:
        group_label = "그룹" if lang == "ko" else "group"
        line = f"{line} · {group_label} {entry.parallel_group}"
    return line


def waiting_on_detail_line(
    entry: NextWorkPackageEntry,
    *,
    lang: str = "en",
) -> str:
    """Render a compact dependency-waiting reason for a Next entry."""
    if not entry.waiting_on:
        return ""
    dependencies = ", ".join(entry.waiting_on[:2])
    remaining = len(entry.waiting_on) - 2
    if remaining > 0:
        if lang == "ko":
            dependencies = f"{dependencies} 외 {remaining}개"
        else:
            dependencies = f"{dependencies}, +{remaining} more"
    if lang == "ko":
        return f"대기: {dependencies}"
    return f"waiting on {dependencies}"


def blocked_detail_line(
    package: WorkPackageSnapshot,
    *,
    lang: str = "en",
) -> str:
    """Render a compact blocked reason line."""
    details: list[str] = []
    if package.repair_max_attempts:
        repair_label = "복구" if lang == "ko" else "repair"
        details.append(
            f"{repair_label} {package.repair_attempt_count}/{package.repair_max_attempts}"
        )
    reason = (
        package.repair_blocked_reason
        or ", ".join(package.last_result_blockers[:2])
        or package.last_result_summary
    )
    if reason:
        details.append(reason)
    return " · ".join(details)
