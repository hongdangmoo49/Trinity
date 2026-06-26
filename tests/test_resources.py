"""Tests for Trinity-managed agent resource overlays."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trinity.config import TrinityConfig
from trinity.models import AgentSpec, Provider
from trinity.providers.invoker import CliProviderInvoker, PromptRequest
from trinity.providers.policy import InvocationAccess
from trinity.resources.paths import ResourcePathError, ResourcePathResolver
from trinity.resources.projector import ResourceProjector
from trinity.resources.registry import ResourceRegistry, ResourceRegistryError
from trinity.workflow.engine import WorkflowEngine
from trinity.workflow.models import WorkflowState


def _write_pack(
    resource_root: Path,
    *,
    manifest_path: str = "skills/implementation-plan.md",
    target_provider: str = "codex",
) -> Path:
    pack_root = resource_root / "packs" / "trinity-core"
    (pack_root / "skills").mkdir(parents=True)
    (pack_root / "skills" / "implementation-plan.md").write_text(
        "Plan implementation in small, testable steps.",
        encoding="utf-8",
    )
    pack_root.joinpath("manifest.toml").write_text(
        f"""
id = "trinity-core"
version = "0.1.0"
title = "Trinity Core"

[[resources]]
id = "implementation-plan"
type = "skill"
path = "{manifest_path}"
summary = "Plan implementation work."
target_providers = ["{target_provider}"]
target_agents = ["codex"]
lanes = ["deliberation"]
access = ["read-only"]
mount = "copy"
failure_policy = "degrade"
prompt_budget_chars = 80
""",
        encoding="utf-8",
    )
    return pack_root


def _resolver(tmp_path: Path) -> ResourcePathResolver:
    state_dir = tmp_path / ".trinity"
    return ResourcePathResolver(
        project_dir=tmp_path,
        state_dir=state_dir,
        resource_root=state_dir / "resources",
    )


def test_config_loads_resource_settings(tmp_path):
    state_dir = tmp_path / ".trinity"
    state_dir.mkdir()
    config_path = state_dir / "trinity.config"
    config_path.write_text(
        """
[general]
provider_process_namespace = "auto"

[resources]
enabled = true
root = ".trinity/resources"
projection_mode = "prompt-only"
collision_policy = "namespace"
default_failure_policy = "degrade"
audit = true

[agents.codex]
provider = "codex"
cli_command = "codex"
enabled = true

