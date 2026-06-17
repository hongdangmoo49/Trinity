from __future__ import annotations

from trinity.textual_app.snapshot import WorkPackageSnapshot
from trinity.textual_app.widgets.progress_summary import (
    blocked_detail_line,
    blocked_work_packages,
    compact_wp_line,
    current_work_packages,
    next_work_packages,
    progress_bar,
    progress_summary_line,
    work_package_counts,
    work_package_state,
)


def _package(
    package_id: str,
    status: str,
    *,
    title: str = "Task",
    owner: str = "codex",
    current_executor: str = "",
    repair_blocked_reason: str = "",
    last_result_status: str = "",
) -> WorkPackageSnapshot:
    return WorkPackageSnapshot(
        id=package_id,
        title=title,
        owner_agent=owner,
        status=status,
        current_executor=current_executor,
        repair_blocked_reason=repair_blocked_reason,
        repair_attempt_count=2 if repair_blocked_reason else 0,
        repair_max_attempts=2 if repair_blocked_reason else 0,
        last_result_status=last_result_status,
    )


def test_work_package_state_groups_statuses() -> None:
    assert work_package_state(_package("WP-001", "done")) == "done"
    assert work_package_state(_package("WP-002", "running")) == "running"
    assert work_package_state(_package("WP-003", "pending")) == "waiting"
    assert work_package_state(_package("WP-004", "blocked")) == "blocked"
    assert (
        work_package_state(
            _package("WP-005", "pending", repair_blocked_reason="needs key")
        )
        == "blocked"
    )
    assert (
        work_package_state(_package("WP-006", "pending", last_result_status="failed"))
        == "blocked"
    )


def test_work_package_progress_helpers_surface_current_next_blocked() -> None:
    packages = [
        _package("WP-001", "done", title="Done"),
        _package("WP-002", "running", title="Parser", current_executor="codex"),
        _package("WP-003", "pending", title="Renderer", owner="claude"),
        _package("WP-004", "pending", title="Validator", owner="antigravity"),
        _package("WP-005", "blocked", title="Adapter", repair_blocked_reason="missing token"),
    ]

    assert work_package_counts(packages) == {
        "done": 1,
        "running": 1,
        "waiting": 2,
        "blocked": 1,
    }
    assert [item.id for item in current_work_packages(packages)] == ["WP-002"]
    assert [item.id for item in next_work_packages(packages)] == ["WP-003", "WP-004"]
    assert [item.id for item in blocked_work_packages(packages)] == ["WP-005"]
    assert progress_summary_line(packages) == (
        "5 WP · 1 done · 1 running · 2 waiting · 1 blocked"
    )
    assert progress_bar(work_package_counts(packages)) == "[#>..!]"
    assert compact_wp_line(packages[1]) == "WP-002 Codex · Parser"
    assert blocked_detail_line(packages[4]) == "repair 2/2 · missing token"


def test_work_package_progress_summary_supports_korean() -> None:
    packages = [
        _package("WP-001", "done"),
        _package("WP-002", "running"),
        _package("WP-003", "pending"),
    ]

    assert progress_summary_line(packages, lang="ko") == (
        "3 WP · 완료 1 · 실행 1 · 대기 1"
    )

