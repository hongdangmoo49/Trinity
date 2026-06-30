"""Blueprint decomposition into agent-owned work packages."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from trinity.models import AgentSpec
from trinity.routing.profile_router import ProfileRouter, RoutingDecision
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
    expected_files: list[str] = field(default_factory=list)
    estimated_weight: int = 1


class BlueprintDecomposer:
    """Create top-level work packages from a finalized blueprint."""

    PROVIDER_PRIORITY: tuple[str, ...] = ("codex", "claude", "antigravity")
    UNKNOWN_WRITE_SCOPE = "__trinity_unknown_write_scope__"

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
    }

    DEFAULT_FOCUS = ("general delivery", ("component", "delivery", "workflow"))

    def __init__(self, router: ProfileRouter | None = None):
        self.router = router or ProfileRouter()

    def decompose(
        self,
        blueprint: Blueprint | dict[str, Any],
        active_agents: Iterable[str] | dict[str, AgentSpec],
        *,
        requires_execution: bool = True,
    ) -> list[WorkPackage]:
        """Return deliverable-oriented packages assigned across active providers."""
        agent_specs = self._normalize_agent_specs(active_agents)
        agent_names = list(agent_specs)
        if not agent_names:
            return []

        normalized = (
            Blueprint.from_dict(blueprint) if isinstance(blueprint, dict) else blueprint
        )
        criteria = self._clean_acceptance_criteria(normalized.acceptance_criteria) or [
            f"Deliver package output aligned with {normalized.title}.",
        ]
        central_packages = self._packages_from_central_graph(
            normalized.work_packages,
            agent_specs,
            criteria,
            requires_execution,
        )
        if central_packages:
            return central_packages

        seeds = self._package_seeds(normalized)
        decisions_by_seed = self._assign_owners(
            agent_specs,
            seeds,
            requires_execution,
        )

        packages: list[WorkPackage] = []
        seed_to_package_id: dict[str, str] = {}
        for index, seed in enumerate(seeds, start=1):
            package_id = f"WP-{index:03d}"
            seed_to_package_id[seed.key] = package_id
            decision = decisions_by_seed[seed.key]
            agent_name = decision.agent_name
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
                        seed,
                        requires_execution,
                    ),
                    acceptance_criteria=list(criteria),
                    status=WorkStatus.PENDING,
                    requires_execution=requires_execution,
                    estimated_weight=seed.estimated_weight,
                    task_kind=decision.task_kind,
                    routing_reason=decision.reason,
                    routing_score=decision.score,
                    profile_revision=decision.profile_revision,
                )
            )
        for package, seed in zip(packages, seeds):
            package.dependencies = [
                seed_to_package_id[key]
                for key in seed.dependency_keys
                if key in seed_to_package_id and seed_to_package_id[key] != package.id
            ]
        return packages

    def _packages_from_central_graph(
        self,
        proposed_packages: Iterable[WorkPackage],
        agent_specs: dict[str, AgentSpec],
        fallback_criteria: list[str],
        requires_execution: bool,
    ) -> list[WorkPackage]:
        """Validate and conservatively normalize model-authored work packages."""
        agent_names = list(agent_specs)
        seeds: list[_PackageSeed] = []
        source_by_key: dict[str, WorkPackage] = {}
        known_keys: set[str] = set()
        for index, package in enumerate(proposed_packages, start=1):
            title = self._clean_text(package.title) or f"Work Package {index}"
            objective = self._clean_text(package.objective) or f"Deliver {title}."
            if self._is_noise_line(title) or self._is_noise_line(objective):
                continue
            key_source = package.id or title
            key = self._seed_key(key_source, known_keys)
            scope = self._clean_list_items(package.scope) or [objective]
            seed = _PackageSeed(
                key=key,
                title=title,
                objective=objective,
                scope=scope,
                kind=self._central_seed_kind(package),
                expected_files=self._clean_expected_files(package.expected_files),
                estimated_weight=max(1, package.estimated_weight),
            )
            seeds.append(seed)
            source_by_key[key] = package

        if not seeds:
            return []

        decisions_by_seed = self._assign_owners(
            agent_specs,
            seeds,
            requires_execution,
        )
        packages: list[WorkPackage] = []
        alias_to_package_id: dict[str, str] = {}
        for index, seed in enumerate(seeds, start=1):
            package_id = f"WP-{index:03d}"
            source = source_by_key[seed.key]
            repair_notes: list[str] = []
            source_id = source.id.strip()
            if source_id and source_id != package_id:
                repair_notes.append(
                    f"id normalized from {source_id!r} to {package_id!r}"
                )
            owner = source.owner_agent.strip()
            if owner not in agent_names:
                decision = decisions_by_seed[seed.key]
                repair_notes.append(
                    f"owner reassigned from {owner or '(empty)'!r} "
                    f"to {decision.agent_name!r} because owner is not active"
                )
                owner = decision.agent_name
            else:
                decision = self._routing_decision_for_seed(
                    agent_specs[owner],
                    seed,
                    requires_execution,
                )
            criteria = (
                self._clean_acceptance_criteria(source.acceptance_criteria)
                or fallback_criteria
            )
            expected_files = self._central_expected_files(
                source,
                seed,
                requires_execution,
            )
            if (
                requires_execution
                and expected_files == [self.UNKNOWN_WRITE_SCOPE]
                and not seed.expected_files
            ):
                repair_notes.append("expected_files missing; using unknown write scope")
            risk = self._normalize_risk_value(source.risk)
            if risk != str(source.risk or "medium").strip().lower():
                repair_notes.append(
                    f"risk normalized from {source.risk!r} to {risk!r}"
                )
            packages.append(
                WorkPackage(
                    id=package_id,
                    title=seed.title,
                    owner_agent=owner,
                    objective=seed.objective,
                    scope=list(seed.scope),
                    out_of_scope=self._central_out_of_scope(source, requires_execution),
                    expected_files=expected_files,
                    acceptance_criteria=list(criteria),
                    status=WorkStatus.PENDING,
                    requires_execution=requires_execution,
                    estimated_weight=seed.estimated_weight,
                    parallel_group=source.parallel_group,
                    parallelizable=source.parallelizable,
                    risk=risk,
                    repair_notes=repair_notes,
                    task_kind=decision.task_kind,
                    routing_reason=(
                        "central owner retained; "
                        f"profile score {decision.score:.1f}: {decision.reason}"
                    ),
                    routing_score=decision.score,
                    profile_revision=decision.profile_revision,
                )
            )
            self._register_package_aliases(alias_to_package_id, source, seed, package_id)

        for package, seed in zip(packages, seeds):
            source = source_by_key[seed.key]
            repair_notes = list(package.repair_notes)
            package.dependencies = self._central_dependencies_for(
                source.dependencies,
                package.id,
                alias_to_package_id,
                repair_notes,
            )
            package.repair_notes = repair_notes
        return packages

    @staticmethod
    def _central_seed_kind(package: WorkPackage) -> str:
        text = " ".join([package.title, package.objective, *package.scope]).lower()
        if any(term in text for term in ("risk", "test", "validation", "검증", "위험")):
            return "validation"
        if any(term in text for term in ("api", "adapter", "dependency", "연동", "통합")):
            return "dependency"
        return "component"

    @staticmethod
    def _task_kind_for_seed(seed: _PackageSeed) -> str:
        if seed.kind in {"dependency", "integration"}:
            return "integration"
        if seed.kind == "validation":
            return "testing"
        if seed.kind == "planning":
            return "planning"
        return "implementation"

    def _clean_expected_files(self, values: Iterable[str]) -> list[str]:
        cleaned = self._clean_list_items(values)
        return [item for item in cleaned if item not in {".", "./"}]

    def _central_expected_files(
        self,
        source: WorkPackage,
        seed: _PackageSeed,
        requires_execution: bool,
    ) -> list[str]:
        if not requires_execution:
            return ["docs/"]
        if seed.expected_files:
            return list(seed.expected_files)
        return [self.UNKNOWN_WRITE_SCOPE]

    def _central_out_of_scope(
        self,
        source: WorkPackage,
        requires_execution: bool,
    ) -> list[str]:
        out_of_scope = self._clean_list_items(source.out_of_scope)
        if out_of_scope:
            return out_of_scope
        return self._out_of_scope_for(source.owner_agent, requires_execution)

    def _register_package_aliases(
        self,
        aliases: dict[str, str],
        source: WorkPackage,
        seed: _PackageSeed,
        package_id: str,
    ) -> None:
        candidates = {
            package_id,
            source.id,
            seed.key,
            seed.title,
            self._normalize_key(source.id),
            self._normalize_key(seed.title),
        }
        for candidate in candidates:
            value = str(candidate).strip()
            if value:
                aliases[value] = package_id

    def _central_dependencies_for(
        self,
        dependencies: Iterable[str],
        package_id: str,
        alias_to_package_id: dict[str, str],
        repair_notes: list[str],
    ) -> list[str]:
        resolved: list[str] = []
        seen: set[str] = set()
        for dependency in dependencies:
            raw = str(dependency).strip()
            if not raw:
                continue
            dep_id = alias_to_package_id.get(raw) or alias_to_package_id.get(
                self._normalize_key(raw)
            )
            if not dep_id:
                repair_notes.append(
                    f"dependency {raw!r} removed because no package matched"
                )
                continue
            if dep_id == package_id:
                repair_notes.append(f"self dependency {raw!r} removed")
                continue
            if dep_id in seen:
                continue
            resolved.append(dep_id)
            seen.add(dep_id)
        return resolved

    @staticmethod
    def _normalize_risk_value(value: str) -> str:
        normalized = str(value or "medium").strip().lower()
        if normalized in {"low", "medium", "high"}:
            return normalized
        return "medium"

    def _normalize_agent_specs(
        self,
        active_agents: Iterable[str] | dict[str, AgentSpec],
    ) -> dict[str, AgentSpec]:
        specs = self.router.specs_from_active_agents(active_agents)
        normalized: dict[str, AgentSpec] = {}
        for name, spec in specs.items():
            agent_name = str(name).strip()
            if agent_name and agent_name not in normalized:
                normalized[agent_name] = spec
        return normalized

    def _assign_owners(
        self,
        agent_specs: dict[str, AgentSpec],
        seeds: list[_PackageSeed],
        requires_execution: bool,
    ) -> dict[str, RoutingDecision]:
        """Assign packages by load balance first, provider priority as tie-break."""
        agent_names = list(agent_specs)
        loads = {agent_name: 0 for agent_name in agent_names}
        assignments: dict[str, RoutingDecision] = {}
        for seed in sorted(seeds, key=lambda item: item.estimated_weight, reverse=True):
            scores = {
                agent_name: self._routing_decision_for_seed(
                    agent_specs[agent_name],
                    seed,
                    requires_execution,
                )
                for agent_name in agent_names
            }
            owner = min(
                agent_names,
                key=lambda agent_name: (
                    loads[agent_name],
                    -scores[agent_name].score,
                    int(
                        agent_specs[agent_name].profile.routing_priority
                        or self._priority_index(agent_name)
                    ),
                    agent_names.index(agent_name),
                ),
            )
            assignments[seed.key] = scores[owner]
            loads[owner] += seed.estimated_weight
        return assignments

    def _routing_decision_for_seed(
        self,
        spec: AgentSpec,
        seed: _PackageSeed,
        requires_execution: bool,
    ) -> RoutingDecision:
        text = " ".join([seed.title, seed.objective, *seed.scope])
        task = self.router.classify_text(
            text,
            turn_mode="execute" if requires_execution else "plan",
            expected_files=seed.expected_files,
            requires_write=requires_execution,
            fallback_kind=self._task_kind_for_seed(seed),
        )
        return self.router.score_agent(spec.name, spec, task)

    def _priority_index(self, agent_name: str) -> int:
        try:
            return self.PROVIDER_PRIORITY.index(agent_name)
        except ValueError:
            return len(self.PROVIDER_PRIORITY)

    def _package_seeds(self, blueprint: Blueprint) -> list[_PackageSeed]:
        seeds: list[_PackageSeed] = []
        known_keys: set[str] = set()
        for index, component in enumerate(blueprint.architecture, start=1):
            seed = self._component_seed(component, index, known_keys)
            if seed is not None:
                seeds.append(seed)

        if blueprint.data_flow:
            data_flow = self._clean_list_items(blueprint.data_flow)
            if data_flow:
                if seeds:
                    seeds = self._attach_data_flow_to_component_seeds(
                        seeds,
                        data_flow,
                    )
                else:
                    data_flow_key = self._seed_key("workflow-implementation", known_keys)
                    seeds.append(
                        _PackageSeed(
                            key=data_flow_key,
                            title=self._workflow_seed_title(blueprint.title),
                            objective="Implement the approved end-to-end workflow.",
                            scope=[f"Integration flow: {item}" for item in data_flow],
                            kind="integration",
                            expected_files=self._scoped_expected_files(
                                "integration",
                                data_flow_key,
                            ),
                            estimated_weight=max(1, len(data_flow)),
                        )
                    )

        external_dependencies = self._clean_list_items(blueprint.external_dependencies)
        if external_dependencies:
            dependency_key = self._seed_key("external-dependencies", known_keys)
            seeds.append(
                _PackageSeed(
                    key=dependency_key,
                    title="External dependency adapters",
                    objective="Integrate and guard the approved external dependencies.",
                    scope=[
                        f"External dependency: {item}"
                        for item in external_dependencies
                    ],
                    kind="dependency",
                    expected_files=self._scoped_expected_files(
                        "dependencies",
                        dependency_key,
                    ),
                    estimated_weight=max(1, len(external_dependencies)),
                )
            )

        risks = [
            risk
            for risk in blueprint.risks
            if not self._is_noise_line(risk.description)
        ]
        if risks:
            risk_key = self._seed_key("risk-validation", known_keys)
            seeds.append(
                _PackageSeed(
                    key=risk_key,
                    title="Risk and validation coverage",
                    objective="Cover the blueprint risks with tests, checks, or docs.",
                    scope=[f"Risk: {risk.description}" for risk in risks],
                    kind="validation",
                    expected_files=[
                        f"tests/validation/{risk_key}/",
                        f"docs/validation/{risk_key}.md",
                    ],
                    estimated_weight=max(1, len(risks)),
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

    @staticmethod
    def _attach_data_flow_to_component_seeds(
        seeds: list[_PackageSeed],
        data_flow: list[str],
    ) -> list[_PackageSeed]:
        updated = list(seeds)
        for index, item in enumerate(data_flow):
            target_index = index % len(updated)
            seed = updated[target_index]
            updated[target_index] = replace(
                seed,
                scope=[*seed.scope, f"Integration flow: {item}"],
            )
        return updated

    @classmethod
    def _workflow_seed_title(cls, blueprint_title: str) -> str:
        title = cls._clean_text(blueprint_title)
        if not title:
            return "End-to-end workflow implementation"
        return f"{title} workflow implementation"

    def _component_seed(
        self,
        component: Any,
        index: int,
        known_keys: set[str],
    ) -> _PackageSeed | None:
        title, responsibility = self._clean_component(
            component.name,
            component.responsibility,
        )
        if not title and not responsibility:
            return None
        if not title:
            title = f"Architecture Component {index}"
        if self._is_non_deliverable_component(title, responsibility):
            return None

        key = self._seed_key(title, known_keys)
        objective = responsibility or f"Deliver the {title} component."
        scope_item = f"{title}: {objective}".strip()
        return _PackageSeed(
            key=key,
            title=title,
            objective=objective,
            scope=[scope_item] if scope_item and scope_item != ":" else [title],
            kind="component",
            dependency_keys=[
                self._normalize_key(dependency)
                for dependency in component.dependencies
                if not self._is_noise_line(dependency)
            ],
            expected_files=self._scoped_expected_files("components", key),
            estimated_weight=self._estimate_weight(title, responsibility),
        )

    @classmethod
    def _clean_component(cls, name: str, responsibility: str) -> tuple[str, str]:
        parsed = cls._parse_tree_component(name) or cls._parse_tree_component(
            responsibility
        )
        if parsed is not None:
            title, inline_responsibility = parsed
            cleaned_responsibility = cls._clean_text(responsibility)
            if cls._looks_like_same_component_line(title, cleaned_responsibility):
                cleaned_responsibility = ""
            return title, inline_responsibility or cleaned_responsibility
        return cls._clean_text(name), cls._clean_text(responsibility)

    @staticmethod
    def _parse_tree_component(value: str) -> tuple[str, str] | None:
        text = str(value).strip()
        match = re.match(
            r"^[\s│|]*(?:[├└]\s*──|[-*+])\s*"
            r"(?P<name>[A-Za-z_][A-Za-z0-9_./-]*)"
            r"(?:\s*#\s*(?P<comment>.+))?\s*$",
            text,
        )
        if not match:
            return None
        name = match.group("name").strip().strip("/")
        comment = (match.group("comment") or "").strip()
        return name, comment

    @staticmethod
    def _clean_text(value: str) -> str:
        text = str(value).strip()
        text = re.sub(r"^`{3,}\w*\s*$", "", text)
        text = re.sub(r"^\s*#{1,6}\s*", "", text)
        text = re.sub(r"^\s*[-*+]\s*", "", text)
        text = re.sub(r"^\*+|\*+$", "", text).strip()
        text = re.sub(r"\*\*", "", text).strip()
        text = re.sub(r"\s+", " ", text)
        return text

    @classmethod
    def _clean_list_items(cls, values: Iterable[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = cls._clean_text(value)
            if cls._is_noise_line(item):
                continue
            if item in seen:
                continue
            cleaned.append(item)
            seen.add(item)
        return cleaned

    @classmethod
    def _clean_acceptance_criteria(cls, values: Iterable[str]) -> list[str]:
        cleaned: list[str] = []
        for item in cls._clean_list_items(values):
            normalized = item.lower()
            if normalized.startswith("vote:"):
                continue
            if "blocked_by_question" in normalized:
                continue
            if re.match(r"q\d+[\).:]", normalized):
                continue
            if normalized.startswith(("(", "->", "→")):
                continue
            if "사용자 결정 필요" in item:
                continue
            cleaned.append(item)
        return cleaned

    @classmethod
    def _is_non_deliverable_component(cls, title: str, responsibility: str) -> bool:
        if cls._is_noise_line(title):
            return True
        if responsibility and cls._is_noise_line(responsibility):
            return True
        normalized = cls._normalize_key(title)
        if normalized in {
            "reason",
            "rationale",
            "alternative",
            "alternatives",
            "options",
            "core-modules",
            "gamecore",
            "게임-엔진",
            "이유",
            "대안",
            "핵심-모듈",
        }:
            return True
        if title.endswith("/") and title.rstrip("/") == responsibility.rstrip("/"):
            return True
        return False

    @staticmethod
    def _is_noise_line(value: str) -> bool:
        text = str(value).strip()
        if not text:
            return True
        stripped = text.strip("`*_-=| ")
        if not stripped:
            return True
        if text.startswith("|") and text.endswith("|"):
            return True
        if re.fullmatch(r"[\s\-\|:]+", text):
            return True
        return False

    @staticmethod
    def _looks_like_same_component_line(title: str, value: str) -> bool:
        return bool(title and value and value.startswith(title))

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
        if agent_name == "antigravity":
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
        if agent == "antigravity" and len(agent_names) > 1:
            return [
                f"WP-{idx + 1:03d}"
                for idx, name in enumerate(agent_names)
                if name != "antigravity"
            ]
        return []

    @staticmethod
    def _scoped_expected_files(category: str, key: str) -> list[str]:
        return [
            f"src/{category}/{key}/",
            f"tests/{category}/{key}/",
        ]

    def _expected_files_for(self, seed: _PackageSeed, requires_execution: bool) -> list[str]:
        if not requires_execution:
            return ["docs/"]
        if seed.expected_files:
            return list(seed.expected_files)
        expected_by_kind = {
            "component": self._scoped_expected_files("components", seed.key),
            "integration": self._scoped_expected_files("integration", seed.key),
            "dependency": self._scoped_expected_files("dependencies", seed.key),
            "validation": [
                f"tests/validation/{seed.key}/",
                f"docs/validation/{seed.key}.md",
            ],
            "planning": [f"docs/plans/{seed.key}.md"],
        }
        return expected_by_kind.get(seed.kind, self._scoped_expected_files("work", seed.key))


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
    "analysis",
    "analyze",
    "inspect",
    "review",
    "설계",
    "계획",
    "기획",
    "구조",
    "아키텍처",
    "분석",
    "검토",
    "파악",
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

STRONG_ANALYSIS_REQUEST_MARKERS: tuple[str, ...] = (
    "tell me",
    "do i need to",
    "is it okay to",
    "should i",
    "what should",
    "where should",
    "which file should",
    "which files should",
    "how should",
    "suggest",
    "recommend",
    "알려줘",
    "알려",
    "어디를",
    "무엇을",
    "어떤 파일",
    "어떻게",
    "해야 할까",
    "해도 될까",
    "필요할까",
    "제안해",
    "추천해",
)

ANALYSIS_REQUEST_MARKERS: tuple[str, ...] = (
    "find",
    *STRONG_ANALYSIS_REQUEST_MARKERS,
    "찾아줘",
    "찾아",
    "제안",
    "추천",
)

EXPLICIT_EXECUTION_COMMAND_MARKERS: tuple[str, ...] = (
    "/execute",
    "execute it",
    "delete dead code",
    "delete it",
    "delete this",
    "delete unused",
    "implement it",
    "implement this",
    "implement fixes",
    "improve it",
    "improve this",
    "and fix",
    "then fix",
    "go ahead",
    "make it",
    "remove dead code",
    "remove it",
    "remove this",
    "remove unused",
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
    "개선해",
    "개선하라",
    "고쳐줘",
    "고쳐",
    "바꿔줘",
    "바꿔",
    "적용해",
    "반영해",
    "진행해",
    "진행하라",
    "수정해",
    "수정하라",
    "삭제해",
    "삭제하라",
    "제거해",
    "제거하라",
    "지워줘",
    "지워",
    "갱신해",
    "갱신하라",
    "변경해",
    "변경하라",
    "생성해",
    "생성하라",
    "업데이트해",
    "업데이트하라",
    "이동해",
    "이동하라",
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
    "create",
    "edit",
    "execute",
    "fix",
    "generate",
    "implement",
    "integrate",
    "modify",
    "move",
    "refactor",
    "rename",
    "update",
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
    has_analysis_request = _contains_any(normalized, ANALYSIS_REQUEST_MARKERS)
    has_strong_analysis_request = _contains_any(
        normalized,
        STRONG_ANALYSIS_REQUEST_MARKERS,
    )
    has_explicit_execution = _contains_any(
        normalized,
        EXPLICIT_EXECUTION_COMMAND_MARKERS,
    )

    if has_design_request and not has_explicit_execution:
        return False
    if has_aspirational_implementation and not has_explicit_execution:
        return False
    if has_strong_analysis_request:
        return False
    if has_analysis_request and not has_explicit_execution:
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
