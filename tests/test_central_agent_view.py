from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.textual_app.snapshot import (
    ExecutionRecoverySnapshot,
    LocalCommandSnapshot,
    QuestionSnapshot,
    SynthesisSnapshot,
    SubtaskSnapshot,
    WorkPackageSnapshot,
    WorkflowNexusSnapshot,
)
from trinity.textual_app.presenters import (
    CentralActionButton,
    CentralActionPlan,
    central_action_plan,
    should_show_blueprint_actions,
)
from trinity.textual_app.widgets.central_agent import CentralAgentView


class CentralAgentHarness(App[None]):
    def __init__(self, view: CentralAgentView) -> None:
        super().__init__()
        self.view = view

    def compose(self) -> ComposeResult:
        yield self.view


def test_central_markdown_keeps_conversation_and_hides_internal_dump() -> None:
    view = CentralAgentView()
    view.snapshot = WorkflowNexusSnapshot(
        session_id="wf-graph",
        state="blueprint_ready",
        goal="Build app",
        synthesis=SynthesisSnapshot(summary="Agreed app blueprint."),
        central_work_packages=["frontend: Build the UI"],
        work_packages=["WP-001 codex: Build the UI (pending)"],
        decisions=["Use hidden internal detail."],
        subtasks=[
            SubtaskSnapshot(
                id="sub-1",
                parent_package_id="WP-001",
                parent_agent="claude",
                delegated_to="codex",
                objective="Internal task",
                result_summary="Done",
                status="done",
            )
        ],
        work_package_repairs=["Repair note"],
        local_commands=[
            LocalCommandSnapshot(
                command="/status",
                title="Status",
                body="Current status.",
            )
        ],
    )

    markdown = view._markdown()

    assert "### Work Packages" in markdown
    assert "- 1 package · ready" in markdown
    assert "Open Inspector or Report" in markdown
    assert "- WP-001 codex: Build the UI (pending)" not in markdown
    assert "### Command Result" in markdown
    assert "Current status." in markdown
    assert "### Decisions" not in markdown
    assert "### Subtasks" not in markdown
    assert "### Local Policy Repairs" not in markdown
    assert "### Local Command Results" not in markdown


def test_central_markdown_surfaces_blueprint_response_before_wp_overview() -> None:
    view = CentralAgentView()
    view.snapshot = WorkflowNexusSnapshot(
        session_id="wf-blueprint",
        state="blueprint_ready",
        goal="Build game",
        synthesis=SynthesisSnapshot(summary="Vampire survival blueprint."),
        central_blueprint=(
            "**Vampire Survival Roguelike**\n\n"
            "Use a wave loop, enemy spawners, weapon upgrades, and run meta data.\n\n"
            "#### Architecture\n"
            "- Combat loop: detailed internal design."
        ),
        central_work_packages=["gameplay: Build combat loop"],
    )

    markdown = view._markdown()

    assert "### Central Agent Response" in markdown
    assert "**Vampire Survival Roguelike**" in markdown
    assert "weapon upgrades" in markdown
    assert "Architecture" not in markdown
    assert "Combat loop" not in markdown
    assert markdown.index("### Central Agent Response") < markdown.index("### Work Packages")


def test_central_markdown_compacts_verbose_blueprint_for_user_view() -> None:
    view = CentralAgentView(lang="ko")
    view.snapshot = WorkflowNexusSnapshot(
        state="blueprint_ready",
        goal="테스트입니다",
        synthesis=SynthesisSnapshot(consensus_progress="blueprint ready"),
        central_blueprint=(
            "제안: 테스트 요청 처리 및 시스템 검증\n"
            "사용자 테스트 메시지 정상 수신. 시스템 초기 응답 및 기본 구성 요소 검증.\n\n"
            "Architecture\n"
            "- 입력 채널: 사용자 입력 (CLI/TUI)\n"
            "Data Flow\n"
            "- 사용자 요청 -> 에이전트 분석 -> 검증 결과 제안\n"
            "Acceptance Criteria\n"
            "- 에이전트 환경 정보 읽기 성공 ([src/trinity](file:///home/user/workspace/Trinity/src/trinity) 확인)\n"
            "작업 패키지 (Work Packages)\n"
            "- WP-001 claude: 입력 채널"
        ),
        work_packages=[
            "WP-001 claude: 입력 채널 (pending)",
            "WP-002 codex: 파서 (pending)",
            "WP-003 antigravity: 검증 대상 (pending)",
        ],
    )

    markdown = view._markdown()

    assert "제안: 테스트 요청 처리 및 시스템 검증" in markdown
    assert "사용자 테스트 메시지 정상 수신" in markdown
    assert "Architecture" not in markdown
    assert "Data Flow" not in markdown
    assert "Acceptance Criteria" not in markdown
    assert "file://" not in markdown
    assert "WP-001 claude: 입력 채널" not in markdown
    assert "**종합:** `설계 준비됨`" in markdown
    assert "blueprint ready" not in markdown
    assert "3개 작업 패키지" in markdown
    assert "상세 설계와 작업 패키지 목록은 인스펙터 또는 리포트" in markdown


