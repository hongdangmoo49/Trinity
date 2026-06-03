"""Tests for BlueprintDecomposer."""

from __future__ import annotations

import pytest

from trinity.models import ArchitectureComponent, Blueprint, WorkStatus
from trinity.workflow.decomposer import BlueprintDecomposer


def _make_blueprint() -> Blueprint:
    """Return a Blueprint with 3 ArchitectureComponents (owners: claude, codex, gemini)."""
    return Blueprint(
        title="User Auth System",
        summary="Add authentication to the app",
        architecture=[
            ArchitectureComponent(
                name="Auth API",
                responsibility="REST endpoints for login/logout",
                owner_agent="claude",
                dependencies=[],
            ),
            ArchitectureComponent(
                name="Token Service",
                responsibility="JWT issuance and validation",
                owner_agent="codex",
                dependencies=["Auth API"],
            ),
            ArchitectureComponent(
                name="Session Store",
                responsibility="Redis-backed session management",
                owner_agent="gemini",
                dependencies=["Token Service"],
            ),
        ],
        acceptance_criteria=["All endpoints return correct HTTP status codes"],
    )


@pytest.fixture
def decomposer() -> BlueprintDecomposer:
    return BlueprintDecomposer()


# ---- tests -----------------------------------------------------------------


def test_decompose_3_agents_3_packages(decomposer: BlueprintDecomposer) -> None:
    """When 3 agents match 3 owners, each gets exactly their own component."""
    bp = _make_blueprint()
    packages = decomposer.decompose(bp, ["claude", "codex", "gemini"])

    assert len(packages) == 3
    owners = {p.owner_agent for p in packages}
    assert owners == {"claude", "codex", "gemini"}

    # Each package should have exactly one component in its scope.
    for pkg in packages:
        assert len(pkg.scope) == 1


def test_decompose_2_agents_2_packages(decomposer: BlueprintDecomposer) -> None:
    """With 2 agents the unassigned component is redistributed round-robin."""
    bp = _make_blueprint()
    packages = decomposer.decompose(bp, ["claude", "codex"])

    assert len(packages) == 2
    owners = {p.owner_agent for p in packages}
    assert owners == {"claude", "codex"}

    total_scope_items = sum(len(p.scope) for p in packages)
    assert total_scope_items == 3  # all components covered


def test_decompose_1_agent_1_package(decomposer: BlueprintDecomposer) -> None:
    """A single agent receives all components."""
    bp = _make_blueprint()
    packages = decomposer.decompose(bp, ["claude"])

    assert len(packages) == 1
    assert packages[0].owner_agent == "claude"
    assert len(packages[0].scope) == 3


def test_decompose_no_agents(decomposer: BlueprintDecomposer) -> None:
    """No agents → empty list."""
    bp = _make_blueprint()
    assert decomposer.decompose(bp, []) == []


def test_each_package_has_acceptance_criteria(decomposer: BlueprintDecomposer) -> None:
    """Every package must carry the blueprint criteria plus per-component criteria."""
    bp = _make_blueprint()
    packages = decomposer.decompose(bp, ["claude", "codex", "gemini"])

    for pkg in packages:
        # Blueprint-level criterion is present
        assert "All endpoints return correct HTTP status codes" in pkg.acceptance_criteria
        # Per-component criterion
        component_criteria = [
            c for c in pkg.acceptance_criteria if "— implemented and tested" in c
        ]
        assert len(component_criteria) == len(pkg.scope)


def test_packages_start_pending(decomposer: BlueprintDecomposer) -> None:
    """All packages must start in PENDING status."""
    bp = _make_blueprint()
    packages = decomposer.decompose(bp, ["claude", "codex", "gemini"])

    for pkg in packages:
        assert pkg.status == WorkStatus.PENDING


def test_package_ids_sequential(decomposer: BlueprintDecomposer) -> None:
    """Package ids must be WP-001, WP-002, etc."""
    bp = _make_blueprint()
    packages = decomposer.decompose(bp, ["claude", "codex", "gemini"])

    expected_ids = ["WP-001", "WP-002", "WP-003"]
    actual_ids = [p.id for p in packages]
    assert actual_ids == expected_ids
