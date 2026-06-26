from __future__ import annotations

from trinity.models import ConsensusResult, DeliberationResult
from trinity.workflow.engine import WorkflowInputAction
from trinity.workflow.models import DecisionRecord, WorkflowSession, WorkflowState
from trinity.workflow.provider_error_gate_flow import ProviderErrorGateFlow


def _session() -> WorkflowSession:
    return WorkflowSession(
        id="wf-provider-gate",
        goal="Design",
        state=WorkflowState.DELIBERATING,
        active_agents=["claude", "antigravity"],
        agent_model_overrides={"antigravity": "agy-test"},
    )


def _result(*, consensus: bool = True) -> DeliberationResult:
    return DeliberationResult(
        user_prompt="Design",
        rounds_completed=1,
        consensus=(
            ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={"claude": "Preserved plan."},
                summary="Blueprint summary.",
            )
            if consensus
            else None
        ),
        metadata={
            "provider_successful_opinions": {"claude": "Preserved plan."},
            "provider_failures": [
                {
                    "agent": "antigravity",
                    "status": "auth_required",
                    "classification": "auth_wait",
                    "reasons": ["login required"],
                    "retryable": True,
                }
            ],
        },
    )


def _decision(answer: str) -> DecisionRecord:
    return DecisionRecord(
        id="dec-provider-gate",
        question_id="q-provider-error-retry",
        decision=answer,
    )


def _flow(session: WorkflowSession):
    events: list[tuple[str, dict[str, object]]] = []
    states: list[tuple[WorkflowState, str]] = []
    marked_results: list[DeliberationResult] = []

    def persist(event: str, data: dict[str, object], **_kwargs) -> None:
        events.append((event, data))

    def set_state(state: WorkflowState, *, reason: str = "") -> None:
        session.state = state
        states.append((state, reason))

    def normalize(overrides, agents):
        overrides = dict(overrides or {})
        return {
            agent: overrides[agent]
            for agent in agents
            if agent in overrides
        }

    def mark_result(result: DeliberationResult) -> None:
        marked_results.append(result)
        session.state = WorkflowState.BLUEPRINT_READY

    return (
        ProviderErrorGateFlow(
            session=session,
            persist=persist,
            set_state=set_state,
            action_type=WorkflowInputAction,
            normalize_model_overrides=normalize,
            mark_deliberation_result=mark_result,
        ),
        events,
        states,
        marked_results,
    )


def test_provider_error_gate_flow_opens_and_retries_failed_agents() -> None:
    session = _session()
    flow, events, states, _marked_results = _flow(session)

    flow.open(_result())
    action = flow.handle_answer(
        "Retry failed providers",
        _decision("Retry failed providers"),
        replaced_decision=False,
    )

    assert session.pending_questions[0].id == "q-provider-error-retry"
    assert session.provider_error_gate["state"] == "retry_requested"
    assert action.should_deliberate is True
    assert action.target_agents == ("antigravity",)
    assert action.agent_model_overrides == {"antigravity": "agy-test"}
    assert action.agent_selection_mode == "targeted"
    assert action.provider_retry_merge_context["retry_agents"] == ["antigravity"]
    assert events[-1][0] == "provider_error_gate_resolved"
    assert events[-1][1]["action"] == "retry"
    assert states[-1] == (
        WorkflowState.DELIBERATING,
        "retrying failed provider responses",
    )


def test_provider_error_gate_flow_rejects_unavailable_continue() -> None:
    session = _session()
    flow, _events, states, marked_results = _flow(session)

    flow.open(_result(consensus=False))
    action = flow.handle_answer(
        "Continue without failed providers",
        _decision("Continue without failed providers"),
        replaced_decision=False,
    )

    assert action.should_deliberate is False
    assert action.message == "Continue is not available because no usable consensus exists."
    assert session.provider_error_gate
    assert marked_results == []
    assert states[-1] == (
        WorkflowState.NEEDS_USER_DECISION,
        "provider error gate continue is unavailable",
    )


def test_provider_error_gate_flow_stop_clears_gate() -> None:
    session = _session()
    flow, events, states, _marked_results = _flow(session)

    flow.open(_result())
    action = flow.handle_answer(
        "Stop workflow",
        _decision("Stop workflow"),
        replaced_decision=True,
    )

    assert action.should_deliberate is False
    assert action.replaced_decision is True
    assert action.message == "Workflow stopped after provider errors."
    assert session.provider_error_gate == {}
    assert events[-1][1] == {
        "action": "stop",
        "failed_agents": ["antigravity"],
    }
    assert states[-1] == (
        WorkflowState.FAILED,
        "provider error gate stopped",
    )
