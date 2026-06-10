"""Prompt-only resource overlay projection for provider turns."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from trinity.models import AgentSpec
from trinity.providers.policy import InvocationAccess
from trinity.resources.models import (
    AgentResourceProjection,
    ResourceOverlayContext,
)
from trinity.resources.paths import ResourcePathResolver
from trinity.resources.registry import ResourceRegistry


class ResourceProjector:
    """Select resources and render prompt inventory for one agent turn."""

    def __init__(
        self,
        *,
        registry: ResourceRegistry,
        resolver: ResourcePathResolver,
        state_dir: Path,
        projection_mode: str = "managed-overlay",
    ) -> None:
        self.registry = registry
        self.resolver = resolver
        self.state_dir = state_dir.resolve()
        self.projection_mode = projection_mode

    def build_context(
        self,
        *,
        spec: AgentSpec,
        cwd: Path,
        access: InvocationAccess,
        lane: str = "deliberation",
        managed_home: Path | None = None,
    ) -> ResourceOverlayContext:
        """Project matching resources and return prompt inventory metadata."""
        activation = getattr(spec, "resource_activation", "auto")
        if activation == "off" or self.projection_mode == "disabled":
            return ResourceOverlayContext()

        resources = self.registry.select(
            provider=spec.provider.value,
            agent_name=spec.name,
            lane=lane,
            access=access.value,
            packs=getattr(spec, "resource_packs", []),
            resource_types=getattr(spec, "resource_types", []),
            disabled=getattr(spec, "resource_disabled", []),
        )
        if not resources:
            return ResourceOverlayContext(diagnostics=tuple(self.registry.diagnostics))

        projections: dict[str, AgentResourceProjection] = {}
        diagnostics: list[str] = list(self.registry.diagnostics)
        inventory_lines = [
            "[Trinity Resource Overlay]",
            "The following Trinity-provided resources are available for this turn.",
            "Use them only when relevant to the task.",
            "",
        ]

        for resource in resources:
            projection = self._project_resource(
                spec=spec,
                resource=resource,
                cwd=cwd,
                managed_home=managed_home,
                prompt_only=(
                    activation == "prompt-only"
                    or self.projection_mode == "prompt-only"
                    or resource.mount == "prompt"
                ),
            )
            projections[projection.key] = projection
            diagnostics.extend(projection.diagnostics)
            inventory_lines.extend(projection.prompt_inventory)

        prompt = "\n".join(line for line in inventory_lines if line is not None).strip()
        return ResourceOverlayContext(
            prompt=prompt,
            projections=projections,
            diagnostics=tuple(diagnostics),
        )

    def _project_resource(
        self,
        *,
        spec: AgentSpec,
        resource,
        cwd: Path,
        managed_home: Path | None,
        prompt_only: bool,
    ) -> AgentResourceProjection:
        # `source_path` may be nested under the pack. Recover pack root by
        # walking back one parent for each pack-relative manifest segment.
        manifest_parts = resource.manifest_path.split("/")
        pack_root = resource.source_path
        for _part in manifest_parts:
            pack_root = pack_root.parent

        path_set = self.resolver.build_path_set(
            agent_name=spec.name,
            pack_root=pack_root,
            managed_home=managed_home,
        )
        projected_path = (
            path_set.projected_dir
            / resource.pack_id
            / Path(*resource.manifest_path.split("/"))
        )
        diagnostics: list[str] = []
        status = "prompt_only" if prompt_only else "projected"
        projection_mode = "prompt-only" if prompt_only else "managed-overlay"

        try:
            projected_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resource.source_path, projected_path)
        except OSError as exc:
            diagnostics.append(f"resource_projection_failed: {exc}")
            status = "failed"

        provider_path = (
            self.resolver.provider_visible_path(projected_path, cwd=cwd)
            if status != "failed"
            else ""
        )
        projection = AgentResourceProjection(
            agent_name=spec.name,
            provider=spec.provider.value,
            pack_id=resource.pack_id,
            resource_id=resource.id,
            resource_type=resource.resource_type,
            projection_mode=projection_mode,
            source_checksum=resource.checksum,
            source_relpath=self.resolver.source_relpath(resource.source_path),
            projected_relpath=(
                self.resolver.projected_relpath(projected_path)
                if status != "failed"
                else ""
            ),
            projected_path=projected_path if status != "failed" else None,
            provider_path=provider_path,
            status=status,
            diagnostics=diagnostics,
            observed_at=time.time(),
        )
        projection.prompt_inventory = self._inventory_lines(
            resource,
            provider_path=provider_path,
            status=status,
        )
        self._write_lock(spec.name, projection)
        return projection

    def _inventory_lines(
        self,
        resource,
        *,
        provider_path: str,
        status: str,
    ) -> list[str]:
        lines = [
            f"- {resource.inventory_id} ({resource.resource_type})",
        ]
        if resource.summary:
            lines.append(f"  Summary: {resource.summary}")
        if provider_path:
            lines.append(f"  Path: {provider_path}")
        if status == "failed":
            lines.append("  Status: unavailable")
        body = self._prompt_body(resource)
        if body:
            lines.append("  Body:")
            lines.extend(f"    {line}" for line in body.splitlines())
        lines.append("")
        return lines

    @staticmethod
    def _prompt_body(resource) -> str:
        budget = int(getattr(resource, "prompt_budget_chars", 0) or 0)
        if budget <= 0:
            return ""
        try:
            text = resource.source_path.read_text(encoding="utf-8")
        except OSError:
            return ""
        text = text.strip()
        if len(text) <= budget:
            return text
        return text[: max(0, budget - 20)].rstrip() + "\n...[truncated]"

    def _write_lock(self, agent_name: str, projection: AgentResourceProjection) -> None:
        lock_path = self.state_dir / "agents" / agent_name / "overlay" / "manifest.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, object] = {}
        if lock_path.exists():
            try:
                data = json.loads(lock_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    existing = data
            except (json.JSONDecodeError, OSError):
                existing = {}
        projections = existing.get("projections")
        if not isinstance(projections, dict):
            projections = {}
        projections[projection.key] = projection.to_dict()
        existing["projections"] = projections
        existing["updated_at"] = time.time()
        lock_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
