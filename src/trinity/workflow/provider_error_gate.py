"""Provider error retry gate helpers for workflow deliberation results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from trinity.models import (
    ConsensusResult,
    DeliberationResult,
    TaskAssignment,
    TaskIntent,
)
from trinity.workflow.models import OpenQuestion

PROVIDER_ERROR_GATE_QUESTION_ID = "q-provider-error-retry"
PROVIDER_ERROR_RETRY_OPTION = "Retry failed providers"
PROVIDER_ERROR_CONTINUE_OPTION = "Continue without failed providers"
PROVIDER_ERROR_STOP_OPTION = "Stop workflow"


@dataclass(frozen=True)
class ProviderErrorGatePlan:
    """Pending user-choice gate created from retryable provider failures."""

    question: OpenQuestion
    gate: dict[str, Any]
    failures: list[dict[str, object]]
    failed_agents: list[str]
    can_continue: bool


def should_open_provider_error_gate(result: DeliberationResult) -> bool:
    if result.metadata.get("provider_error_gate_bypassed") is True:
        return False
    failures = retryable_provider_failures(result)
    if not failures:
        return False
    return bool(result.has_consensus or failures)


def build_provider_error_gate_plan(
    result: DeliberationResult,
    *,
    active_agents: Iterable[str],
    created_at: float,
) -> ProviderErrorGatePlan:
    failures = retryable_provider_failures(result)
    failed_agents = failure_agents(failures)
    successful_opinions = provider_successful_opinions(result)
    active_agent_count = len({str(agent).strip() for agent in active_agents if str(agent).strip()})
    can_continue = bool(
        has_provider_error_gate_preview_consensus(result)
        and usable_consensus_agent_count(result) > 0
    )
    if can_continue and len(failed_agents) >= active_agent_count:
        can_continue = False

    options = [PROVIDER_ERROR_RETRY_OPTION]
    if can_continue:
        options.append(PROVIDER_ERROR_CONTINUE_OPTION)
    options.append(PROVIDER_ERROR_STOP_OPTION)

    question = OpenQuestion(
        id=PROVIDER_ERROR_GATE_QUESTION_ID,
        question=(
            "One or more providers returned errors before central synthesis. "
            "Retry the failed providers, continue without them, or stop?"
        ),
        options=options,
        recommended_option=PROVIDER_ERROR_RETRY_OPTION,
        raised_by=failed_agents,
        rationale=provider_error_gate_rationale(failures),
        metadata={
            "kind": "provider_error_gate",
            "failed_agents": failed_agents,
            "successful_agents": list(successful_opinions.keys()),
            "can_continue": can_continue,
        },
    )
    gate = {
        "state": "waiting",
        "question_id": question.id,
        "failures": failures,
        "failed_agents": failed_agents,
        "successful_opinions": successful_opinions,
        "can_continue": can_continue,
        "result": deliberation_result_to_dict(result),
        "created_at": created_at,
    }
    return ProviderErrorGatePlan(
        question=question,
        gate=gate,
        failures=failures,
        failed_agents=failed_agents,
        can_continue=can_continue,
    )


def is_provider_error_gate_question(question: OpenQuestion) -> bool:
    return (
        question.id == PROVIDER_ERROR_GATE_QUESTION_ID
        or question.metadata.get("kind") == "provider_error_gate"
    )


def provider_error_gate_choice(answer: str) -> str:
    normalized = answer.strip().lower()
    if normalized in {"2", "continue", "continue without failed providers"}:
        return "continue"
    if normalized in {"3", "stop", "stop workflow", "abort"}:
        return "stop"
    if "continue" in normalized:
        return "continue"
    if "stop" in normalized or "abort" in normalized:
        return "stop"
    return "retry"


def provider_error_retry_prompt(gate: dict[str, Any]) -> str:
    failures = gate.get("failures", [])
    failed_agents = ", ".join(str(agent) for agent in gate.get("failed_agents", []))
    successful_agents = ", ".join(
        str(agent) for agent in gate.get("successful_opinions", {})
    )
    reason_lines = []
    if isinstance(failures, list):
        for failure in failures:
            if not isinstance(failure, dict):
                continue
            agent = str(failure.get("agent", "") or "provider")
            status = str(failure.get("status", "") or "unknown")
            reason_lines.append(f"- {agent}: {status}")
    result = gate.get("result", {}) if isinstance(gate.get("result", {}), dict) else {}
    original_prompt = str(result.get("user_prompt", "") or "the previous request")
    return (
        "Retry the failed provider response for the previous Trinity request.\n\n"
        f"Failed providers: {failed_agents or '(unknown)'}\n"
        f"Previously successful providers preserved by Trinity: "
        f"{successful_agents or '(none)'}\n"
        + "\n".join(reason_lines)
        + "\n\nOriginal request:\n"
        + original_prompt
    )


def provider_error_retry_context(gate: dict[str, Any]) -> dict[str, Any]:
    successful = gate.get("successful_opinions", {})
    result = gate.get("result", {}) if isinstance(gate.get("result", {}), dict) else {}
    return {
        "successful_opinions": (
            {
                str(agent).strip(): str(opinion)
                for agent, opinion in successful.items()
                if str(agent).strip() and str(opinion).strip()
            }
            if isinstance(successful, dict)
            else {}
        ),
        "retry_agents": [
            str(agent).strip()
            for agent in gate.get("failed_agents", [])
            if str(agent).strip()
        ],
        "original_prompt": str(
            result.get("user_prompt")
            or gate.get("original_prompt")
            or ""
        ),
        "source_question_id": str(gate.get("question_id", "")),
    }


def retryable_provider_failures(result: DeliberationResult) -> list[dict[str, object]]:
    failures = result.metadata.get("provider_failures", [])
    if not isinstance(failures, list):
        return []
    return [
        dict(item)
        for item in failures
        if isinstance(item, dict) and bool(item.get("retryable", False))
    ]


def provider_successful_opinions(result: DeliberationResult) -> dict[str, str]:
    opinions = result.metadata.get("provider_successful_opinions", {})
    if isinstance(opinions, dict):
        normalized = {
            str(agent).strip(): str(opinion)
            for agent, opinion in opinions.items()
            if str(agent).strip() and str(opinion).strip()
        }
        if normalized:
            return normalized
    if result.consensus is None:
        return {}
    return {
        str(agent).strip(): str(opinion)
        for agent, opinion in result.consensus.opinions.items()
        if str(agent).strip() and str(opinion).strip()
    }


def failure_agents(failures: list[dict[str, object]]) -> list[str]:
    seen: set[str] = set()
    agents: list[str] = []
    for failure in failures:
        agent = str(failure.get("agent", "") or "").strip()
        if agent and agent not in seen:
            agents.append(agent)
            seen.add(agent)
    return agents


def usable_consensus_agent_count(result: DeliberationResult) -> int:
    if result.consensus is None:
        return 0
    return len(result.consensus.opinions)


def has_provider_error_gate_preview_consensus(result: DeliberationResult) -> bool:
    return result.consensus is not None and result.consensus.reached


def provider_error_gate_rationale(failures: list[dict[str, object]]) -> str:
    lines = []
    for failure in failures:
        agent = str(failure.get("agent", "") or "provider")
        status = str(failure.get("status", "") or "unknown")
        classification = str(failure.get("classification", "") or status)
        lines.append(f"{agent}: {status} ({classification})")
    return "; ".join(lines)


def deliberation_result_to_dict(result: DeliberationResult) -> dict[str, Any]:
    consensus = None
    if result.consensus is not None:
        consensus = {
            "reached": result.consensus.reached,
            "agreement_count": result.consensus.agreement_count,
            "total_agents": result.consensus.total_agents,
            "opinions": dict(result.consensus.opinions),
            "summary": result.consensus.summary,
        }
    return {
        "user_prompt": result.user_prompt,
        "rounds_completed": result.rounds_completed,
        "consensus": consensus,
        "tasks": [
            {
                "agent_name": task.agent_name,
                "task_description": task.task_description,
                "priority": task.priority,
                "intent": task.intent.value,
                "requires_execution": task.requires_execution,
            }
            for task in result.tasks
        ],
        "total_tokens_used": result.total_tokens_used,
        "duration_seconds": result.duration_seconds,
        "metadata": dict(result.metadata),
    }


def deliberation_result_from_dict(data: dict[str, Any]) -> DeliberationResult:
    consensus_data = data.get("consensus", {})
    consensus = None
    if isinstance(consensus_data, dict):
        opinions = consensus_data.get("opinions", {})
        consensus = ConsensusResult(
            reached=bool(consensus_data.get("reached", False)),
            agreement_count=int(consensus_data.get("agreement_count", 0)),
            total_agents=int(consensus_data.get("total_agents", 0)),
            opinions={
                str(key): str(value)
                for key, value in (
                    opinions.items() if isinstance(opinions, dict) else []
                )
            },
            summary=str(consensus_data.get("summary", "")),
        )
    tasks: list[TaskAssignment] = []
    tasks_data = data.get("tasks", [])
    for item in tasks_data if isinstance(tasks_data, list) else []:
        if not isinstance(item, dict):
            continue
        intent_value = str(item.get("intent", TaskIntent.PLAN.value))
        try:
            intent = TaskIntent(intent_value)
        except ValueError:
            intent = TaskIntent.PLAN
        tasks.append(
            TaskAssignment(
                agent_name=str(item.get("agent_name", "")),
                task_description=str(item.get("task_description", "")),
                priority=int(item.get("priority", 0)),
                intent=intent,
                requires_execution=bool(item.get("requires_execution", False)),
            )
        )
    metadata = data.get("metadata", {})
    return DeliberationResult(
        user_prompt=str(data.get("user_prompt", "")),
        rounds_completed=int(data.get("rounds_completed", 0)),
        consensus=consensus,
        tasks=tasks,
        total_tokens_used=int(data.get("total_tokens_used", 0)),
        duration_seconds=float(data.get("duration_seconds", 0.0)),
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )
