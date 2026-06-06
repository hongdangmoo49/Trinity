"""Tests for blueprint decomposition into work packages."""

from trinity.workflow import Blueprint, BlueprintDecomposer, WorkPackage, WorkStatus
from trinity.workflow.structured import ArchitectureComponent, RiskItem


def _blueprint() -> Blueprint:
    return Blueprint(
        title="L2 Bridge Path Bot",
        summary="Finds reliable bridge routes across layer 2 networks.",
        architecture=[
            ArchitectureComponent(
                name="Route Scoring Model",
                responsibility="score routes by fee, latency, and reliability",
            ),
            ArchitectureComponent(
                name="Bridge Adapter Interface",
                responsibility="integrate bridge quote APIs",
            ),
            ArchitectureComponent(
                name="Reliability Review Matrix",
                responsibility="track provider risk and edge cases",
            ),
        ],
        data_flow=["request -> quote aggregation -> scoring -> ranked route"],
        external_dependencies=["Hop API", "Across API"],
        risks=[RiskItem(description="stale bridge quotes")],
        acceptance_criteria=[
            "returns ranked bridge routes",
            "documents provider failure modes",
        ],
    )


def test_decompose_single_agent_packages_have_required_fields():
    decomposer = BlueprintDecomposer()

    packages = decomposer.decompose(_blueprint(), ["claude"], requires_execution=False)

    assert len(packages) > 1
    assert [package.id for package in packages] == [
        f"WP-{index:03d}" for index in range(1, len(packages) + 1)
    ]
    assert {package.owner_agent for package in packages} == {"claude"}
    assert all(package.status == WorkStatus.PENDING for package in packages)
    assert all(package.requires_execution is False for package in packages)
    assert all(package.objective for package in packages)
    assert all(package.scope for package in packages)
    assert all(package.acceptance_criteria for package in packages)
    assert all(package.estimated_weight >= 1 for package in packages)


def test_decompose_two_agents_balances_deliverable_packages():
    packages = BlueprintDecomposer().decompose(_blueprint(), ["claude", "codex"])

    assert len(packages) > 2
    owners = [package.owner_agent for package in packages]
    assert set(owners) == {"claude", "codex"}
    weights = {"claude": 0, "codex": 0}
    for package in packages:
        weights[package.owner_agent] += package.estimated_weight
    assert abs(weights["claude"] - weights["codex"]) <= 1
    assert all(package.objective for package in packages)
    assert all(package.scope for package in packages)
    assert all(package.acceptance_criteria for package in packages)


def test_decompose_three_agents_balances_independent_slices():
    packages = BlueprintDecomposer().decompose(
        _blueprint(),
        ["claude", "codex", "antigravity"],
    )

    assert len(packages) > 3
    weights = {"claude": 0, "codex": 0, "antigravity": 0}
    for package in packages:
        weights[package.owner_agent] += package.estimated_weight
    assert max(weights.values()) - min(weights.values()) <= 1
    antigravity_packages = [
        package for package in packages if package.owner_agent == "antigravity"
    ]
    assert any(
        "risk" in item.lower() or "reliability" in item.lower()
        for package in antigravity_packages
        for item in package.scope
    )


def test_decompose_accepts_blueprint_dict():
    packages = BlueprintDecomposer().decompose(
        _blueprint().to_dict(),
        ["codex"],
    )

    assert len(packages) > 1
    assert {package.owner_agent for package in packages} == {"codex"}


def test_decompose_component_dependencies_resolve_to_package_ids():
    blueprint = _blueprint()
    blueprint.architecture[1].dependencies = ["Route Scoring Model"]

    packages = BlueprintDecomposer().decompose(
        blueprint,
        ["claude", "codex", "antigravity"],
    )

    scoring = next(package for package in packages if package.title == "Route Scoring Model")
    adapter = next(package for package in packages if package.title == "Bridge Adapter Interface")
    assert adapter.dependencies == [scoring.id]


