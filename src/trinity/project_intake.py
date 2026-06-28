"""Project intake analysis and artifact writing."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_INTAKE_JSON = "project-intake.json"
PROJECT_INTAKE_MARKDOWN = "project-intake.md"
PROJECT_INTAKE_PROMPT_MAX_CHARS = 4000
PROJECT_MODES = {"existing", "new"}


@dataclass(frozen=True)
class GitWorkspaceAnalysis:
    """Read-only Git metadata for a target workspace."""

    git_repo: bool
    branch: str
    dirty_count: int | None
    untracked_count: int | None


@dataclass(frozen=True)
class ProjectIntake:
    """Project onboarding context safe to persist under Trinity state."""

    mode: str
    target_workspace: Path
    created_at: str
    git_repo: bool
    branch: str
    dirty_count: int | None
    untracked_count: int | None
    package_managers: tuple[str, ...] = ()
    test_commands: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "target_workspace": str(self.target_workspace),
            "created_at": self.created_at,
            "git_repo": self.git_repo,
            "branch": self.branch,
            "dirty_count": self.dirty_count,
            "untracked_count": self.untracked_count,
            "package_managers": list(self.package_managers),
            "test_commands": list(self.test_commands),
            "notes": self.notes,
        }

    def to_markdown(self) -> str:
        package_managers = _csv_or_none(self.package_managers)
        test_commands = _csv_or_none(self.test_commands)
        dirty_count = _value_or_unknown(self.dirty_count)
        untracked_count = _value_or_unknown(self.untracked_count)
        notes = self.notes.strip() or "(none)"
        return "\n".join(
            [
                "# Project Intake",
                "",
                f"- Mode: {self.mode}",
                f"- Target workspace: `{self.target_workspace}`",
                f"- Created at: {self.created_at}",
                f"- Git repo: {self.git_repo}",
                f"- Branch: {self.branch}",
                f"- Dirty count: {dirty_count}",
                f"- Untracked count: {untracked_count}",
                f"- Package managers: {package_managers}",
                f"- Test commands: {test_commands}",
                "",
                "## Notes",
                "",
                notes,
                "",
            ]
        )


@dataclass(frozen=True)
class ProjectIntakePaths:
    """Written project intake artifact paths."""

    json_path: Path
    markdown_path: Path


def build_project_intake(
    *,
    mode: str,
    target_workspace: Path,
    notes: str = "",
    created_at: str | None = None,
) -> ProjectIntake:
    """Build read-only project intake metadata for a target workspace."""
    normalized_mode = _normalize_mode(mode)
    workspace = _safe_resolve(target_workspace)
    git = analyze_git_workspace(workspace)
    package_managers = detect_package_managers(workspace)
    test_commands = suggest_test_commands(workspace, package_managers)
    return ProjectIntake(
        mode=normalized_mode,
        target_workspace=workspace,
        created_at=created_at or _utc_now_iso(),
        git_repo=git.git_repo,
        branch=git.branch,
        dirty_count=git.dirty_count,
        untracked_count=git.untracked_count,
        package_managers=package_managers,
        test_commands=test_commands,
        notes=notes,
    )


def write_project_intake(state_dir: Path, intake: ProjectIntake) -> ProjectIntakePaths:
    """Write project intake JSON and Markdown under the Trinity state directory."""
    state = state_dir.expanduser()
    state.mkdir(parents=True, exist_ok=True)
    json_path = state / PROJECT_INTAKE_JSON
    markdown_path = state / PROJECT_INTAKE_MARKDOWN
    json_path.write_text(
        json.dumps(intake.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(intake.to_markdown(), encoding="utf-8")
    return ProjectIntakePaths(json_path=json_path, markdown_path=markdown_path)


def load_project_intake_markdown(
    state_dir: Path,
    *,
    max_chars: int = PROJECT_INTAKE_PROMPT_MAX_CHARS,
) -> str:
    """Load project intake markdown from Trinity state for prompt context."""
    path = state_dir.expanduser() / PROJECT_INTAKE_MARKDOWN
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}\n\n[truncated]"


def project_intake_prompt_block(
    state_dir: Path,
    *,
    max_chars: int = PROJECT_INTAKE_PROMPT_MAX_CHARS,
) -> str:
    """Return the project intake context block for provider prompts."""
    markdown = load_project_intake_markdown(state_dir, max_chars=max_chars)
    if not markdown:
        return ""
    return f"Project Intake Context:\n{markdown}"


def analyze_git_workspace(path: Path) -> GitWorkspaceAnalysis:
    """Return read-only Git metadata for a path."""
    workspace = _safe_resolve(path)
    git_repo = (workspace / ".git").exists()
    if not git_repo:
        return GitWorkspaceAnalysis(
            git_repo=False,
            branch="(none)",
            dirty_count=None,
            untracked_count=None,
        )
    counts = _git_status_counts(workspace)
    return GitWorkspaceAnalysis(
        git_repo=True,
        branch=_git_branch(workspace),
        dirty_count=counts[0] if counts is not None else None,
        untracked_count=counts[1] if counts is not None else None,
    )


def detect_package_managers(path: Path) -> tuple[str, ...]:
    """Detect likely package managers from common manifest files."""
    workspace = _safe_resolve(path)
    managers: list[str] = []
    if (workspace / "pyproject.toml").exists():
        managers.append("uv" if (workspace / "uv.lock").exists() else "python")
    elif (workspace / "requirements.txt").exists():
        managers.append("python")

    if (workspace / "package.json").exists():
        if (workspace / "pnpm-lock.yaml").exists():
            managers.append("pnpm")
        elif (workspace / "yarn.lock").exists():
            managers.append("yarn")
        else:
            managers.append("npm")

    if (workspace / "Cargo.toml").exists():
        managers.append("cargo")
    if (workspace / "go.mod").exists():
        managers.append("go")
    if (workspace / "pom.xml").exists():
        managers.append("maven")
    if (workspace / "build.gradle").exists() or (workspace / "build.gradle.kts").exists():
        managers.append("gradle")
    return tuple(managers)


def suggest_test_commands(
    path: Path,
    package_managers: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Suggest likely test commands without executing them."""
    workspace = _safe_resolve(path)
    managers = package_managers or detect_package_managers(workspace)
    commands: list[str] = []
    if any(manager in managers for manager in ("npm", "pnpm", "yarn")):
        command = _node_test_command(workspace, managers)
        if command:
            commands.append(command)
    if "uv" in managers:
        commands.append("uv run pytest")
    elif "python" in managers and (workspace / "tests").exists():
        commands.append("pytest")
    if "cargo" in managers:
        commands.append("cargo test")
    if "go" in managers:
        commands.append("go test ./...")
    if "maven" in managers:
        commands.append("mvn test")
    if "gradle" in managers:
        commands.append("./gradlew test")
    return tuple(commands)