[agents.codex.resources]
packs = ["trinity-core"]
types = ["skill", "prompt"]
disabled = ["trinity-core.unused"]
activation = "prompt-only"
""",
        encoding="utf-8",
    )

    config = TrinityConfig.load(config_path)

    assert config.resource_projection_mode == "prompt-only"
    assert config.resources_root == Path(".trinity/resources")
    assert config.provider_process_namespace == "auto"
    codex = config.agents["codex"]
    assert codex.resource_packs == ["trinity-core"]
    assert codex.resource_types == ["skill", "prompt"]
    assert codex.resource_disabled == ["trinity-core.unused"]
    assert codex.resource_activation == "prompt-only"


@pytest.mark.parametrize(
    "bad_path",
    [
        "../outside.md",
        "/tmp/outside.md",
        "C:/Users/name/skill.md",
        "skills\\windows.md",
        "//server/share/skill.md",
    ],
)
def test_manifest_path_rejects_os_specific_or_escaping_paths(tmp_path, bad_path):
    resolver = _resolver(tmp_path)

    with pytest.raises(ResourcePathError):
        resolver.validate_manifest_path(bad_path)


def test_registry_loads_and_filters_resources(tmp_path):
    resolver = _resolver(tmp_path)
    _write_pack(resolver.resource_root)

    registry = ResourceRegistry.load(root=resolver.resource_root, resolver=resolver)
    selected = registry.select(
        provider="codex",
        agent_name="codex",
        lane="deliberation",
        access="read-only",
    )

    assert len(selected) == 1
    assert selected[0].inventory_id == "trinity::trinity-core/implementation-plan"
    assert selected[0].checksum.startswith("sha256:")
    assert not registry.select(
        provider="claude-code",
        agent_name="claude",
        lane="deliberation",
        access="read-only",
    )


def test_registry_strict_mode_raises_on_invalid_manifest_path(tmp_path):
    resolver = _resolver(tmp_path)
    _write_pack(resolver.resource_root, manifest_path="../outside.md")

    with pytest.raises((ResourceRegistryError, ResourcePathError)):
        ResourceRegistry.load(
            root=resolver.resource_root,
            resolver=resolver,
            strict=True,
        )


def test_projector_copies_resource_and_builds_prompt_inventory(tmp_path):
    state_dir = tmp_path / ".trinity"
    resolver = _resolver(tmp_path)
    _write_pack(resolver.resource_root)
    registry = ResourceRegistry.load(root=resolver.resource_root, resolver=resolver)
    projector = ResourceProjector(
        registry=registry,
        resolver=resolver,
        state_dir=state_dir,
    )
    spec = AgentSpec(
        name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        resource_packs=["trinity-core"],
    )

    context = projector.build_context(
        spec=spec,
        cwd=tmp_path,
        access=InvocationAccess.READ_ONLY,
        lane="deliberation",
    )

    assert "trinity::trinity-core/implementation-plan" in context.prompt
    assert "Plan implementation work." in context.prompt
    assert "Plan implementation in small, testable steps." in context.prompt
    projection = next(iter(context.projections.values()))
    assert projection.status == "projected"
    assert projection.projected_path is not None
    assert projection.projected_path.exists()
    assert projection.projected_relpath.startswith("agents/codex/overlay/projected/")
    assert str(tmp_path) not in projection.to_dict()["projected_path"]

    lock_path = state_dir / "agents" / "codex" / "overlay" / "manifest.lock"
    lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
    stored_projection = next(iter(lock_data["projections"].values()))
    assert stored_projection["source_relpath"].startswith("resources/packs/")
    assert stored_projection["projected_relpath"].startswith("agents/codex/")
    assert stored_projection["projected_path"] == ""


def test_invoker_render_prompt_includes_resource_overlay(tmp_path):
    request = PromptRequest(
        agent_name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        role_prompt="System role.",
        context_prompt="Shared context.",
        resource_prompt="[Trinity Resource Overlay]\n- trinity::core/skill",
        prompt="Do the work.",
        cwd=tmp_path,
    )

    rendered = CliProviderInvoker._render_prompt(request)

    assert "[System Role]\nSystem role." in rendered
    assert "[Context]\nShared context." in rendered
    assert "[Trinity Resource Overlay]" in rendered
    assert rendered.endswith("Do the work.")


def test_workflow_session_persists_resource_projection_metadata(tmp_path):
    engine = WorkflowEngine(state_dir=tmp_path / ".trinity")
    engine.session.state = WorkflowState.DELIBERATING
    engine._provider_observations().record_provider_observations(
        {
            "resource_projections": {
                "codex:codex:trinity-core:implementation-plan:skill": {
                    "agent_name": "codex",
                    "provider": "codex",
                    "pack_id": "trinity-core",
                    "resource_id": "implementation-plan",
                    "resource_type": "skill",
                    "projection_mode": "managed-overlay",
                    "source_checksum": "sha256:test",
                    "source_relpath": "resources/packs/trinity-core/skills/a.md",
                    "projected_relpath": "agents/codex/overlay/projected/a.md",
                    "provider_path": ".trinity/agents/codex/overlay/projected/a.md",
                    "status": "projected",
                }
            }
        }
    )

    loaded = WorkflowEngine(state_dir=tmp_path / ".trinity")

    assert loaded.session.resource_projections
    projection = next(iter(loaded.session.resource_projections.values()))
    assert projection.pack_id == "trinity-core"
    assert projection.projected_relpath == "agents/codex/overlay/projected/a.md"