def test_decompose_filters_markdown_artifacts_and_scopes_expected_files():
    blueprint = Blueprint(
        title="Mobile Shooting Game",
        summary="Build a 1945-style mobile shooter.",
        architecture=[
            ArchitectureComponent(name="*게임 엔진", responsibility="** Unity 2D (권장)"),
            ArchitectureComponent(name="이유", responsibility="2D mobile pipeline"),
            ArchitectureComponent(name="*핵심 모듈", responsibility="**"),
            ArchitectureComponent(name="```", responsibility="```"),
            ArchitectureComponent(name="GameCore/", responsibility="GameCore/"),
            ArchitectureComponent(
                name="├── InputController    # 터치/드래그 입력 처리",
                responsibility="├── InputController    # 터치/드래그 입력 처리",
            ),
            ArchitectureComponent(
                name="├── EntityManager      # 플레이어/적/탄환 풀링",
                responsibility="├── EntityManager      # 플레이어/적/탄환 풀링",
            ),
        ],
        data_flow=["```", "Touch Input -> PlayerMovement", "```"],
        external_dependencies=[
            "| 항목 | 용도 |",
            "|------|------|",
            "| Unity 2D | 게임 엔진 |",
        ],
        risks=[
            RiskItem(description="| 리스크 | 완화책 |"),
            RiskItem(description="모바일 성능 병목"),
        ],
        acceptance_criteria=[
            "60 FPS 유지",
            "## 사용자 결정 필요",
            "*Q1. 게임 엔진 선택?**",
            "(A) Unity 2D",
            "VOTE: BLOCKED_BY_QUESTION",
        ],
    )

    packages = BlueprintDecomposer().decompose(
        blueprint,
        ["claude", "codex", "antigravity"],
    )

    titles = [package.title for package in packages]
    assert "InputController" in titles
    assert "EntityManager" in titles
    assert "```" not in titles
    assert "GameCore/" not in titles
    assert "게임 엔진" not in titles
    assert "이유" not in titles
    assert all(package.expected_files != ["src/", "tests/"] for package in packages)
    assert all(
        "blocked_by_question" not in criterion.lower()
        for package in packages
        for criterion in package.acceptance_criteria
    )
    component_packages = [
        package
        for package in packages
        if package.title in {"InputController", "EntityManager"}
    ]
    assert len({tuple(package.expected_files) for package in component_packages}) == 2


def test_decompose_prefers_central_work_package_graph():
    blueprint = _blueprint()
    blueprint.work_packages = [
        WorkPackage(
            id="frontend",
            title="Frontend shell",
            owner_agent="claude",
            objective="Build the interactive shell.",
            scope=["UI state", "layout"],
            expected_files=["src/frontend/"],
            acceptance_criteria=["UI smoke test passes"],
            parallel_group=1,
            parallelizable=True,
            risk="low",
        ),
        WorkPackage(
            id="api",
            title="API bridge",
            owner_agent="codex",
            objective="Connect UI events to the API.",
            dependencies=["frontend"],
            scope=["API adapter"],
            expected_files=["src/api/"],
            parallel_group=2,
            parallelizable=False,
            risk="high",
        ),
    ]

    packages = BlueprintDecomposer().decompose(
        blueprint,
        ["claude", "codex", "antigravity"],
    )

    assert [package.title for package in packages] == ["Frontend shell", "API bridge"]
    assert [package.id for package in packages] == ["WP-001", "WP-002"]
    assert packages[0].owner_agent == "claude"
    assert packages[0].acceptance_criteria == ["UI smoke test passes"]
    assert packages[1].dependencies == ["WP-001"]
    assert packages[1].parallel_group == 2
    assert packages[1].parallelizable is False
    assert packages[1].risk == "high"


def test_decompose_repairs_invalid_central_graph_fields_conservatively():
    blueprint = _blueprint()
    blueprint.work_packages = [
        WorkPackage(
            id="shared",
            title="Shared setup",
            owner_agent="missing",
            objective="Prepare shared setup.",
            dependencies=["Shared setup", "missing-dependency"],
            scope=[],
            expected_files=[],
            risk="extreme",
        ),
        WorkPackage(
            id="tests",
            title="Validation pass",
            owner_agent="antigravity",
            objective="Validate the setup.",
            dependencies=["shared", "tests"],
            expected_files=["tests/validation/"],
        ),
    ]

    packages = BlueprintDecomposer().decompose(blueprint, ["codex", "antigravity"])

    assert [package.id for package in packages] == ["WP-001", "WP-002"]
    assert packages[0].owner_agent in {"codex", "antigravity"}
    assert packages[0].scope == ["Prepare shared setup."]
    assert packages[0].expected_files == [BlueprintDecomposer.UNKNOWN_WRITE_SCOPE]
    assert packages[0].risk == "medium"
    assert packages[1].owner_agent == "antigravity"
    assert packages[1].dependencies == ["WP-001"]
