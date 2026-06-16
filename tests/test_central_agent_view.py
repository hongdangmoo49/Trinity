from __future__ import annotations

from trinity.textual_app.snapshot import (
    LocalCommandSnapshot,
    SynthesisSnapshot,
    SubtaskSnapshot,
    WorkPackageSnapshot,
    WorkflowNexusSnapshot,
)
from trinity.textual_app.widgets.central_agent import CentralAgentView


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
    assert "3개 작업 패키지" in markdown
    assert "상세 설계와 WP 목록은 Inspector 또는 Report" in markdown


def test_blueprint_next_actions_only_show_when_ready_with_packages() -> None:
    assert CentralAgentView._should_show_blueprint_actions(
        WorkflowNexusSnapshot(
            state="blueprint_ready",
            work_packages=["WP-001 codex: Build loop (pending)"],
        )
    )
    assert not CentralAgentView._should_show_blueprint_actions(
        WorkflowNexusSnapshot(
            state="executing",
            work_packages=["WP-001 codex: Build loop (running)"],
        )
    )
    assert not CentralAgentView._should_show_blueprint_actions(
        WorkflowNexusSnapshot(state="blueprint_ready")
    )


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
                last_result_agent="claude",
                last_result_status="",
                last_result_summary="Wiring UI to API contract.",
            ),
        ],
    )

    markdown = view._markdown()

    assert "Progress" in markdown
    assert "1 done / 1 running / 0 pending" in markdown
    assert "### Current Focus" in markdown
    assert "**WP-002** [running] `claude`: Wire UI" in markdown
    assert "### Execution Result Summary" not in markdown
    assert "Files: src/api.py, tests/test_api.py" not in markdown
