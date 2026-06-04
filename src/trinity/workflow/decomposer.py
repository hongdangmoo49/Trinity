"""Blueprint decomposition into agent-owned work packages."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal
from typing import Any

from trinity.workflow.models import Blueprint, WorkPackage, WorkStatus


BlueprintFollowupAction = Literal["execute", "continue", "new", "cancel"]


@dataclass(frozen=True)
class _PackageSeed:
    """Intermediate deliverable before it is assigned to a provider."""

    key: str
    title: str
    objective: str
    scope: list[str]
    kind: str
    dependency_keys: list[str] = field(default_factory=list)
    estimated_weight: int = 1


class BlueprintDecomposer:
    """Create top-level work packages from a finalized blueprint."""

    PROVIDER_PRIORITY: tuple[str, ...] = ("codex", "claude", "antigravity", "gemini")

    AGENT_FOCUS: dict[str, tuple[str, tuple[str, ...]]] = {
        "codex": (
            "implementation and integration",
            (
                "adapter",
                "api",
                "code",
                "data",
                "graph",
                "implementation",
                "integrate",
                "route",
                "service",
                "search",
            ),
        ),
        "claude": (
            "architecture and planning",
            (
                "architecture",
                "design",
                "strategy",
                "model",
                "scoring",
                "planning",
                "failure",
            ),
        ),
        "antigravity": (
            "validation and exploration",
            (
                "edge",
                "external",
                "quality",
                "reliability",
                "research",
                "review",
                "risk",
                "test",
                "validation",
            ),
        ),
        "gemini": (
            "validation and exploration",
            (
                "edge",
                "external",
                "quality",
                "reliability",
                "research",
                "review",
                "risk",
                "test",
                "validation",
            ),
        ),
    }

    DEFAULT_FOCUS = ("general delivery", ("component", "delivery", "workflow"))

    def decompose(
        self,
        blueprint: Blueprint | dict[str, Any],
        active_agents: Iterable[str],
        *,
        requires_execution: bool = True,
    ) -> list[WorkPackage]:
        """Return deliverable-oriented packages assigned across active providers."""
        agent_names = self._normalize_agents(active_agents)
        if not agent_names:
            return []

        normalized = (
            Blueprint.from_dict(blueprint) if isinstance(blueprint, dict) else blueprint
        )
        seeds = self._package_seeds(normalized)
        criteria = normalized.acceptance_criteria or [
            f"Deliver package output aligned with {normalized.title}.",
        ]
        owners_by_seed = self._assign_owners(agent_names, seeds)

        packages: list[WorkPackage] = []
        seed_to_package_id: dict[str, str] = {}
        for index, seed in enumerate(seeds, start=1):
            package_id = f"WP-{index:03d}"
            seed_to_package_id[seed.key] = package_id
            agent_name = owners_by_seed[seed.key]
            focus_label, _ = self.AGENT_FOCUS.get(agent_name, self.DEFAULT_FOCUS)
            packages.append(
                WorkPackage(
                    id=package_id,
                    title=seed.title,
                    owner_agent=agent_name,
                    objective=self._objective_for(seed, agent_name, focus_label),
                    scope=list(seed.scope),
                    out_of_scope=self._out_of_scope_for(agent_name, requires_execution),
                    expected_files=self._expected_files_for(
                        seed.kind,
                        requires_execution,
                    ),
                    acceptance_criteria=list(criteria),
                    status=WorkStatus.PENDING,
                    requires_execution=requires_execution,
                    estimated_weight=seed.estimated_weight,
                )
            )
        for package, seed in zip(packages, seeds):
            package.dependencies = [
                seed_to_package_id[key]
                for key in seed.dependency_keys
                if key in seed_to_package_id and seed_to_package_id[key] != package.id
            ]
        return packages

    def _normalize_agents(self, active_agents: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        agent_names: list[str] = []
        for name in active_agents:
            normalized = str(name).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            agent_names.append(normalized)
        return agent_names

    def _assign_owners(
        self,
        agent_names: list[str],
        seeds: list[_PackageSeed],
    ) -> dict[str, str]:
        """Assign packages by load balance first, provider priority as tie-break."""
        loads = {agent_name: 0 for agent_name in agent_names}
        assignments: dict[str, str] = {}
        for seed in sorted(seeds, key=lambda item: item.estimated_weight, reverse=True):
            scores = {
                agent_name: self._agent_fit_score(seed, agent_name)
                for agent_name in agent_names
            }
            owner = min(
                agent_names,
                key=lambda agent_name: (
                    loads[agent_name],
                    -scores[agent_name],
                    self._priority_index(agent_name),
                    agent_names.index(agent_name),
                ),
            )
            assignments[seed.key] = owner
            loads[owner] += seed.estimated_weight
        return assignments

    def _agent_fit_score(self, seed: _PackageSeed, agent_name: str) -> int:
        normalized = " ".join([seed.title, seed.objective, *seed.scope]).lower()
        _, keywords = self.AGENT_FOCUS.get(agent_name, self.DEFAULT_FOCUS)
        score = sum(1 for keyword in keywords if keyword in normalized)
        if agent_name == "codex" and seed.kind in {"component", "integration", "dependency"}:
            score += 2
        if agent_name == "claude" and seed.kind in {"component", "planning"}:
            score += 1
        if agent_name in {"antigravity", "gemini"} and seed.kind == "validation":
            score += 2
        return score

    def _priority_index(self, agent_name: str) -> int:
        try:
            return self.PROVIDER_PRIORITY.index(agent_name)
        except ValueError:
            return len(self.PROVIDER_PRIORITY)

    def _package_seeds(self, blueprint: Blueprint) -> list[_PackageSeed]:
        seeds: list[_PackageSeed] = []
        known_keys: set[str] = set()
        for index, component in enumerate(blueprint.architecture, start=1):
            title = component.name.strip() or f"Architecture Component {index}"
            scope_item = f"{title}: {component.responsibility}".strip()
            key = self._seed_key(title, known_keys)
            seeds.append(
                _PackageSeed(
                    key=key,
                    title=title,
                    objective=(
                        component.responsibility
                        or f"Deliver the {title} component."
                    ),
                    scope=[scope_item] if scope_item and scope_item != ":" else [title],
                    kind="component",
                    dependency_keys=[
                        self._normalize_key(dependency)
                        for dependency in component.dependencies
                    ],
                    estimated_weight=self._estimate_weight(
                        title,
                        component.responsibility,
                    ),
                )
            )

        if blueprint.data_flow:
            seeds.append(
                _PackageSeed(
                    key=self._seed_key("data-flow", known_keys),
                    title="Data flow and integration",
                    objective="Implement the approved end-to-end data flow.",
                    scope=[f"Data flow: {item}" for item in blueprint.data_flow],
                    kind="integration",
                    estimated_weight=max(1, len(blueprint.data_flow)),
                )
            )

        if blueprint.external_dependencies:
            seeds.append(
                _PackageSeed(
                    key=self._seed_key("external-dependencies", known_keys),
                    title="External dependency adapters",
                    objective="Integrate and guard the approved external dependencies.",
                    scope=[
                        f"External dependency: {item}"
                        for item in blueprint.external_dependencies
                    ],
                    kind="dependency",
                    estimated_weight=max(1, len(blueprint.external_dependencies)),
                )
            )

        if blueprint.risks:
            seeds.append(
                _PackageSeed(
                    key=self._seed_key("risk-validation", known_keys),
                    title="Risk and validation coverage",
                    objective="Cover the blueprint risks with tests, checks, or docs.",
                    scope=[f"Risk: {risk.description}" for risk in blueprint.risks],
                    kind="validation",
                    estimated_weight=max(1, len(blueprint.risks)),
                )
            )

        if not seeds:
            title = blueprint.title or "Blueprint delivery"
            seeds.append(
                _PackageSeed(
                    key=self._seed_key(title, known_keys),
                    title=title,
                    objective=blueprint.summary or f"Deliver {title}.",
                    scope=[blueprint.summary or f"Finalize {title}."],
                    kind="planning",
                    estimated_weight=1,
                )
            )
        return seeds

    def _seed_key(self, value: str, known_keys: set[str]) -> str:
        base = self._normalize_key(value) or "package"
        candidate = base
        index = 2
        while candidate in known_keys:
            candidate = f"{base}-{index}"
            index += 1
        known_keys.add(candidate)
        return candidate

    @staticmethod
    def _normalize_key(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9가-힣]+", "-", value.lower()).strip("-")
        return normalized

    @staticmethod
    def _estimate_weight(*parts: str) -> int:
        text = " ".join(part for part in parts if part).lower()
        weight = 1
        if any(term in text for term in ("api", "adapter", "integration", "통합")):
            weight += 1
        if any(term in text for term in ("risk", "failure", "security", "장애", "위험")):
            weight += 1
        if len(text) > 160:
            weight += 1
        return min(weight, 5)

    @staticmethod
    def _objective_for(seed: _PackageSeed, agent_name: str, focus_label: str) -> str:
        return (
            f"{agent_name} owns {focus_label} for this deliverable: "
            f"{seed.objective}"
        )

    @staticmethod
    def _out_of_scope_for(agent_name: str, requires_execution: bool) -> list[str]:
        if not requires_execution:
            return ["Do not edit files; produce planning/specification output only."]
        if agent_name == "gemini":
            return ["Do not merge or finalize implementation without review sign-off."]
        if agent_name == "claude":
            return ["Avoid bulk implementation unless required to unblock architecture."]
        if agent_name == "codex":
            return ["Do not change product scope without recorded decision."]
        return ["Do not expand scope beyond the approved blueprint."]

    @staticmethod
    def _dependencies_for(index: int, agent_names: list[str]) -> list[str]:
        agent = agent_names[index - 1]
        if agent == "codex" and "claude" in agent_names:
            return [f"WP-{agent_names.index('claude') + 1:03d}"]
        if agent == "gemini" and len(agent_names) > 1:
            return [
                f"WP-{idx + 1:03d}"
                for idx, name in enumerate(agent_names)
                if name != "gemini"
            ]
        return []

    @staticmethod
    def _expected_files_for(kind: str, requires_execution: bool) -> list[str]:
        if not requires_execution:
            return ["docs/"]
        expected_by_kind = {
            "component": ["src/", "tests/"],
            "integration": ["src/", "tests/"],
            "dependency": ["src/", "tests/"],
            "validation": ["tests/", "docs/"],
            "planning": ["src/", "tests/", "docs/"],
        }
        return expected_by_kind.get(kind, ["src/", "tests/", "docs/"])


DESIGN_ONLY_MARKERS: tuple[str, ...] = (
    "design only",
    "plan only",
    "proposal only",
    "spec only",
    "architecture only",
    "do not implement",
    "don't implement",
    "no code changes",
    "without code changes",
    "설계만",
    "계획만",
    "구현하지",
    "개발하지",
    "코드 변경 없이",
    "파일을 바꾸지",
)

DESIGN_REQUEST_MARKERS: tuple[str, ...] = (
    "design",
    "plan",
    "proposal",
    "spec",
    "architecture",
    "설계",
    "계획",
    "기획",
    "구조",
    "아키텍처",
)

ASPIRATIONAL_IMPLEMENTATION_MARKERS: tuple[str, ...] = (
    "want to build",
    "want to implement",
    "would like to build",
    "would like to implement",
    "개발하고 싶",
    "구현하고 싶",
    "만들고 싶",
)

EXPLICIT_EXECUTION_COMMAND_MARKERS: tuple[str, ...] = (
    "/execute",
    "execute it",
    "implement it",
    "implement this",
    "go ahead",
    "make it",
    "ship it",
    "start implementation",
    "start development",
    "이 설계대로 구현",
    "이대로 구현",
    "이대로 만들어",
    "개발 시작",
    "구현 시작",
    "개발해",
    "개발하라",
    "구현해",
    "구현하라",
    "진행해",
    "진행하라",
    "수정해",
    "수정하라",
    "추가해",
    "추가하라",
    "작성해",
    "작성하라",
    "만들어",
    "만들라",
    "실행해",
    "실행하라",
)

GENERAL_EXECUTION_MARKERS: tuple[str, ...] = (
    "add",
    "build",
    "change",
    "edit",
    "execute",
    "fix",
    "implement",
    "integrate",
    "modify",
    "refactor",
    "write code",
    "개발",
    "구현",
    "진행",
    "수정",
    "추가",
    "작성",
    "만들",
    "실행",
)


def classify_execution_intent(text: str) -> bool:
    """Return whether a goal/result explicitly requests implementation work."""
    normalized = _normalize_intent_text(text)
    if _contains_any(normalized, DESIGN_ONLY_MARKERS):
        return False

    has_design_request = _contains_any(normalized, DESIGN_REQUEST_MARKERS)
    has_aspirational_implementation = _contains_any(
        normalized,
        ASPIRATIONAL_IMPLEMENTATION_MARKERS,
    )
    has_explicit_execution = _contains_any(
        normalized,
        EXPLICIT_EXECUTION_COMMAND_MARKERS,
    )

    if has_design_request and not has_explicit_execution:
        return False
    if has_aspirational_implementation and not has_explicit_execution:
        return False
    if has_explicit_execution:
        return True
    return _contains_any(normalized, GENERAL_EXECUTION_MARKERS)


def classify_blueprint_followup_action(
    text: str,
) -> BlueprintFollowupAction | None:
    """Classify follow-up text when a blueprint is already ready."""
    normalized = _normalize_intent_text(text)
    if not normalized:
        return None

    cancel_markers = (
        "cancel",
        "stop here",
        "취소",
        "멈춰",
        "중단",
        "여기까지",
    )
    new_markers = (
        "new workflow",
        "new request",
        "start over",
        "새 workflow",
        "새 요청",
        "새로 시작",
        "처음부터",
    )
    if any(marker in normalized for marker in cancel_markers):
        return "cancel"
    if any(marker in normalized for marker in new_markers):
        return "new"

    has_explicit_execution = _contains_any(
        normalized,
        EXPLICIT_EXECUTION_COMMAND_MARKERS,
    )
    if _contains_any(normalized, DESIGN_ONLY_MARKERS):
        return "continue"
    if _contains_any(normalized, DESIGN_REQUEST_MARKERS) and not has_explicit_execution:
        return "continue"
    if (
        _contains_any(normalized, ASPIRATIONAL_IMPLEMENTATION_MARKERS)
        and not has_explicit_execution
    ):
        return None
    if has_explicit_execution:
        return "execute"
    return None


def _normalize_intent_text(text: str) -> str:
    return " ".join(text.lower().split())


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(_contains_marker(text, marker) for marker in markers)


def _contains_marker(text: str, marker: str) -> bool:
    if marker.isascii() and re.fullmatch(r"[a-z0-9 _/-]+", marker):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])", text))
    return marker in text