def test_central_markdown_localizes_korean_current_focus() -> None:
    view = CentralAgentView(lang="ko")
    view.snapshot = WorkflowNexusSnapshot(
        state="executing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="클라이언트",
                owner_agent="codex",
                current_executor="codex",
                status="blocked",
                last_result_blockers=[
                    "파일 없음",
                    "테스트 실패",
                    "리뷰 필요",
                ],
            )
        ],
    )

    markdown = view._markdown()

    assert "### 현재 진행/주의 항목" in markdown
    assert "- **WP-001** [차단] `codex`: 클라이언트" in markdown
    assert "  - 차단 요소: 파일 없음, 테스트 실패, +1개 더" in markdown
    assert "[blocked]" not in markdown
    assert "Blockers:" not in markdown
    assert "+1 more" not in markdown


def test_blueprint_next_actions_only_show_when_ready_with_packages() -> None:
    assert should_show_blueprint_actions(
        WorkflowNexusSnapshot(
            state="blueprint_ready",
            work_packages=["WP-001 codex: Build loop (pending)"],
        )
    )
    assert not should_show_blueprint_actions(
        WorkflowNexusSnapshot(
            state="executing",
            work_packages=["WP-001 codex: Build loop (running)"],
        )
    )
    assert not should_show_blueprint_actions(
        WorkflowNexusSnapshot(state="blueprint_ready")
    )


def test_central_action_plan_prioritizes_provider_error_gate() -> None:
    plan = central_action_plan(
        WorkflowNexusSnapshot(
            state="needs_user_decision",
            questions=[
                QuestionSnapshot(
                    id="q-provider-error-retry",
                    question="Provider errors occurred.",
                    options=[
                        "Retry failed providers",
                        "Continue without failed providers",
                        "Stop workflow",
                    ],
                )
            ],
            execution_recovery=ExecutionRecoverySnapshot(
                state="failed",
                retry_candidates=("WP-001",),
            ),
            work_package_details=[
                WorkPackageSnapshot(
                    id="WP-001",
                    title="Client",
                    owner_agent="codex",
                    status="blocked",
                    repair_blocked_reason="duplicate_required_changes",
                )
            ],
        )
    )

    assert plan.title_key == "provider_error_action"
    assert [button.action for button in plan.buttons] == [
        "provider-error-retry",
        "provider-error-continue",
        "provider-error-stop",
    ]


def test_central_action_plan_prioritizes_repair_over_execution_retry() -> None:
    plan = central_action_plan(
        WorkflowNexusSnapshot(
            state="needs_user_decision",
            execution_recovery=ExecutionRecoverySnapshot(
                state="repair_blocked",
                retry_candidates=("WP-001",),
            ),
            work_package_details=[
                WorkPackageSnapshot(
                    id="WP-001",
                    title="Client",
                    owner_agent="codex",
                    status="blocked",
                    repair_blocked_reason="duplicate_required_changes",
                )
            ],
        )
    )

    assert plan.title_key == "repair_action"
    assert [button.action for button in plan.buttons] == [
        "repair-retry-once",
        "repair-mark-done",
        "repair-open-review",
        "repair-stop",
    ]


def test_central_action_plan_uses_execution_retry_before_blueprint_actions() -> None:
    plan = central_action_plan(
        WorkflowNexusSnapshot(
            state="blueprint_ready",
            work_packages=["WP-001 codex: Build loop (failed)"],
            execution_recovery=ExecutionRecoverySnapshot(
                state="failed",
                retry_candidates=("WP-001",),
            ),
        )
    )

    assert plan.title_key == "execution_recovery_action"
    assert [button.action for button in plan.buttons] == ["execution-retry"]


def test_central_action_plan_falls_back_to_blueprint_actions() -> None:
    plan = central_action_plan(
        WorkflowNexusSnapshot(
            state="blueprint_ready",
            work_packages=["WP-001 codex: Build loop (pending)"],
        )
    )

    assert plan.title_key == "next_action"
    assert [button.action for button in plan.buttons] == [
        "execute",
        "refine-features",
        "refine-risks",
        "refine-work-packages",
    ]