def _node_test_command(path: Path, managers: tuple[str, ...]) -> str:
    package_json = path / "package.json"
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict) or "test" not in scripts:
        return ""
    if "pnpm" in managers:
        return "pnpm test"
    if "yarn" in managers:
        return "yarn test"
    return "npm test"


def _git_status_counts(path: Path) -> tuple[int, int] | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    dirty = 0
    untracked = 0
    for line in completed.stdout.splitlines():
        if not line:
            continue
        if line.startswith("??"):
            untracked += 1
        else:
            dirty += 1
    return dirty, untracked


def _git_branch(path: Path) -> str:
    head = _git_head_path(path)
    if not head.exists():
        return "unknown"
    try:
        text = head.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    prefix = "ref: refs/heads/"
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text[:12] if text else "unknown"


def _git_head_path(path: Path) -> Path:
    marker = path / ".git"
    if marker.is_dir():
        return marker / "HEAD"
    if not marker.is_file():
        return marker / "HEAD"
    try:
        text = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return marker / "HEAD"
    prefix = "gitdir:"
    if not text.lower().startswith(prefix):
        return marker / "HEAD"
    gitdir = Path(text[len(prefix) :].strip())
    if not gitdir.is_absolute():
        gitdir = path / gitdir
    return gitdir / "HEAD"


def _normalize_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in PROJECT_MODES:
        raise ValueError(f"Unsupported project intake mode: {mode}")
    return normalized


def _safe_resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except OSError:
        return path.expanduser().absolute()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _csv_or_none(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "(none)"


def _value_or_unknown(value: int | None) -> str:
    return str(value) if value is not None else "unknown"
