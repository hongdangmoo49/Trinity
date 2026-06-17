"""Role-aware shared-context projection profiles."""

from __future__ import annotations

from dataclasses import dataclass

from trinity.context.shared import SharedContextEngine


@dataclass(frozen=True)
class ContextProfile:
    """Shared-context selection policy for one agent turn."""

    id: str
    include_sections: tuple[str, ...]
    max_chars: int = 12_000


@dataclass(frozen=True)
class ContextProjection:
    """Rendered context projection metadata."""

    profile_id: str
    sections: tuple[str, ...]
    text: str
    truncated: bool = False


CONTEXT_PROFILES: dict[str, ContextProfile] = {
    "architect": ContextProfile(
        id="architect",
        include_sections=(
            "Current Goal",
            "Agreed Conclusion",
            "Task Assignment",
            "Session History",
        ),
    ),
    "implementer": ContextProfile(
        id="implementer",
        include_sections=(
            "Agreed Conclusion",
            "Task Assignment",
            "Task Results",
            "Subtasks",
        ),
    ),
    "reviewer": ContextProfile(
        id="reviewer",
        include_sections=(
            "Agreed Conclusion",
            "Task Results",
            "Subtasks",
            "Response Diagnostics",
        ),
    ),
    "balanced": ContextProfile(
        id="balanced",
        include_sections=(
            "Current Goal",
            "Agreed Conclusion",
            "Task Assignment",
            "Task Results",
        ),
    ),
}


def project_shared_context(
    shared: SharedContextEngine,
    profile_id: str,
) -> ContextProjection:
    """Render a compact shared context projection for a profile id."""
    profile = CONTEXT_PROFILES.get(profile_id) or CONTEXT_PROFILES["balanced"]
    chunks: list[str] = []
    included: list[str] = []
    for section in profile.include_sections:
        content = shared.read_section(section)
        if not content or not content.strip():
            continue
        chunks.append(f"## {section}\n{content.strip()}")
        included.append(section)
    text = "\n\n".join(chunks).strip()
    truncated = False
    if profile.max_chars > 0 and len(text) > profile.max_chars:
        text = text[: profile.max_chars].rstrip()
        truncated = True
    return ContextProjection(
        profile_id=profile.id,
        sections=tuple(included),
        text=text,
        truncated=truncated,
    )