def test_central_markdown_summarizes_execution_progress_without_result_dump() -> None:
    view = CentralAgentView()
    view.snapshot = WorkflowNexusSnapshot(
        session_id="wf-results",
        state="executing",
        goal="Build app",
        work_packages=["WP-001 codex: Build API (done)"],
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Build API",
                owner_agent="codex",
                status="done",
                last_result_agent="codex",
                last_result_status="done",
                last_result_summary="Implemented API endpoints.",
                last_result_files_changed=["src/api.py", "tests/test_api.py"],
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Wire UI",
                owner_agent="claude",
                status="running",
                current_executor="claude",
                last_result_agent="claude",
                last_result_status="",
                last_result_summary="Wiring UI to API contract.",
            ),
            WorkPackageSnapshot(
                id="WP-003",
                title="Fix auth",
                owner_agent="codex",
                status="blocked",
                repair_blocked_reason="missing token",
            ),
        ],
    )

    markdown = view._markdown()

    assert "Progress" in markdown
    assert "1 done / 1 running / 0 waiting / 1 blocked" in markdown
    assert "3 WP · 1 done · 1 running · 1 blocked" in markdown
    assert "Current: WP-002 Claude · Wire UI" in markdown
    assert "Blocked: WP-003 Codex · Fix auth" in markdown
    assert "### Current Focus" in markdown
    assert "- **WP-002** [running] `claude`: Wire UI" in markdown
    assert "- **WP-003** [blocked] `codex`: Fix auth" in markdown
    assert "### Execution Result Summary" not in markdown
    assert "Files: src/api.py, tests/test_api.py" not in markdown


@pytest.mark.asyncio
async def test_central_view_reuses_composed_fixed_widgets_for_updates() -> None:
    view = CentralAgentView()
    app = CentralAgentHarness(view)

    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        query_calls: list[str] = []
        original_query_one = view.query_one

        def counted_query_one(selector, *args, **kwargs):
            fixed_selectors = {
                "#central-title",
                "#central-markdown",
                "#central-local-command-tables",
                "#central-action-title",
                "#central-actions",
            }
            if selector in fixed_selectors:
                query_calls.append(selector)
            return original_query_one(selector, *args, **kwargs)

        view.query_one = counted_query_one

        view.apply_snapshot(
            WorkflowNexusSnapshot(
                state="blueprint_ready",
                synthesis=SynthesisSnapshot(summary="Ready to build."),
                work_packages=["WP-001 codex: Build API (pending)"],
                local_commands=[
                    LocalCommandSnapshot(
                        command="/status",
                        title="Status",
                        body="Current state.",
                        table_columns=("WP", "Status"),
                        table_rows=(("WP-001", "done"),),
                    )
                ],
            )
        )
        await pilot.pause()

        view.apply_snapshot(
            WorkflowNexusSnapshot(
                state="executing",
                synthesis=SynthesisSnapshot(status="running", summary="Running."),
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Build API",
                        owner_agent="codex",
                        status="running",
                    )
                ],
            )
        )
        await pilot.pause()

        assert query_calls == []


@pytest.mark.asyncio
async def test_central_activity_frame_skips_idle_title_update() -> None:
    view = CentralAgentView()
    view.snapshot = WorkflowNexusSnapshot(state="blueprint_ready")
    app = CentralAgentHarness(view)

    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        title = view.query_one("#central-title", Static)
        updates: list[str] = []
        original_update = title.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        title.update = counted_update

        view.set_activity_frame(1)
        await pilot.pause()

        assert view._activity_frame == 1
        assert updates == []


@pytest.mark.asyncio
async def test_central_apply_snapshot_skips_unchanged_title_update() -> None:
    view = CentralAgentView()
    snapshot = WorkflowNexusSnapshot(state="blueprint_ready")
    app = CentralAgentHarness(view)

    async with app.run_test(size=(80, 20)) as pilot:
        view.apply_snapshot(snapshot)
        await pilot.pause()
        title = view.query_one("#central-title", Static)
        updates: list[str] = []
        original_update = title.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        title.update = counted_update

        view.apply_snapshot(snapshot)
        await pilot.pause()
        assert updates == []

        view.apply_snapshot(WorkflowNexusSnapshot(state="executing"))
        await pilot.pause()

        assert updates == ["Central Agent |"]


@pytest.mark.asyncio
async def test_central_apply_snapshot_skips_same_snapshot_object_reapply() -> None:
    view = CentralAgentView()
    snapshot = WorkflowNexusSnapshot(state="blueprint_ready")
    app = CentralAgentHarness(view)

    async with app.run_test(size=(80, 20)) as pilot:
        view.apply_snapshot(snapshot)
        await pilot.pause()

        calls: list[str] = []

        def counted_markdown() -> str:
            calls.append("markdown")
            return ""

        view._markdown = counted_markdown

        view.apply_snapshot(snapshot)
        await pilot.pause()
        assert calls == []

        view.apply_snapshot(WorkflowNexusSnapshot(state="blueprint_ready"))
        await pilot.pause()
        assert calls == ["markdown"]


