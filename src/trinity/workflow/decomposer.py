"""Blueprint decomposition into agent-owned work packages."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from trinity.workflow.models import WorkPackage, WorkStatus
from trinity.workflow.structured import Blueprint


class BlueprintDecomposer:
    """Create top-level work packages from a finalized blueprint."""

    AGENT_FOCUS: dict[str, tuple[str, tuple[str, ...]]] = {
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
        "codex": (
            "implementation and integration",
            (
                "adapter",
                "api",
                "code",
                "data",
                "graph",
                "implementation",
                "route",
                "service",
                "search",
            ),
        ),
        "gemini": (
            "review, risk, and validation",
            (
                "edge",
                "quality",
                "reliability",
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
        """Return one top-level package for each active agent."""
        agent_names = [name for name in active_agents if name]
        if not agent_names:
            return []

        normalized = (
            Blueprint.from_dict(blueprint) if isinstance(blueprint, dict) else blueprint
        )
        component_scope = self._component_scope(normalized)
        assignments = self._assign_scope(agent_names, component_scope)
        criteria = normalized.acceptance_criteria or [
            f"Deliver package output aligned with {normalized.title}.",
        ]

        packages: list[WorkPackage] = []
        for index, agent_name in enumerate(agent_names, start=1):
            package_id = f"WP-{index:03d}"
            focus_label, _ = self.AGENT_FOCUS.get(agent_name, self.DEFAULT_FOCUS)
            scope = assignments.get(agent_name) or self._fallback_scope(
                normalized,
                agent_name,
            )
            packages.append(
                WorkPackage(
                    id=package_id,
                    title=self._title_for(agent_name, focus_label, normalized.title),
                    owner_agent=agent_name,
                    objective=self._objective_for(
                        agent_name,
                        focus_label,
                        normalized.title,
                    ),
                    scope=scope,
                    out_of_scope=self._out_of_scope_for(agent_name, requires_execution),
                    dependencies=self._dependencies_for(index, agent_names),
                    expected_files=self._expected_files_for(
                        agent_name,
                        requires_execution,
                    ),
                    acceptance_criteria=list(criteria),
                    status=WorkStatus.PENDING,
                    requires_execution=requires_execution,
                )
            )
        return packages

    def _assign_scope(
        self,
        agent_names: list[str],
        component_scope: list[str],
    ) -> dict[str, list[str]]:
        assignments = {agent_name: [] for agent_name in agent_names}
        unassigned: list[str] = []

        for scope_item in component_scope:
            owner = self._best_owner(scope_item, agent_names)
            if owner:
                assignments[owner].append(scope_item)
            else:
                unassigned.append(scope_item)

        for index, scope_item in enumerate(unassigned):
            owner = agent_names[index % len(agent_names)]
            assignments[owner].append(scope_item)

        # Keep every package substantive even when all components matched one agent.
        for index, agent_name in enumerate(agent_names):
            if not assignments[agent_name] and component_scope:
                assignments[agent_name].append(component_scope[index % len(component_scope)])
        return assignments

    def _best_owner(self, scope_item: str, agent_names: list[str]) -> str | None:
        normalized = scope_item.lower()
        best_agent = None
        best_score = 0
        for agent_name in agent_names:
            _, keywords = self.AGENT_FOCUS.get(agent_name, self.DEFAULT_FOCUS)
            score = sum(1 for keyword in keywords if keyword in normalized)
            if score > best_score:
                best_agent = agent_name
                best_score = score
        return best_agent

    @staticmethod
    def _component_scope(blueprint: Blueprint) -> list[str]:
        scope: list[str] = []
        for component in blueprint.architecture:
            item = f"{component.name}: {component.responsibility}".strip()
            if item and item != ":":
                scope.append(item)
        for flow in blueprint.data_flow:
            scope.append(f"Data flow: {flow}")
        for dependency in blueprint.external_dependencies:
            scope.append(f"External dependency: {dependency}")
        for risk in blueprint.risks:
            scope.append(f"Risk: {risk.description}")
        return scope

    @staticmethod
    def _fallback_scope(blueprint: Blueprint, agent_name: str) -> list[str]:
        if blueprint.summary:
            return [f"{agent_name} contribution: {blueprint.summary}"]
        return [f"{agent_name} contribution: finalize {blueprint.title}."]

    @staticmethod
    def _title_for(agent_name: str, focus_label: str, blueprint_title: str) -> str:
        clean_title = blueprint_title or "Blueprint"
        return f"{agent_name}: {focus_label} for {clean_title}"

    @staticmethod
    def _objective_for(agent_name: str, focus_label: str, blueprint_title: str) -> str:
        clean_title = blueprint_title or "the approved blueprint"
        return (
            f"{agent_name} owns {focus_label} work needed to deliver {clean_title}."
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
    def _expected_files_for(agent_name: str, requires_execution: bool) -> list[str]:
        if not requires_execution:
            return ["docs/"]
        expected = {
            "claude": ["docs/", "src/"],
            "codex": ["src/", "tests/"],
            "gemini": ["tests/", "docs/"],
        }
        return expected.get(agent_name, ["src/", "tests/", "docs/"])


def classify_execution_intent(text: str) -> bool:
    """Return whether a goal/result appears to request implementation work."""
    normalized = " ".join(text.lower().split())
    design_only_markers = (
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
        "코드 변경 없이",
    )
    execution_markers = (
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
        "구현",
        "수정",
        "추가",
        "작성",
    )
    if any(marker in normalized for marker in design_only_markers):
        return False
    for marker in execution_markers:
        if marker.isascii():
            if re.search(rf"\b{re.escape(marker)}\b", normalized):
                return True
        elif marker in normalized:
            return True
    return False
