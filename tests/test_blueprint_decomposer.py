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


def test_decompose_single_agent_package_has_required_fields():
    decomposer = BlueprintDecomposer()

    packages = decomposer.decompose(_blueprint(), ["claude"], requires_execution=False)

    assert len(packages) == 1
    package = packages[0]
    assert package.id == "WP-001"
    assert package.owner_agent == "claude"
    assert package.status == WorkStatus.PENDING
    assert package.requires_execution is False
    assert package.objective
    assert package.scope
    assert package.acceptance_criteria


def test_decompose_two_agents_creates_two_packages():
    packages = BlueprintDecomposer().decompose(_blueprint(), ["claude", "codex"])

    assert [package.id for package in packages] == ["WP-001", "WP-002"]
    assert [package.owner_agent for package in packages] == ["claude", "codex"]
    assert all(package.objective for package in packages)
    assert all(package.scope for package in packages)
    assert all(package.acceptance_criteria for package in packages)


def test_decompose_three_agents_assigns_review_scope_to_gemini():
    packages = BlueprintDecomposer().decompose(
        _blueprint(),
        ["claude", "codex", "gemini"],
    )

    assert len(packages) == 3
    gemini = packages[2]
    assert gemini.owner_agent == "gemini"
    assert any("risk" in item.lower() or "reliability" in item.lower()
               for item in gemini.scope)
    assert gemini.dependencies == ["WP-001", "WP-002"]


def test_decompose_accepts_blueprint_dict():
    packages = BlueprintDecomposer().decompose(
        _blueprint().to_dict(),
        ["codex"],
    )

    assert len(packages) == 1
    assert packages[0].owner_agent == "codex"
