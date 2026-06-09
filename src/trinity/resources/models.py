"""Models for Trinity-managed agent resources."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


RESOURCE_TYPES = {"skill", "hook", "command", "prompt", "mcp", "file"}
RESOURCE_MOUNTS = {"copy", "render", "adapter", "prompt"}
RESOURCE_FAILURE_POLICIES = {
    "degrade",
    "skip",
    "fail-provider-call",
    "fail-workflow",
}
RESOURCE_ACTIVATIONS = {"auto", "project", "prompt-only", "off"}
RESOURCE_PROJECTION_MODES = {"managed-overlay", "prompt-only", "disabled"}
RESOURCE_COLLISION_POLICIES = {"namespace", "fail", "native-wins"}
RESOURCE_SIDE_EFFECTS = {"none", "read", "write", "network", "exec"}


@dataclass(frozen=True)
class AgentResourceRef:
    """One resource declared by a Trinity resource pack manifest."""

    id: str
    pack_id: str
    version: str
    resource_type: str
    source_path: Path
    manifest_path: str
    summary: str = ""
    target_providers: tuple[str, ...] = ()
    target_agents: tuple[str, ...] = ()
    lanes: tuple[str, ...] = ()
    access: tuple[str, ...] = ()
    mount: str = "copy"
    side_effects: str = "none"
    failure_policy: str = "degrade"
    checksum: str = ""
    prompt_budget_chars: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def qualified_id(self) -> str:
        return f"{self.pack_id}.{self.id}"

    @property
    def inventory_id(self) -> str:
        return f"trinity::{self.pack_id}/{self.id}"


@dataclass
class AgentResourceProjection:
    """Resource projection result for one agent/provider turn."""

    agent_name: str
    provider: str
    pack_id: str
    resource_id: str
    resource_type: str
    projection_mode: str
    source_checksum: str
    source_relpath: str = ""
    projected_relpath: str = ""
    projected_path: Path | None = None
    provider_path: str = ""
    env: dict[str, str] = field(default_factory=dict)
    argv: list[str] = field(default_factory=list)
    prompt_inventory: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | projected | prompt_only | skipped | failed
    diagnostics: list[str] = field(default_factory=list)
    observed_at: float = field(default_factory=time.time)

    @property
    def key(self) -> str:
        return ":".join(
            [
                self.agent_name,
                self.provider,
                self.pack_id,
                self.resource_id,
                self.resource_type,
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "provider": self.provider,
            "pack_id": self.pack_id,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "projection_mode": self.projection_mode,
            "source_checksum": self.source_checksum,
            "source_relpath": self.source_relpath,
            "projected_relpath": self.projected_relpath,
            "projected_path": "",
            "provider_path": self.provider_path,
            "env": dict(self.env),
            "argv": list(self.argv),
            "prompt_inventory": list(self.prompt_inventory),
            "status": self.status,
            "diagnostics": list(self.diagnostics),
            "observed_at": self.observed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentResourceProjection":
        projected_path = str(data.get("projected_path") or "").strip()
        return cls(
            agent_name=str(data.get("agent_name", "")),
            provider=str(data.get("provider", "")),
            pack_id=str(data.get("pack_id", "")),
            resource_id=str(data.get("resource_id", "")),
            resource_type=str(data.get("resource_type", "")),
            projection_mode=str(data.get("projection_mode", "")),
            source_checksum=str(data.get("source_checksum", "")),
            source_relpath=str(data.get("source_relpath", "")),
            projected_relpath=str(data.get("projected_relpath", "")),
            projected_path=Path(projected_path) if projected_path else None,
            provider_path=str(data.get("provider_path", "")),
            env=(
                dict(data.get("env", {}))
                if isinstance(data.get("env"), dict)
                else {}
            ),
            argv=[
                str(item)
                for item in (
                    data.get("argv", []) if isinstance(data.get("argv"), list) else []
                )
            ],
            prompt_inventory=[
                str(item)
                for item in (
                    data.get("prompt_inventory", [])
                    if isinstance(data.get("prompt_inventory"), list)
                    else []
                )
            ],
            status=str(data.get("status", "pending")),
            diagnostics=[
                str(item)
                for item in (
                    data.get("diagnostics", [])
                    if isinstance(data.get("diagnostics"), list)
                    else []
                )
            ],
            observed_at=float(data.get("observed_at", time.time())),
        )


@dataclass(frozen=True)
class ResourcePathSet:
    """Resolved path set for one agent resource projection."""

    project_dir: Path
    state_dir: Path
    resource_root: Path
    pack_root: Path
    managed_home: Path
    overlay_dir: Path
    projected_dir: Path
    provider_visible_projected_dir: str
    provider_visible_home: str
    platform: str


@dataclass(frozen=True)
class ResourceOverlayContext:
    """Prompt and metadata produced for a provider turn."""

    prompt: str = ""
    projections: dict[str, AgentResourceProjection] = field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()

    def projections_to_metadata(self) -> dict[str, dict[str, Any]]:
        return {
            key: projection.to_dict()
            for key, projection in self.projections.items()
        }
