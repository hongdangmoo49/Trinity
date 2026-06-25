from __future__ import annotations

from trinity.textual_app.snapshot import WorkPackageSnapshot
from trinity.textual_app.widgets.progress_summary import (
    blocked_detail_line,
    blocked_dependency_ids,
    blocked_work_packages,
    compact_wp_line,
    current_work_packages,
    next_work_package_entries,
    next_work_package_line,
    next_work_packages,
    progress_bar,
    progress_summary_line,
    waiting_on_detail_line,
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
    dependencies: list[str] | None = None,
    parallel_group: int | None = None,
    requires_execution: bool = True,
    repair_blocked_reason: str = "",
    last_result_status: str = "",
) -> WorkPackageSnapshot:
    return WorkPackageSnapshot(
        id=package_id,
        title=title,
        owner_agent=owner,
        status=status,
        current_executor=current_executor,
        dependencies=dependencies or [],
        parallel_group=parallel_group,
        requires_execution=requires_execution,
        repair_blocked_reason=repair_blocked_reason,
        repair_attempt_count=2 if repair_blocked_reason else 0,
        repair_max_attempts=2 if repair_blocked_reason else 0,
        last_result_status=last_result_status,
    )


def test_work_package_state_groups_statuses() -> None:
    assert work_package_state(_package("WP-001", "done")) == "done"
    assert work_package_state(_package("WP-001A", "succeeded")) == "done"
    assert (
        work_package_state(_package("WP-001B", "pending", last_result_status="succeeded"))
        == "done"
    )
    assert work_package_state(_package("WP-002", "running")) == "running"
    assert work_package_state(_package("WP-003", "pending")) == "waiting"
    assert work_package_state(_package("WP-003A", "needs_user_decision")) == "waiting"
    assert (
        work_package_state(_package("WP-003B", "waiting_for_external_input"))
        == "waiting"
    )
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
        _package("WP-004A", "needs_user_decision", title="Decision", owner="claude"),
        _package(
            "WP-004B",
            "waiting_for_external_input",
            title="External Input",
            owner="codex",
        ),
        _package("WP-005", "blocked", title="Adapter", repair_blocked_reason="missing token"),
    ]

    assert work_package_counts(packages) == {
        "done": 1,
        "running": 1,
        "waiting": 4,
        "blocked": 1,
    }
    assert [item.id for item in current_work_packages(packages)] == ["WP-002"]
    assert [item.id for item in next_work_packages(packages)] == [
        "WP-003",
        "WP-004",
        "WP-004A",
    ]
    assert [item.id for item in blocked_work_packages(packages)] == ["WP-005"]
    assert progress_summary_line(packages) == (
        "7 WP · 1 done · 1 running · 4 waiting · 1 blocked"
    )
    assert progress_bar(work_package_counts(packages)) == "[#>....!]"
    assert compact_wp_line(packages[1]) == "WP-002 Codex · Parser"
    assert blocked_detail_line(packages[-1]) == "repair 2/2 · missing token"


def test_work_package_progress_summary_supports_korean() -> None:
    packages = [
        _package("WP-001", "done"),
        _package("WP-002", "running"),
        _package("WP-003", "pending"),
    ]

    assert progress_summary_line([], lang="ko") == "작업 패키지 없음"
    assert progress_summary_line(packages, lang="ko") == (
        "작업 패키지 3개 · 완료 1 · 실행 1 · 대기 1"
    )


def test_progress_bar_compacts_width_but_keeps_nonzero_state_markers() -> None:
    bar = progress_bar(
        {
            "done": 5,
            "running": 4,
            "waiting": 7,
            "blocked": 2,
            "unknown": 1,
        },
        width=6,
    )

    assert bar.startswith("[")
    assert bar.endswith("]")
    assert len(bar.removeprefix("[").removesuffix("]")) == 6
    for marker in "#>.!?":
        assert marker in bar


def test_next_work_package_entries_prioritize_dependency_ready_packages() -> None:
    packages = [
        _package("WP-001", "running", title="Foundation"),
        _package("WP-002", "done", title="Schema"),
        _package(
            "WP-003",
            "pending",
            title="Renderer",
            owner="claude",
            dependencies=["WP-001"],
        ),
        _package(
            "WP-004",
            "pending",
            title="Parser",
            dependencies=["WP-002"],
            parallel_group=1,
        ),
        _package(
            "WP-005",
            "queued",
            title="Validator",
            owner="antigravity",
            parallel_group=1,
        ),
    ]

    entries = next_work_package_entries(packages, limit=None)

    assert [entry.package.id for entry in entries] == ["WP-004", "WP-005", "WP-003"]
    assert [entry.ready for entry in entries] == [True, True, False]
    assert entries[2].waiting_on == ("WP-001",)
    assert [item.id for item in next_work_packages(packages)] == [
        "WP-004",
        "WP-005",
        "WP-003",
    ]
    assert next_work_package_line(entries[0]) == "WP-004 Codex · Parser · group 1"
    assert waiting_on_detail_line(entries[2]) == "waiting on WP-001"


def test_blocked_dependency_ids_ignore_unknown_or_done_dependencies() -> None:
    packages = [
        _package("WP-001", "done"),
        _package("WP-002", "blocked"),
        _package("WP-003", "pending", dependencies=["WP-001", "WP-002", "WP-999"]),
    ]
    packages_by_id = {package.id: package for package in packages}

    assert blocked_dependency_ids(packages[2], packages_by_id) == ["WP-002"]


def test_next_work_package_entries_skip_non_executable_waiting_packages() -> None:
    packages = [
        _package("WP-001", "pending", requires_execution=False),
        _package("WP-002", "pending"),
    ]

    assert [entry.package.id for entry in next_work_package_entries(packages)] == [
        "WP-002"
    ]
