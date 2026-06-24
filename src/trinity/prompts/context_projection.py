"""Prompt helpers for profile-aware shared context projection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from trinity.context.profiles import project_shared_context
from trinity.context.shared import SharedContextEngine


def agent_context_profile(
    agents: Mapping[str, Any],
    agent_name: str,
    *,
    default: str = "balanced",
) -> str:
    """Resolve the Trinity context profile for an agent-like object."""
    agent = agents.get(agent_name)
    spec = getattr(agent, "spec", None)
    profile = getattr(spec, "profile", None)
    return str(getattr(profile, "context_profile", "") or default)


def render_operating_profile_block(
    agents: Mapping[str, Any],
    agent_name: str,
    *,
    mode: str,
    heading: str = "[Operating Profile]",
) -> str:
    """Render concise Trinity-facing profile hints for a provider turn."""
    agent = agents.get(agent_name)
    spec = getattr(agent, "spec", None)
    profile = getattr(spec, "profile", None)
    context_profile = agent_context_profile(agents, agent_name)

    lines = [
        heading,
        f"Agent: {agent_name or '(unknown)'}",
        f"Turn mode: {mode}",
        f"Context profile: {context_profile}",
    ]
    if profile is None:
        lines.append("Profile source: default fallback")
        return "\n".join(lines) + "\n\n"

    mission = str(getattr(profile, "mission", "") or "").strip()
    if mission:
        lines.append(f"Mission: {mission}")
    supported_modes = [str(item) for item in getattr(profile, "supported_turn_modes", [])]
    if supported_modes:
        support = "yes" if mode in supported_modes else "fallback"
        lines.append(f"Supported modes: {', '.join(supported_modes)} ({support})")
    output_contracts = getattr(profile, "output_contracts", {}) or {}
    if isinstance(output_contracts, dict):
        output_contract = str(output_contracts.get(mode, "") or "").strip()
        if output_contract:
            lines.append(f"Output contract: {output_contract}")
    strengths = _profile_strengths(profile)
    if strengths:
        lines.append(f"Strengths: {strengths}")
    review_focus = [str(item) for item in getattr(profile, "review_focus", [])]
    if mode in {"review", "final_review"} and review_focus:
        lines.append(f"Review focus: {', '.join(review_focus[:4])}")
    return "\n".join(lines) + "\n\n"


def render_context_projection_block(
    shared: SharedContextEngine,
    profile_id: str,
    *,
    heading: str = "[Context Projection]",
) -> str:
    """Render a provider-facing shared context projection block."""
    projection = project_shared_context(shared, profile_id)
    if not projection.text:
        return (
            f"{heading}\n"
            f"Profile: {profile_id}\n"
            "Sections: none\n\n"
        )

    sections = ", ".join(projection.sections) or "none"
    truncated = "yes" if projection.truncated else "no"
    return (
        f"{heading}\n"
        f"Profile: {projection.profile_id}\n"
        f"Sections: {sections}\n"
        f"Truncated: {truncated}\n"
        f"{projection.text}\n\n"
    )


def _profile_strengths(profile: Any) -> str:
    strengths = getattr(profile, "strengths", {}) or {}
    if not isinstance(strengths, dict):
        return ""
    items: list[tuple[str, float]] = []
    for name, score in strengths.items():
        try:
            items.append((str(name), float(score)))
        except (TypeError, ValueError):
            continue
    items.sort(key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{name} {score:.2f}" for name, score in items[:3])