@pytest.mark.asyncio
async def test_central_apply_snapshot_skips_unchanged_running_class_sync() -> None:
    view = CentralAgentView()
    app = CentralAgentHarness(view)

    async with app.run_test(size=(80, 20)) as pilot:
        view.apply_snapshot(WorkflowNexusSnapshot(state="executing"))
        await pilot.pause()

        class_calls: list[bool] = []
        original_set_class = view.set_class

        def counted_set_class(add: bool, class_name: str) -> None:
            if class_name == "central-running":
                class_calls.append(add)
            original_set_class(add, class_name)

        view.set_class = counted_set_class

        view.apply_snapshot(WorkflowNexusSnapshot(state="reviewing"))
        await pilot.pause()
        assert class_calls == []

        view.apply_snapshot(WorkflowNexusSnapshot(state="blueprint_ready"))
        await pilot.pause()
        assert class_calls == [False]


@pytest.mark.asyncio
async def test_central_apply_snapshot_skips_unchanged_action_plan_render() -> None:
    view = CentralAgentView()
    first = WorkflowNexusSnapshot(
        state="executing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Build API",
                owner_agent="codex",
                status="running",
            )
        ],
    )
    second = WorkflowNexusSnapshot(
        state="executing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Build API",
                owner_agent="codex",
                status="done",
            )
        ],
    )
    app = CentralAgentHarness(view)

    async with app.run_test(size=(80, 20)) as pilot:
        view.apply_snapshot(first)
        await pilot.pause()

        renders: list[object] = []
        original_render = view._render_blueprint_actions

        def counted_render(plan) -> None:
            renders.append(plan)
            original_render(plan)

        view._render_blueprint_actions = counted_render

        view.apply_snapshot(second)
        await pilot.pause()
        assert renders == []

        view.apply_snapshot(
            WorkflowNexusSnapshot(
                state="blueprint_ready",
                work_packages=["WP-001 codex: Build API (pending)"],
            )
        )
        await pilot.pause()

        assert len(renders) == 1


@pytest.mark.asyncio
async def test_central_apply_snapshot_skips_body_only_local_command_table_render() -> None:
    view = CentralAgentView()
    app = CentralAgentHarness(view)

    def snapshot(body: str, rows: tuple[tuple[str, ...], ...]) -> WorkflowNexusSnapshot:
        return WorkflowNexusSnapshot(
            state="blueprint_ready",
            local_commands=[
                LocalCommandSnapshot(
                    command="/status",
                    title="Status",
                    body=body,
                    table_columns=("WP", "Status"),
                    table_rows=rows,
                )
            ],
        )

    async with app.run_test(size=(80, 20)) as pilot:
        view.apply_snapshot(snapshot("Initial body.", (("WP-001", "done"),)))
        await pilot.pause()

        renders: list[list[LocalCommandSnapshot]] = []
        original_render = view._render_local_command_tables

        def counted_render(commands: list[LocalCommandSnapshot]) -> None:
            renders.append(commands)
            original_render(commands)

        view._render_local_command_tables = counted_render

        view.apply_snapshot(snapshot("Updated body.", (("WP-001", "done"),)))
        await pilot.pause()
        assert renders == []

        view.apply_snapshot(snapshot("Updated body.", (("WP-001", "failed"),)))
        await pilot.pause()
        assert len(renders) == 1


@pytest.mark.asyncio
async def test_central_action_render_skips_unchanged_title_update() -> None:
    view = CentralAgentView()
    app = CentralAgentHarness(view)

    async with app.run_test(size=(80, 20)) as pilot:
        first = CentralActionPlan(
            "next_actions",
            (
                CentralActionButton(
                    "execute",
                    "execute",
                    "primary",
                    "execute_tooltip",
                ),
            ),
        )
        second = CentralActionPlan(
            "next_actions",
            (
                CentralActionButton(
                    "refine-features",
                    "refine_features",
                    "default",
                    "refine-features_tooltip",
                ),
            ),
        )

        view._render_blueprint_actions(first)
        await pilot.pause()

        title = view.query_one("#central-action-title", Static)
        updates: list[str] = []
        original_update = title.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        title.update = counted_update

        view._render_blueprint_actions(second)
        await pilot.pause()
        assert updates == []

        view._render_blueprint_actions(CentralActionPlan())
        await pilot.pause()
        assert updates == [""]


@pytest.mark.asyncio
async def test_central_activity_frame_updates_running_title() -> None:
    view = CentralAgentView()
    view.snapshot = WorkflowNexusSnapshot(state="executing")
    app = CentralAgentHarness(view)

    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        title = view.query_one("#central-title", Static)
        updates: list[str] = []
        original_update = title.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        title.update = counted_update

        view.set_activity_frame(1)
        await pilot.pause()

        assert updates == ["Central Agent /"]

        updates.clear()
        view.set_activity_frame(1)
        await pilot.pause()

        assert updates == []
