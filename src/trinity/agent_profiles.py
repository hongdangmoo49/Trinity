"""Default and resolved agent operating profiles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from trinity.models import AgentProfile, Provider


PROFILE_FIELDS: tuple[str, ...] = (
    "mission",
    "summary",
    "strengths",
    "preferred_task_kinds",
    "avoid_task_kinds",
    "review_focus",
    "supported_turn_modes",
    "default_turn_mode",
    "output_contracts",
    "context_profile",
    "cost_tier",
    "latency_tier",
    "risk_tolerance",
    "routing_priority",
    "revision",
)


DEFAULT_OUTPUT_CONTRACTS: dict[str, str] = {
    "chat": "chat_v1",
    "plan": "plan_v1",
    "blueprint": "plan_v1",
    "execute": "execution_v1",
    "review": "review_v1",
    "final_review": "final_review_v1",
    "repair": "repair_v1",
    "summarize": "chat_v1",
}


def default_agent_profile(agent_name: str, provider: Provider) -> AgentProfile:
    """Return the default operating profile for an agent/provider pair."""
    name = str(agent_name or "").strip().lower()
    if name == "claude" or provider == Provider.CLAUDE_CODE:
        return _claude_profile()
    if name == "codex" or provider == Provider.CODEX:
        return _codex_profile()
    if name == "antigravity" or provider == Provider.ANTIGRAVITY_CLI:
        return _antigravity_profile()
    return _balanced_profile()


def resolve_agent_profile(
    agent_name: str,
    provider: Provider,
    override: dict[str, Any] | None = None,
) -> AgentProfile:
    """Merge config profile overrides onto the built-in default profile."""
    profile = default_agent_profile(agent_name, provider)
    data = profile.to_dict()
    for key, value in dict(override or {}).items():
        if key not in PROFILE_FIELDS:
            continue
        if key in {"strengths", "output_contracts"}:
            data[key] = _string_mapping(value, float_values=key == "strengths")
        elif key == "routing_priority":
            data[key] = _safe_int(value, data[key])
        elif key in {
            "preferred_task_kinds",
            "avoid_task_kinds",
            "review_focus",
            "supported_turn_modes",
        }:
            data[key] = _string_list(value)
        else:
            data[key] = str(value or "").strip()
    return _profile_from_dict(data)


def agent_profile_overrides(
    agent_name: str,
    provider: Provider,
    profile: AgentProfile,
) -> dict[str, Any]:
    """Return only fields that differ from the default profile."""
    base = default_agent_profile(agent_name, provider).to_dict()
    current = profile.to_dict()
    overrides: dict[str, Any] = {}
    for key in PROFILE_FIELDS:
        if current.get(key) != base.get(key):
            overrides[key] = deepcopy(current[key])
    return overrides


def _profile_from_dict(data: dict[str, Any]) -> AgentProfile:
    return AgentProfile(
        mission=str(data.get("mission", "") or ""),
        summary=str(data.get("summary", "") or ""),
        strengths=_string_mapping(data.get("strengths", {}), float_values=True),
        preferred_task_kinds=_string_list(data.get("preferred_task_kinds", [])),
        avoid_task_kinds=_string_list(data.get("avoid_task_kinds", [])),
        review_focus=_string_list(data.get("review_focus", [])),
        supported_turn_modes=_string_list(data.get("supported_turn_modes", [])),
        default_turn_mode=str(data.get("default_turn_mode", "chat") or "chat"),
        output_contracts=_string_mapping(data.get("output_contracts", {})),
        context_profile=str(data.get("context_profile", "balanced") or "balanced"),
        cost_tier=str(data.get("cost_tier", "medium") or "medium"),
        latency_tier=str(data.get("latency_tier", "medium") or "medium"),
        risk_tolerance=str(data.get("risk_tolerance", "medium") or "medium"),
        routing_priority=_safe_int(data.get("routing_priority", 100), 100),
        revision=str(data.get("revision", "default-v1") or "default-v1"),
    )


def _claude_profile() -> AgentProfile:
    return AgentProfile(
        mission="Architecture, planning, and high-level technical decisions.",
        summary=(
            "Structures ambiguous requirements, reviews design trade-offs, and "
            "keeps implementation scope coherent."
        ),
        strengths={
            "architecture": 0.95,
            "planning": 0.90,
            "review": 0.80,
            "documentation": 0.75,
            "implementation": 0.45,
            "testing": 0.55,
        },
        preferred_task_kinds=["architecture", "planning", "review", "documentation"],
        avoid_task_kinds=["large_implementation"],
        review_focus=["architecture", "compatibility", "maintainability", "scope"],
        supported_turn_modes=["chat", "plan", "blueprint", "review", "final_review"],
        default_turn_mode="plan",
        output_contracts=dict(DEFAULT_OUTPUT_CONTRACTS),
        context_profile="architect",
        cost_tier="high",
        latency_tier="medium",
        risk_tolerance="high",
        routing_priority=20,
    )


def _codex_profile() -> AgentProfile:
    return AgentProfile(
        mission="Implementation, refactoring, integration, and test automation.",
        summary=(
            "Turns agreed plans into code, keeps changes scoped, and reports "
            "verification clearly."
        ),
        strengths={
            "implementation": 0.95,
            "integration": 0.85,
            "refactor": 0.80,
            "testing": 0.80,
            "repair": 0.85,
            "review": 0.65,
            "architecture": 0.45,
            "documentation": 0.55,
        },
        preferred_task_kinds=[
            "implementation",
            "integration",
            "refactor",
            "testing",
            "repair",
        ],
        avoid_task_kinds=["architecture"],
        review_focus=["runtime_correctness", "test_coverage", "edge_cases"],
        supported_turn_modes=[
            "chat",
            "plan",
            "execute",
            "review",
            "repair",
            "summarize",
        ],
        default_turn_mode="execute",
        output_contracts=dict(DEFAULT_OUTPUT_CONTRACTS),
        context_profile="implementer",
        cost_tier="medium",
        latency_tier="fast",
        risk_tolerance="medium",
        routing_priority=10,
    )


def _antigravity_profile() -> AgentProfile:
    return AgentProfile(
        mission="Validation, alternative exploration, and quality risk discovery.",
        summary=(
            "Finds edge cases, regression risks, and practical validation gaps "
            "before work is accepted."
        ),
        strengths={
            "review": 0.95,
            "testing": 0.85,
            "research": 0.75,
            "documentation": 0.65,
            "implementation": 0.40,
            "architecture": 0.55,
        },
        preferred_task_kinds=["review", "testing", "research", "documentation"],
        avoid_task_kinds=["large_implementation"],
        review_focus=["edge_cases", "regression", "performance", "anti_patterns"],
        supported_turn_modes=["chat", "plan", "review", "final_review", "summarize"],
        default_turn_mode="review",
        output_contracts=dict(DEFAULT_OUTPUT_CONTRACTS),
        context_profile="reviewer",
        cost_tier="medium",
        latency_tier="medium",
        risk_tolerance="medium",
        routing_priority=30,
    )


def _balanced_profile() -> AgentProfile:
    return AgentProfile(
        mission="General Trinity workflow assistance.",
        summary="Handles general planning, implementation, and review work.",
        strengths={"implementation": 0.5, "planning": 0.5, "review": 0.5},
        preferred_task_kinds=[],
        avoid_task_kinds=[],
        review_focus=["correctness", "maintainability"],
        supported_turn_modes=["chat", "plan", "execute", "review", "summarize"],
        default_turn_mode="chat",
        output_contracts=dict(DEFAULT_OUTPUT_CONTRACTS),
        context_profile="balanced",
        cost_tier="medium",
        latency_tier="medium",
        risk_tolerance="medium",
        routing_priority=100,
    )


def _string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _string_mapping(value: Any, *, float_values: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key, raw in value.items():
        name = str(key).strip()
        if not name:
            continue
        if float_values:
            try:
                normalized[name] = float(raw)
            except (TypeError, ValueError):
                continue
        else:
            item = str(raw or "").strip()
            if item:
                normalized[name] = item
    return normalized


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
