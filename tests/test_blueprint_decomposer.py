"""Tests for blueprint decomposition into work packages."""

from trinity.workflow import Blueprint, BlueprintDecomposer, WorkStatus
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


def test_decompose_legacy_gemini_still_gets_validation_scope():
    packages = BlueprintDecomposer().decompose(
        _blueprint(),
        ["claude", "codex", "gemini"],
    )

    gemini_packages = [
        package for package in packages if package.owner_agent == "gemini"
    ]
    assert gemini_packages
    assert any(
        "risk" in item.lower() or "reliability" in item.lower()
        for package in gemini_packages
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
