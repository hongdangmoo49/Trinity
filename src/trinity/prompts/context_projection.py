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
