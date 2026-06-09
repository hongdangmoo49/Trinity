"""Cross-platform path handling for Trinity resource overlays."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from trinity.platform.capabilities import normalize_os_name
from trinity.resources.models import ResourcePathSet


class ResourcePathError(ValueError):
    """Raised when a resource path is unsafe or unsupported."""


class ResourcePathResolver:
    """Resolve and render resource overlay paths for provider processes."""

    def __init__(
        self,
        *,
        project_dir: Path,
        state_dir: Path,
        resource_root: Path,
        os_name: str | None = None,
    ) -> None:
        self.project_dir = project_dir.resolve()
        self.state_dir = state_dir.resolve()
        self.resource_root = self._resolve_under_project(resource_root).resolve()
        self.os_name = normalize_os_name(os_name)

    def validate_manifest_path(self, value: str) -> PurePosixPath:
        """Return a validated pack-relative POSIX path."""
        text = str(value or "").strip()
        if not text:
            raise ResourcePathError("Resource path must not be empty.")
        if "\\" in text:
            raise ResourcePathError(
                f"Resource path must use POSIX separators: {text!r}"
            )
        if text.startswith(("/", "//")):
            raise ResourcePathError(f"Resource path must be relative: {text!r}")
        if re.match(r"^[A-Za-z]:", text):
            raise ResourcePathError(f"Drive-letter paths are not allowed: {text!r}")
        if text.startswith("\\\\"):
            raise ResourcePathError(f"UNC paths are not allowed: {text!r}")

        path = PurePosixPath(text)
        if any(part in {"", ".", ".."} for part in path.parts):
            raise ResourcePathError(
                f"Resource path contains unsafe segment: {text!r}"
            )
        return path

    def resolve_pack_path(self, pack_root: Path, manifest_path: str) -> Path:
        """Resolve a manifest path under a pack root, blocking escapes."""
        rel_path = self.validate_manifest_path(manifest_path)
        root = pack_root.resolve()
        resolved = root.joinpath(*rel_path.parts).resolve()
        if not resolved.is_relative_to(root):
            raise ResourcePathError(
                f"Resource path escapes pack root: {manifest_path!r}"
            )
        return resolved

    def build_path_set(
        self,
        *,
        agent_name: str,
        pack_root: Path,
        managed_home: Path | None = None,
    ) -> ResourcePathSet:
        """Return the path set used to project resources for one agent."""
        home = (
            managed_home.resolve()
            if managed_home is not None
            else (self.state_dir / "agents" / agent_name / "provider-state").resolve()
        )
        overlay_dir = (self.state_dir / "agents" / agent_name / "overlay").resolve()
        projected_dir = overlay_dir / "projected"
        return ResourcePathSet(
            project_dir=self.project_dir,
            state_dir=self.state_dir,
            resource_root=self.resource_root,
            pack_root=pack_root.resolve(),
            managed_home=home,
            overlay_dir=overlay_dir,
            projected_dir=projected_dir,
            provider_visible_projected_dir=self.render_provider_path(projected_dir),
            provider_visible_home=self.render_provider_path(home),
            platform=self.os_name,
        )

    def source_relpath(self, path: Path) -> str:
        """Return a state-dir-relative source path when possible."""
        return self._relative_or_absolute(path, self.state_dir)

    def projected_relpath(self, path: Path) -> str:
        """Return a state-dir-relative projected path when possible."""
        return self._relative_or_absolute(path, self.state_dir)

    def provider_visible_path(self, path: Path, *, cwd: Path | None = None) -> str:
        """Render a path string that the provider process can open."""
        resolved = path.resolve()
        if cwd is not None:
            cwd_resolved = cwd.resolve()
            if resolved.is_relative_to(cwd_resolved):
                return self._format_relative(resolved.relative_to(cwd_resolved))
        return self.render_provider_path(resolved)

    def render_provider_path(self, path: Path) -> str:
        """Render an absolute path for the configured provider OS namespace."""
        text = str(path)
        if self.os_name == "windows":
            return text.replace("/", "\\")
        return path.as_posix()

    def namespace_issue_for_command(self, cli_command: str) -> str:
        """Return a warning when a command appears to belong to another namespace."""
        command = str(cli_command or "").strip()
        if not command:
            return "empty provider command"
        if self.os_name == "windows":
            if command.startswith("/"):
                return "windows provider command looks like a POSIX path"
            return ""
        if command.lower().endswith(".exe") or "\\" in command:
            return "POSIX provider command looks like a Windows executable"
        if re.match(r"^[A-Za-z]:", command):
            return "POSIX provider command uses a Windows drive-letter path"
        return ""

    def _resolve_under_project(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        return self.project_dir / path

    def _relative_or_absolute(self, path: Path, root: Path) -> str:
        resolved = path.resolve()
        root_resolved = root.resolve()
        if resolved.is_relative_to(root_resolved):
            return resolved.relative_to(root_resolved).as_posix()
        return self.render_provider_path(resolved)

    def _format_relative(self, path: Path) -> str:
        text = path.as_posix()
        if self.os_name == "windows":
            return text.replace("/", "\\")
        return text
