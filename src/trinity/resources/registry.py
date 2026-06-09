"""Resource pack manifest loading for Trinity-managed overlays."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # pragma: no cover - Python 3.10 compatibility path.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from trinity.resources.models import (
    RESOURCE_FAILURE_POLICIES,
    RESOURCE_MOUNTS,
    RESOURCE_SIDE_EFFECTS,
    RESOURCE_TYPES,
    AgentResourceRef,
)
from trinity.resources.paths import ResourcePathError, ResourcePathResolver


class ResourceRegistryError(ValueError):
    """Raised when resource registry or manifest data is invalid."""


@dataclass(frozen=True)
class ResourcePack:
    """Loaded Trinity resource pack."""

    id: str
    version: str
    title: str
    root: Path
    resources: tuple[AgentResourceRef, ...]


class ResourceRegistry:
    """Load Trinity resource packs from `.trinity/resources`."""

    def __init__(
        self,
        *,
        root: Path,
        resolver: ResourcePathResolver,
        packs: tuple[ResourcePack, ...] = (),
        diagnostics: tuple[str, ...] = (),
    ) -> None:
        self.root = root
        self.resolver = resolver
        self.packs = packs
        self.diagnostics = diagnostics

    @classmethod
    def load(
        cls,
        *,
        root: Path,
        resolver: ResourcePathResolver,
        strict: bool = False,
    ) -> "ResourceRegistry":
        """Load registry and pack manifests, returning an empty registry when absent."""
        root = root.resolve()
        if not root.exists():
            return cls(root=root, resolver=resolver)

        pack_paths = cls._pack_paths(root)
        packs: list[ResourcePack] = []
        diagnostics: list[str] = []
        seen_resource_ids: set[str] = set()

        for pack_path in pack_paths:
            try:
                pack = cls._load_pack(pack_path, resolver)
            except (OSError, tomllib.TOMLDecodeError, ResourceRegistryError, ResourcePathError) as exc:
                if strict:
                    raise
                diagnostics.append(f"{pack_path}: {exc}")
                continue

            for resource in pack.resources:
                unique_key = resource.qualified_id
                if unique_key in seen_resource_ids:
                    message = f"Duplicate resource id: {unique_key}"
                    if strict:
                        raise ResourceRegistryError(message)
                    diagnostics.append(message)
                    continue
                seen_resource_ids.add(unique_key)
            packs.append(pack)

        return cls(
            root=root,
            resolver=resolver,
            packs=tuple(packs),
            diagnostics=tuple(diagnostics),
        )

    @property
    def resources(self) -> tuple[AgentResourceRef, ...]:
        items: list[AgentResourceRef] = []
        for pack in self.packs:
            items.extend(pack.resources)
        return tuple(items)

    def select(
        self,
        *,
        provider: str,
        agent_name: str,
        lane: str,
        access: str,
        packs: list[str] | tuple[str, ...] = (),
        resource_types: list[str] | tuple[str, ...] = (),
        disabled: list[str] | tuple[str, ...] = (),
    ) -> tuple[AgentResourceRef, ...]:
        """Return resources matching agent/provider/lane/access filters."""
        pack_filter = {item for item in packs if item}
        type_filter = {item for item in resource_types if item}
        disabled_set = {item for item in disabled if item}
        selected: list[AgentResourceRef] = []

        for resource in self.resources:
            if pack_filter and resource.pack_id not in pack_filter:
                continue
            if type_filter and resource.resource_type not in type_filter:
                continue
            if resource.id in disabled_set or resource.qualified_id in disabled_set:
                continue
            if resource.target_providers and provider not in resource.target_providers:
                continue
            if resource.target_agents and agent_name not in resource.target_agents:
                continue
            if resource.lanes and lane not in resource.lanes:
                continue
            if resource.access and access not in resource.access:
                continue
            selected.append(resource)

        return tuple(selected)

    @staticmethod
    def _pack_paths(root: Path) -> tuple[Path, ...]:
        registry_path = root / "registry.toml"
        if registry_path.exists():
            data = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            packs = data.get("packs", data.get("enabled_packs", []))
            if isinstance(packs, list):
                paths = [root / str(item) for item in packs if str(item).strip()]
                if paths:
                    return tuple(paths)

        packs_dir = root / "packs"
        if not packs_dir.exists():
            return ()
        return tuple(
            sorted(
                path
                for path in packs_dir.iterdir()
                if path.is_dir() and (path / "manifest.toml").exists()
            )
        )

    @staticmethod
    def _load_pack(pack_path: Path, resolver: ResourcePathResolver) -> ResourcePack:
        manifest_path = pack_path / "manifest.toml"
        if not manifest_path.exists():
            raise ResourceRegistryError("manifest.toml is missing")
        data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        pack_id = str(data.get("id") or pack_path.name).strip()
        if not pack_id:
            raise ResourceRegistryError("pack id is required")
        version = str(data.get("version") or "0.0.0").strip()
        title = str(data.get("title") or pack_id).strip()

        resources_data = data.get("resources", [])
        if not isinstance(resources_data, list):
            raise ResourceRegistryError("resources must be a list")

        resources: list[AgentResourceRef] = []
        for index, item in enumerate(resources_data, start=1):
            if not isinstance(item, dict):
                raise ResourceRegistryError(f"resource #{index} must be a table")
            resources.append(
                ResourceRegistry._parse_resource(
                    item,
                    pack_id=pack_id,
                    version=version,
                    pack_root=pack_path,
                    resolver=resolver,
                )
            )

        return ResourcePack(
            id=pack_id,
            version=version,
            title=title,
            root=pack_path.resolve(),
            resources=tuple(resources),
        )

    @staticmethod
    def _parse_resource(
        data: dict[str, Any],
        *,
        pack_id: str,
        version: str,
        pack_root: Path,
        resolver: ResourcePathResolver,
    ) -> AgentResourceRef:
        resource_id = str(data.get("id") or "").strip()
        if not resource_id:
            raise ResourceRegistryError("resource id is required")
        resource_type = str(data.get("type") or "").strip()
        if resource_type not in RESOURCE_TYPES:
            raise ResourceRegistryError(
                f"unsupported resource type for {resource_id}: {resource_type!r}"
            )
        manifest_path = str(data.get("path") or "").strip()
        source_path = resolver.resolve_pack_path(pack_root, manifest_path)
        mount = str(data.get("mount") or "copy").strip()
        if mount not in RESOURCE_MOUNTS:
            raise ResourceRegistryError(
                f"unsupported mount for {resource_id}: {mount!r}"
            )
        failure_policy = str(data.get("failure_policy") or "degrade").strip()
        if failure_policy not in RESOURCE_FAILURE_POLICIES:
            raise ResourceRegistryError(
                f"unsupported failure_policy for {resource_id}: {failure_policy!r}"
            )
        side_effects = str(data.get("side_effects") or "none").strip()
        if side_effects not in RESOURCE_SIDE_EFFECTS:
            raise ResourceRegistryError(
                f"unsupported side_effects for {resource_id}: {side_effects!r}"
            )

        return AgentResourceRef(
            id=resource_id,
            pack_id=pack_id,
            version=version,
            resource_type=resource_type,
            source_path=source_path,
            manifest_path=manifest_path,
            summary=str(data.get("summary") or "").strip(),
            target_providers=_string_tuple(data.get("target_providers", [])),
            target_agents=_string_tuple(data.get("target_agents", [])),
            lanes=_string_tuple(data.get("lanes", [])),
            access=_string_tuple(data.get("access", [])),
            mount=mount,
            side_effects=side_effects,
            failure_policy=failure_policy,
            checksum=_sha256_file(source_path),
            prompt_budget_chars=max(0, int(data.get("prompt_budget_chars", 0) or 0)),
            metadata={
                key: value
                for key, value in data.items()
                if key
                not in {
                    "id",
                    "type",
                    "path",
                    "summary",
                    "target_providers",
                    "target_agents",
                    "lanes",
                    "access",
                    "mount",
                    "side_effects",
                    "failure_policy",
                    "prompt_budget_chars",
                }
            },
        )


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
