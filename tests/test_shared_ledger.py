"""Tests for the shared workflow ledger markdown renderer."""

from pathlib import Path

from trinity.models import Provider
from trinity.providers.readiness import ProviderState, ReadinessResult
from trinity.workflow.ledger import SharedLedgerRenderer, render_shared_ledger
from trinity.workflow.models import (
    DecisionRecord,
    ExecutionResult,
    OpenQuestion,
    SubtaskResult,
    WorkPackage,
    WorkStatus,
    WorkflowSession,
    WorkflowState,
)
from trinity.workflow.structured import ArchitectureComponent, Blueprint, RiskItem


def test_shared_ledger_renders_workflow_state_and_provider_readiness():
    session = WorkflowSession(
        id="session-001",
        goal="Implement provider readiness ledger",
        state=WorkflowState.EXECUTING,
        active_agents=["codex", "gemini"],
        current_round=3,
    )
    readiness = {
        "codex": ReadinessResult(
            agent_name="codex",
            provider=Provider.CODEX,
            ready=True,
            state=ProviderState.READY,
            reason="input prompt detected",
            action_hint="",
            excerpt="Codex\n>",
        ),
        "gemini": {
            "provider": Provider.GEMINI_CLI,
            "ready": False,
            "state": ProviderState.AUTH_REQUIRED,
            "reason": "authentication required",
            "action_hint": "Run `gemini` and complete the authentication flow.",
        },
    }

    markdown = SharedLedgerRenderer().render(session, readiness)

    assert markdown.startswith("# Shared Context\n")
    assert "## Current Goal\nImplement provider readiness ledger\n" in markdown
    assert "## Workflow State" in markdown
    assert "- id: session-001" in markdown
    assert "- state: executing" in markdown
    assert "- current_round: 3" in markdown
    assert "- active_agents: codex, gemini" in markdown
    assert "## Provider Readiness" in markdown
    assert "### codex" in markdown
    assert "- provider: codex" in markdown
    assert "- ready: yes" in markdown
    assert "- state: ready" in markdown
    assert "```text\nCodex\n>\n```" in markdown
    assert "### gemini" in markdown
    assert "- provider: gemini-cli" in markdown
    assert "- ready: no" in markdown
    assert "- state: auth_required" in markdown
    assert "complete the authentication flow" in markdown


