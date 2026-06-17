"""Profile-based task routing helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from trinity.models import AgentSpec, Provider


TASK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "architecture": (
        "architecture",
        "architect",
        "design",
        "model",
        "strategy",
        "planning",
        "failure",
        "설계",
        "아키텍처",
    ),
    "implementation": (
        "code",
        "component",
        "feature",
        "implementation",
        "implement",
        "service",
        "route",
        "ui",
        "구현",
        "기능",
    ),
    "integration": (
        "adapter",
        "api",
        "bridge",
        "dependency",
        "external",
        "integrate",
        "integration",
        "provider",
        "연동",
        "통합",
    ),
    "testing": (
        "edge",
        "quality",
        "regression",
        "reliability",
        "risk",
        "test",
        "validation",
        "검증",
        "테스트",
        "위험",
    ),
    "documentation": ("document", "docs", "readme", "guide", "문서"),
    "review": ("review", "audit", "검토", "리뷰"),
    "repair": ("repair", "fix", "retry", "복구", "수정"),
    "research": ("research", "alternative", "explore", "조사", "대안"),
    "release": ("release", "version", "changelog", "pr", "merge"),
}


@dataclass(frozen=True)
class ClassifiedTask:
    """A normalized task description used for agent scoring."""

    kind: str
    turn_mode: str = "execute"
    risk: str = "medium"
    expected_files: tuple[str, ...] = ()
    requires_write: bool = True
    confidence: float = 1.0


@dataclass(frozen=True)
class RoutingDecision:
    """Selected agent and diagnostic score for one routed task."""

    agent_name: str
    score: float
    task_kind: str
    turn_mode: str
    reason: str
    profile_revision: str


class ProfileRouter:
    """Deterministic profile-based agent selector."""

    def classify_text(
        self,
        text: str,
        *,
        turn_mode: str = "execute",
        risk: str = "medium",
        expected_files: Iterable[str] = (),
        requires_write: bool = True,
        fallback_kind: str = "implementation",
    ) -> ClassifiedTask:
        """Classify free text into the strongest known task kind."""
        normalized = str(text or "").lower()
        best_kind = fallback_kind
        best_hits = 0
        for kind, keywords in TASK_KEYWORDS.items():
            hits = sum(1 for keyword in keywords if keyword in normalized)
            if hits > best_hits:
                best_kind = kind
                best_hits = hits
        confidence = min(1.0, 0.25 + (best_hits * 0.25)) if best_hits else 0.25
        return ClassifiedTask(
            kind=best_kind,
            turn_mode=turn_mode,
            risk=risk,
            expected_files=tuple(str(item) for item in expected_files),
            requires_write=requires_write,
            confidence=confidence,
        )

    def select_agent(
        self,
        agents: Mapping[str, AgentSpec],
        task: ClassifiedTask,
        *,
        exclude: Iterable[str] = (),
    ) -> RoutingDecision | None:
        """Select the best candidate for a classified task."""
        excluded = {str(name).strip() for name in exclude if str(name).strip()}
        candidates = {
            name: spec
            for name, spec in agents.items()
            if name and name not in excluded and spec.enabled
        }
        if not candidates:
            return None

        ranked = sorted(
            (
                self.score_agent(name, spec, task)
                for name, spec in candidates.items()
            ),
            key=lambda decision: (
                -decision.score,
                self._priority(candidates[decision.agent_name]),
                decision.agent_name,
            ),
        )
        return ranked[0]

    def score_agent(
        self,
        agent_name: str,
        spec: AgentSpec,
        task: ClassifiedTask,
    ) -> RoutingDecision:
        """Score one agent for one task."""
        profile = spec.profile
        strength = float(profile.strengths.get(task.kind, 0.0) or 0.0)
        score = strength * 100.0
        reasons = [f"{task.kind} strength {strength:.2f}"]

        if task.kind in profile.preferred_task_kinds:
            score += 12.0
            reasons.append("preferred task kind")
        if task.kind in profile.avoid_task_kinds:
            score -= 40.0
            reasons.append("avoid task kind")
        if task.turn_mode and task.turn_mode not in profile.supported_turn_modes:
            score -= 30.0
            reasons.append(f"mode {task.turn_mode} not preferred")
        if task.risk.lower() in {"high", "critical"} and profile.risk_tolerance == "high":
            score += 8.0
            reasons.append("high risk tolerance")
        if task.requires_write and "execute" not in profile.supported_turn_modes:
            score -= 20.0
            reasons.append("read-focused profile")

        latency_bonus = {"fast": 4.0, "medium": 0.0, "slow": -4.0}.get(
            profile.latency_tier,
            0.0,
        )
        if latency_bonus:
            score += latency_bonus
            reasons.append(f"{profile.latency_tier} latency")

        return RoutingDecision(
            agent_name=agent_name,
            score=round(score, 3),
            task_kind=task.kind,
            turn_mode=task.turn_mode,
            reason=", ".join(reasons),
            profile_revision=profile.revision,
        )

    @staticmethod
    def specs_from_active_agents(
        active_agents: Iterable[str] | Mapping[str, AgentSpec],
    ) -> dict[str, AgentSpec]:
        """Normalize active agent names or specs into AgentSpec mappings."""
        if isinstance(active_agents, Mapping):
            return {
                str(name): spec
                for name, spec in active_agents.items()
                if str(name).strip()
            }
        specs: dict[str, AgentSpec] = {}
        for raw in active_agents:
            name = str(raw).strip()
            if not name:
                continue
            specs[name] = AgentSpec(
                name=name,
                provider=_provider_for_name(name),
                cli_command=name,
            )
        return specs

    @staticmethod
    def _priority(spec: AgentSpec) -> int:
        return int(spec.profile.routing_priority or 100)


def _provider_for_name(agent_name: str) -> Provider:
    normalized = str(agent_name or "").strip().lower()
    if normalized == "codex":
        return Provider.CODEX
    if normalized == "antigravity":
        return Provider.ANTIGRAVITY_CLI
    return Provider.CLAUDE_CODE

