"""Tests for deliberation report builder and renderer."""

import time

from trinity.models import ConsensusResult, DeliberationResult
from trinity.tui.report import DeliberationReportBuilder, DeliberationReport
from trinity.workflow.models import (
    ArchitectureComponent,
    Blueprint,
    DecisionRecord,
    ExecutionResult,
    RiskItem,
    WorkPackage,
    WorkflowSession,
    WorkflowState,
    WorkStatus,
)


def _sample_session() -> WorkflowSession:
    return WorkflowSession(
        id="test-session-001",
        goal="인증 시스템 설계",
        state=WorkflowState.BLUEPRINT_READY,
        active_agents=["claude", "codex", "antigravity"],
        current_round=3,
        blueprint=Blueprint(
            title="JWT 인증 시스템",
            summary="JWT 기반 인증 설계",
            architecture=[
                ArchitectureComponent(
                    name="AuthController",
                    responsibility="인증 요청 처리",
                    owner_agent="codex",
                ),
            ],
            data_flow=["Client → AuthController → TokenService"],
            risks=[
                RiskItem(
                    description="토큰 만료 처리 누락",
                    severity="high",
                    mitigation="자동 갱신 로직 추가",
                ),
            ],
            acceptance_criteria=["로그인/로그아웃 동작"],
        ),
        work_packages=[
            WorkPackage(
                id="wp-001",
                title="인증 컨트롤러 구현",
                owner_agent="codex",
                objective="JWT 인증 컨트롤러 및 미들웨어 구현",
                status=WorkStatus.DONE,
            ),
        ],
        execution_results=[
            ExecutionResult(
                package_id="wp-001",
                agent_name="codex",
                status=WorkStatus.DONE,
                summary="인증 컨트롤러 구현 완료",
                files_changed=["src/auth/controller.py", "src/auth/middleware.py"],
            ),
        ],
        decisions=[
            DecisionRecord(
                id="dec-001",
                decision="JWT 사용",
                decided_by="user",
            ),
        ],
        created_at=time.time(),
    )


def _sample_result() -> DeliberationResult:
    return DeliberationResult(
        user_prompt="인증 시스템 설계",
        rounds_completed=3,
        consensus=ConsensusResult(
            reached=True,
            agreement_count=3,
            total_agents=3,
            opinions={
                "claude": "approve",
                "codex": "approve",
                "antigravity": "approve",
            },
            summary="JWT 기반 인증 시스템 설계에 합의",
        ),
        total_tokens_used=15000,
        duration_seconds=45.3,
    )


def test_report_builds_from_session_and_result():
    session = _sample_session()
    result = _sample_result()
    report = DeliberationReportBuilder(session, result).build()

    assert report.meta.session_id == "test-session-001"
    assert report.meta.goal == "인증 시스템 설계"
    assert report.meta.rounds == 3
    assert report.meta.tokens == "15,000"
    assert len(report.meta.agents) == 3


def test_report_consensus():
    report = DeliberationReportBuilder(
        _sample_session(), _sample_result(),
    ).build()

    assert report.consensus is not None
    assert report.consensus.reached is True
    assert report.consensus.agreement_ratio == "3/3"


def test_report_consensus_not_reached():
    result = DeliberationResult(
        user_prompt="test",
        rounds_completed=2,
        consensus=ConsensusResult(
            reached=False,
            agreement_count=1,
            total_agents=3,
            opinions={},
            summary="No agreement",
        ),
        total_tokens_used=5000,
        duration_seconds=20.0,
    )
    session = WorkflowSession(
        id="no-consensus",
        goal="test",
        state=WorkflowState.DELIBERATING,
    )
    report = DeliberationReportBuilder(session, result).build()
    assert report.consensus is not None
    assert report.consensus.reached is False
    assert report.consensus.agreement_ratio == "1/3"


def test_report_blueprint():
    report = DeliberationReportBuilder(
        _sample_session(), _sample_result(),
    ).build()

    assert report.blueprint is not None
    assert report.blueprint.title == "JWT 인증 시스템"
    assert report.blueprint.architecture_count == 1
    assert report.blueprint.risk_count == 1
    assert report.blueprint.data_flow_count == 1
    assert report.blueprint.acceptance_criteria_count == 1


def test_report_packages():
    report = DeliberationReportBuilder(
        _sample_session(), _sample_result(),
    ).build()

    assert len(report.packages) == 1
    assert report.packages[0].id == "wp-001"
    assert report.packages[0].owner_agent == "codex"
    assert report.packages[0].status == "done"


def test_report_executions():
    report = DeliberationReportBuilder(
        _sample_session(), _sample_result(),
    ).build()

    assert len(report.executions) == 1
    assert report.executions[0].files_count == 2
    assert report.executions[0].status == "done"


def test_report_decisions():
    report = DeliberationReportBuilder(
        _sample_session(), _sample_result(),
    ).build()

    assert len(report.decisions) == 1
    assert report.decisions[0].decision == "JWT 사용"
    assert report.decisions[0].decided_by == "user"


def test_report_render_does_not_raise():
    report = DeliberationReportBuilder(
        _sample_session(), _sample_result(),
    ).build()
    group = report.render()
    assert group is not None


def test_report_to_markdown():
    report = DeliberationReportBuilder(
        _sample_session(), _sample_result(),
    ).build()
    md = report.to_markdown()

    assert "# Deliberation Report" in md
    assert "인증 시스템 설계" in md
    assert "JWT 인증 시스템" in md
    assert "Consensus reached" in md
    assert "wp-001" in md
    assert "dec-001" in md


def test_report_without_result():
    session = _sample_session()
    report = DeliberationReportBuilder(session, result=None).build()

    assert report.meta.tokens == "N/A"
    assert report.meta.duration == "N/A"
    assert report.meta.rounds == 3  # falls back to session.current_round
    assert report.consensus is None


def test_report_empty_session():
    session = WorkflowSession(
        id="empty-session",
        goal="",
        state=WorkflowState.IDLE,
    )
    report = DeliberationReportBuilder(session, result=None).build()

    assert report.meta.goal == "(none)"
    assert report.consensus is None
    assert report.blueprint is None
    assert report.packages == ()
    assert report.executions == ()
    assert report.decisions == ()


def test_report_frozen():
    report = DeliberationReportBuilder(
        _sample_session(), _sample_result(),
    ).build()
    # Frozen dataclass should raise on attribute assignment
    try:
        report.meta.session_id = "changed"
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_long_objective_in_markdown():
    session = WorkflowSession(
        id="trunc-session",
        goal="test",
        state=WorkflowState.BLUEPRINT_READY,
        work_packages=[
            WorkPackage(
                id="wp-long",
                title="Long",
                owner_agent="codex",
                objective="x" * 200,
                status=WorkStatus.PENDING,
            ),
        ],
    )
    report = DeliberationReportBuilder(session, result=None).build()
    md = report.to_markdown()
    # 200 chars → truncated to 120 chars in the table, so the full
    # 200-char run must not survive intact (no line with >120 x's).
    for line in md.splitlines():
        x_run = line.replace("x", "")
        assert len(x_run) <= 120 + 10  # table formatting adds a few chars
    assert "wp-long" in md
    assert "codex" in md