def test_shared_ledger_renders_structured_workflow_artifacts():
    decision = DecisionRecord(
        id="DEC-001",
        question_id="Q-001",
        decided_by="user",
        decision="Optimize for readiness clarity before orchestration wiring.",
        rationale="The shared document should be readable before it becomes a source hook.",
        timestamp=0,
    )
    subtask = SubtaskResult(
        id="ST-001",
        parent_package_id="WP-001",
        parent_agent="codex",
        delegated_to="code-search",
        objective="Find existing shared.md sections.",
        result_summary="Found Task Results and Subtasks appenders.",
        status=WorkStatus.DONE,
        decisions_made=["Reuse existing section names"],
        files_changed=["src/trinity/context/shared.py"],
        unresolved_issues=["Wire renderer into persistence later"],
    )
    blueprint = Blueprint(
        title="Shared Ledger Renderer",
        summary="Render structured workflow state into human-readable shared.md.",
        architecture=[
            ArchitectureComponent(
                name="SharedLedgerRenderer",
                responsibility="Convert session state into markdown sections.",
                owner_agent="codex",
                dependencies=["WorkflowSession"],
            )
        ],
        data_flow=["session.json -> renderer -> shared.md"],
        external_dependencies=["none"],
        risks=[
            RiskItem(
                description="Markdown is readable but not the source of truth.",
                severity="low",
                mitigation="Keep session.json as canonical state.",
                owner_agent="codex",
            )
        ],
        acceptance_criteria=["All required v0.7.0 sections render."],
        open_questions=[
            OpenQuestion(
                id="Q-BP-001",
                question="Should shared.md be overwritten or patched?",
                status="open",
            )
        ],
    )
    session = WorkflowSession(
        id="session-002",
        goal="Build the shared ledger",
        state=WorkflowState.REVIEWING,
        active_agents=["codex"],
        pending_questions=[
            OpenQuestion(
                id="Q-001",
                question="Should renderer be pure?",
                options=["pure", "mutating"],
                recommended_option="pure",
                blocking=True,
                raised_by=["codex"],
                rationale="Pure rendering keeps persistence separate.",
            )
        ],
        blueprint=blueprint.to_dict(),
        work_packages=[
            WorkPackage(
                id="WP-001",
                title="Ledger markdown slice",
                owner_agent="codex",
                objective="Render workflow artifacts into shared markdown.",
                scope=["ledger renderer", "unit tests"],
                out_of_scope=["protocol integration"],
                dependencies=["session model"],
                expected_files=["src/trinity/workflow/ledger.py"],
                acceptance_criteria=["renders work packages", "renders task results"],
                status=WorkStatus.DONE,
            )
        ],
        execution_results=[
            ExecutionResult(
                package_id="WP-001",
                agent_name="codex",
                status=WorkStatus.DONE,
                summary="Implemented renderer and tests.",
                files_changed=["src/trinity/workflow/ledger.py", "tests/test_shared_ledger.py"],
                decisions_made=[decision],
                blockers=["none"],
                follow_up=["Connect renderer to shared.md writer in a later slice."],
                subtasks=[subtask],
                raw_response_path=Path(".trinity/logs/provider/codex/result.raw.txt"),
            )
        ],
        decisions=[decision],
    )

    markdown = render_shared_ledger(session)

    assert_in_order(
        markdown,
        [
            "## Workflow State",
            "## Provider Readiness",
            "## Decisions",
            "## Open Questions",
            "## Blueprint",
            "## Work Packages",
            "## Task Results",
            "## Subtasks",
        ],
    )
    assert "### DEC-001" in markdown
    assert "- question_id: Q-001" in markdown
    assert "- timestamp: 1970-01-01T00:00:00+00:00" in markdown
    assert "### Q-001" in markdown
    assert "- options: pure, mutating" in markdown
    assert "### Shared Ledger Renderer" in markdown
    assert "- SharedLedgerRenderer: Convert session state into markdown sections." in markdown
    assert "- session.json -> renderer -> shared.md" in markdown
    assert "- low: Markdown is readable but not the source of truth." in markdown
    assert "### WP-001: Ledger markdown slice" in markdown
    assert "- owner: codex" in markdown
    assert "- acceptance:\n  - renders work packages\n  - renders task results" in markdown
    assert "### WP-001 / codex" in markdown
    assert "- raw_response_path: `.trinity/logs/provider/codex/result.raw.txt`" in markdown
    assert "  - DEC-001: Optimize for readiness clarity before orchestration wiring." in markdown
    assert "### ST-001 / WP-001" in markdown
    assert "- delegated_to: code-search" in markdown
    assert "- unresolved_issues:\n  - Wire renderer into persistence later" in markdown


def test_shared_ledger_empty_sections_are_explicit():
    session = WorkflowSession(
        id="session-empty",
        goal="",
        state=WorkflowState.IDLE,
    )

    markdown = SharedLedgerRenderer().render(session)

    assert "## Current Goal\n(none)\n" in markdown
    assert "## Provider Readiness\n(none)\n" in markdown
    assert "## Decisions\n(none)\n" in markdown
    assert "## Open Questions\n(none)\n" in markdown
    assert "## Blueprint\n(none)\n" in markdown
    assert "## Work Packages\n(none)\n" in markdown
    assert "## Task Results\n(none)\n" in markdown
    assert "## Subtasks\n(none)\n" in markdown
    assert markdown.endswith("\n")


def test_workflow_public_api_exports_shared_ledger_renderer():
    from trinity.workflow import SharedLedgerRenderer as ExportedRenderer
    from trinity.workflow import render_shared_ledger as exported_render

    session = WorkflowSession(
        id="session-export",
        goal="Render",
        state=WorkflowState.IDLE,
    )

    assert ExportedRenderer is SharedLedgerRenderer
    assert exported_render(session).startswith("# Shared Context\n")


def assert_in_order(text: str, expected: list[str]) -> None:
    positions = [text.index(item) for item in expected]
    assert positions == sorted(positions)
