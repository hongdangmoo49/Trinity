from __future__ import annotations

from trinity.textual_app.snapshot import (
    LocalCommandSnapshot,
    SynthesisSnapshot,
    WorkPackageSnapshot,
    WorkflowNexusSnapshot,
)
from trinity.textual_app.widgets.central_agent import CentralAgentView


def test_central_markdown_surfaces_wp_graph_before_local_commands() -> None:
    view = CentralAgentView()
    view.snapshot = WorkflowNexusSnapshot(
        session_id="wf-graph",
        state="blueprint_ready",
        goal="Build app",
        synthesis=SynthesisSnapshot(summary="Agreed app blueprint."),
        central_work_packages=["frontend: Build the UI"],
        work_packages=["WP-001 codex: Build the UI (pending)"],
        local_commands=[
            LocalCommandSnapshot(
                command="/status",
                title="Status",
                body="Current status.",
            )
        ],
    )

    markdown = view._markdown()

    assert "### Central WP Graph" in markdown
    assert "- frontend: Build the UI" in markdown
    assert "### Local WP Graph" in markdown
    assert "- WP-001 codex: Build the UI (pending)" in markdown
    assert markdown.index("### Central WP Graph") < markdown.index(
        "### Local Command Results"
    )


def test_central_markdown_surfaces_blueprint_response_before_wp_graph() -> None:
    view = CentralAgentView()
    view.snapshot = WorkflowNexusSnapshot(
        session_id="wf-blueprint",
        state="blueprint_ready",
        goal="Build game",
        synthesis=SynthesisSnapshot(summary="Vampire survival blueprint."),
        central_blueprint=(
            "**Vampire Survival Roguelike**\n\n"
            "Use a wave loop, enemy spawners, weapon upgrades, and run meta data."
        ),
        central_work_packages=["gameplay: Build combat loop"],
    )

    markdown = view._markdown()

    assert "### Central Agent Response" in markdown
    assert "**Vampire Survival Roguelike**" in markdown
    assert "weapon upgrades" in markdown
    assert markdown.index("### Central Agent Response") < markdown.index(
        "### Central WP Graph"
    )


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


def test_central_markdown_summarizes_execution_results() -> None:
    view = CentralAgentView()
    view.snapshot = WorkflowNexusSnapshot(
        session_id="wf-results",
        state="post_review_ready",
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
                status="blocked",
                last_result_agent="claude",
                last_result_status="blocked",
                last_result_summary="Waiting on API contract.",
                last_result_blockers=["API schema is missing."],
            ),
        ],
    )

    markdown = view._markdown()

    assert "### Execution Result Summary" in markdown
    assert "Results: `blocked=1, done=1`" in markdown
    assert "**WP-001** [done -> done] `codex`: Build API - Implemented API endpoints." in markdown
    assert "Files: src/api.py, tests/test_api.py" in markdown
    assert "**WP-002** [blocked -> blocked] `claude`: Wire UI - Waiting on API contract." in markdown
    assert "Blockers: API schema is missing." in markdown
