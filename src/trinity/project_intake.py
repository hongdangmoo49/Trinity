"""Project intake analysis and artifact writing."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:  # pragma: no cover - Python 3.10 fallback is covered by dependency tests.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


PROJECT_INTAKE_JSON = "project-intake.json"
PROJECT_INTAKE_MARKDOWN = "project-intake.md"
PROJECT_INTAKE_PROMPT_MAX_CHARS = 4000
PROJECT_MODES = {"existing", "new"}
NEW_PROJECT_BRIEF_FIELD_LABELS = {
    "product_goal": "goal",
    "project_type": "type",
    "target_users": "users",
    "success_criteria": "success",
    "first_milestone": "milestone",
}
SCOPE_PARENT_DIRS = ("apps", "packages", "services", "libs", "crates", "modules")
SCOPE_MANIFEST_FILES = (
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
)


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
    dev_commands: tuple[str, ...] = ()
    build_commands: tuple[str, ...] = ()
    entrypoints: tuple[str, ...] = ()
    source_roots: tuple[str, ...] = ()
    scope_candidates: tuple[str, ...] = ()
    selected_scope: str = ""
    docs_found: tuple[str, ...] = ()
    product_goal: str = ""
    project_type: str = ""
    starter_profile: str = ""
    target_users: str = ""
    success_criteria: str = ""
    stack_preferences: tuple[str, ...] = ()
    first_milestone: str = ""
    constraints: tuple[str, ...] = ()
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
            "dev_commands": list(self.dev_commands),
            "build_commands": list(self.build_commands),
            "entrypoints": list(self.entrypoints),
            "source_roots": list(self.source_roots),
            "scope_candidates": list(self.scope_candidates),
            "selected_scope": self.selected_scope,
            "docs_found": list(self.docs_found),
            "product_goal": self.product_goal,
            "project_type": self.project_type,
            "starter_profile": self.starter_profile,
            "target_users": self.target_users,
            "success_criteria": self.success_criteria,
            "stack_preferences": list(self.stack_preferences),
            "first_milestone": self.first_milestone,
            "constraints": list(self.constraints),
            "notes": self.notes,
        }

    def to_markdown(self) -> str:
        package_managers = _csv_or_none(self.package_managers)
        test_commands = _csv_or_none(self.test_commands)
        dev_commands = _csv_or_none(self.dev_commands)
        build_commands = _csv_or_none(self.build_commands)
        entrypoints = _csv_or_none(self.entrypoints)
        source_roots = _csv_or_none(self.source_roots)
        scope_candidates = _csv_or_none(self.scope_candidates)
        selected_scope = self.selected_scope.strip() or "(none)"
        docs_found = _csv_or_none(self.docs_found)
        stack_preferences = _csv_or_none(self.stack_preferences)
        constraints = _csv_or_none(self.constraints)
        product_goal = self.product_goal.strip() or "(none)"
        project_type = self.project_type.strip() or "(none)"
        starter_profile = self.starter_profile.strip() or "(none)"
        target_users = self.target_users.strip() or "(none)"
        success_criteria = self.success_criteria.strip() or "(none)"
        first_milestone = self.first_milestone.strip() or "(none)"
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
                f"- Dev commands: {dev_commands}",
                f"- Build commands: {build_commands}",
                f"- Entrypoints: {entrypoints}",
                f"- Source roots: {source_roots}",
                f"- Scope candidates: {scope_candidates}",
                f"- Selected scope: {selected_scope}",
                f"- Docs found: {docs_found}",
                "",
                "## Brief",
                "",
                f"- Product goal: {product_goal}",
                f"- Project type: {project_type}",
                f"- Starter profile: {starter_profile}",
                f"- Target users: {target_users}",
                f"- Success criteria: {success_criteria}",
                f"- Stack preferences: {stack_preferences}",
                f"- First milestone: {first_milestone}",
                f"- Constraints: {constraints}",
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
    product_goal: str = "",
    project_type: str = "",
    starter_profile: str = "",
    target_users: str = "",
    success_criteria: str = "",
    stack_preferences: tuple[str, ...] | list[str] = (),
    first_milestone: str = "",
    constraints: tuple[str, ...] | list[str] = (),
    selected_scope: str = "",
    created_at: str | None = None,
) -> ProjectIntake:
    """Build read-only project intake metadata for a target workspace."""
    normalized_mode = _normalize_mode(mode)
    workspace = _safe_resolve(target_workspace)
    git = analyze_git_workspace(workspace)
    package_managers = detect_package_managers(workspace)
    test_commands = suggest_test_commands(workspace, package_managers)
    dev_commands = suggest_dev_commands(workspace, package_managers)
    build_commands = suggest_build_commands(workspace, package_managers)
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
        dev_commands=dev_commands,
        build_commands=build_commands,
        entrypoints=detect_entrypoints(workspace, package_managers),
        source_roots=detect_source_roots(workspace),
        scope_candidates=detect_scope_candidates(workspace),
        selected_scope=selected_scope.strip(),
        docs_found=detect_docs(workspace),
        product_goal=product_goal.strip(),
        project_type=project_type.strip(),
        starter_profile=starter_profile.strip(),
        target_users=target_users.strip(),
        success_criteria=success_criteria.strip(),
        stack_preferences=_normalize_string_tuple(stack_preferences),
        first_milestone=first_milestone.strip(),
        constraints=_normalize_string_tuple(constraints),
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


def missing_new_project_brief_field_keys(intake: ProjectIntake) -> tuple[str, ...]:
    """Return missing brief field keys required for new-project planning."""
    if intake.mode != "new":
        return ()
    missing: list[str] = []
    for field_name in NEW_PROJECT_BRIEF_FIELD_LABELS:
        if not str(getattr(intake, field_name)).strip():
            missing.append(field_name)
    return tuple(missing)


def missing_new_project_brief_fields(intake: ProjectIntake) -> tuple[str, ...]:
    """Return user-facing missing brief field labels for a new project."""
    return tuple(
        NEW_PROJECT_BRIEF_FIELD_LABELS[field_name]
        for field_name in missing_new_project_brief_field_keys(intake)
    )


def existing_project_intake_drift_fields(
    intake: ProjectIntake,
    target_workspace: Path,
    *,
    live_git: GitWorkspaceAnalysis | None = None,
) -> tuple[str, ...]:
    """Return saved existing-project intake fields that differ from live analysis."""
    if intake.mode != "existing":
        return ()
    workspace = _safe_resolve(target_workspace)
    if workspace != _safe_resolve(intake.target_workspace):
        return ()
    git = live_git or analyze_git_workspace(workspace)
    package_managers = detect_package_managers(workspace)
    live_values = {
        "git_repo": git.git_repo,
        "branch": git.branch,
        "dirty_count": git.dirty_count,
        "untracked_count": git.untracked_count,
        "package_managers": package_managers,
        "test_commands": suggest_test_commands(workspace, package_managers),
        "dev_commands": suggest_dev_commands(workspace, package_managers),
        "build_commands": suggest_build_commands(workspace, package_managers),
        "entrypoints": detect_entrypoints(workspace, package_managers),
        "source_roots": detect_source_roots(workspace),
        "scope_candidates": detect_scope_candidates(workspace),
        "docs_found": detect_docs(workspace),
    }
    fields: list[str] = []
    for field_name, live_value in live_values.items():
        if getattr(intake, field_name) != live_value:
            fields.append(field_name)
    return tuple(fields)


def load_project_intake(state_dir: Path) -> ProjectIntake | None:
    """Load persisted project intake JSON from Trinity state."""
    path = state_dir.expanduser() / PROJECT_INTAKE_JSON
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid project intake JSON: {path}") from exc
    except OSError as exc:
        raise ValueError(f"Could not read project intake JSON: {path}") from exc
    if not isinstance(data, Mapping):
        raise ValueError(f"Invalid project intake JSON: {path}")
    return project_intake_from_dict(data)


def project_intake_from_dict(data: Mapping[str, Any]) -> ProjectIntake:
    """Build a project intake value from persisted JSON data."""
    try:
        mode = _normalize_mode(str(data["mode"]))
        target_workspace = Path(str(data["target_workspace"]))
    except KeyError as exc:
        raise ValueError(f"Missing project intake field: {exc.args[0]}") from exc
    return ProjectIntake(
        mode=mode,
        target_workspace=target_workspace,
        created_at=str(data.get("created_at", "unknown")),
        git_repo=bool(data.get("git_repo", False)),
        branch=str(data.get("branch", "unknown")),
        dirty_count=_optional_int(data.get("dirty_count")),
        untracked_count=_optional_int(data.get("untracked_count")),
        package_managers=_string_tuple(data.get("package_managers")),
        test_commands=_string_tuple(data.get("test_commands")),
        dev_commands=_string_tuple(data.get("dev_commands")),
        build_commands=_string_tuple(data.get("build_commands")),
        entrypoints=_string_tuple(data.get("entrypoints")),
        source_roots=_string_tuple(data.get("source_roots")),
        scope_candidates=_string_tuple(data.get("scope_candidates")),
        selected_scope=str(data.get("selected_scope", "")).strip(),
        docs_found=_string_tuple(data.get("docs_found")),
        product_goal=str(data.get("product_goal", "")),
        project_type=str(data.get("project_type", "")),
        starter_profile=str(data.get("starter_profile", "")),
        target_users=str(data.get("target_users", "")),
        success_criteria=str(data.get("success_criteria", "")),
        stack_preferences=_string_tuple(data.get("stack_preferences")),
        first_milestone=str(data.get("first_milestone", "")),
        constraints=_string_tuple(data.get("constraints")),
        notes=str(data.get("notes", "")),
    )


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
    guidance = project_intake_guidance_block(state_dir)
    sections = ["Project Intake Context:"]
    if guidance:
        sections.append(guidance)
    sections.append(markdown)
    return "\n".join(sections)


def project_intake_guidance_block(state_dir: Path) -> str:
    """Return mode-specific guidance derived from persisted intake JSON."""
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return ""
    if intake is None:
        return ""
    if intake.mode == "new":
        lines = [
            "Project Intake Guidance:",
            "- Treat the target workspace as a fresh project workspace.",
            *_new_project_brief_guidance_lines(intake),
            "- Prefer the recorded dev/build/test commands when planning validation.",
        ]
    else:
        lines = [
            "Project Intake Guidance:",
            "- Treat the target workspace as the existing project under discussion.",
            "- Read detected docs, entrypoints, and source roots before proposing edits.",
            *_existing_project_scope_guidance_lines(intake),
            *_existing_project_brief_guidance_lines(intake),
            "- Prefer the recorded dev/build/test commands when planning validation.",
        ]
    return "\n".join(lines)


def _new_project_brief_guidance_lines(intake: ProjectIntake) -> list[str]:
    missing = missing_new_project_brief_fields(intake)
    starter_profile = intake.starter_profile.strip()
    if missing:
        lines = [
            (
                "- The new-project brief is incomplete; confirm missing fields "
                f"before scaffolding: {_csv_or_none(missing)}."
            ),
            (
                "- Do not treat framework, architecture, or UX choices as final "
                "until the missing brief fields are answered."
            ),
        ]
        if starter_profile:
            lines.append(
                f"- Use the recorded starter profile as the initial project shape: {starter_profile}."
            )
        return lines
    lines = [
        (
            "- The new-project brief is complete; use the recorded goal, type, "
            "users, success criteria, stack, and milestone as planning constraints."
        ),
        (
            "- Prefer concrete scaffolding steps only after the plan preserves "
            "the recorded success criteria and constraints."
        ),
    ]
    if starter_profile:
        lines.append(
            f"- Use the recorded starter profile as the initial project shape: {starter_profile}."
        )
    return lines


def _existing_project_brief_guidance_lines(intake: ProjectIntake) -> list[str]:
    if not _has_project_brief_context(intake):
        return []
    return [
        (
            "- Use recorded brief fields as user intent, but verify them against "
            "the existing docs and source before proposing edits."
        )
    ]


def _existing_project_scope_guidance_lines(intake: ProjectIntake) -> list[str]:
    lines: list[str] = []
    selected_scope = intake.selected_scope.strip()
    if selected_scope:
        lines.append(
            (
                "- Treat the selected scope as the primary work area for this "
                f"conversation: {selected_scope}."
            )
        )
    if intake.scope_candidates:
        lines.append(
            (
                "- Detected possible subproject scopes; confirm the intended scope "
                f"before broad edits: {_csv_or_none(intake.scope_candidates)}."
            )
        )
    return lines


def _has_project_brief_context(intake: ProjectIntake) -> bool:
    return any(
        (
            intake.product_goal.strip(),
            intake.project_type.strip(),
            intake.starter_profile.strip(),
            intake.target_users.strip(),
            intake.success_criteria.strip(),
            intake.stack_preferences,
            intake.first_milestone.strip(),
            intake.constraints,
            intake.notes.strip(),
        )
    )


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


def suggest_dev_commands(
    path: Path,
    package_managers: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Suggest likely local development commands without executing them."""
    workspace = _safe_resolve(path)
    managers = package_managers or detect_package_managers(workspace)
    commands: list[str] = []
    node_scripts = _node_scripts(workspace)
    node_runner = _node_runner(managers)
    for script in ("dev", "start"):
        if script in node_scripts and node_runner:
            commands.append(f"{node_runner} {script}")
    if (workspace / "manage.py").exists():
        commands.append("python manage.py runserver")
    elif (workspace / "app.py").exists():
        commands.append("python app.py")
    if "cargo" in managers:
        commands.append("cargo run")
    if "go" in managers:
        commands.append("go run ./...")
    return tuple(dict.fromkeys(commands))


def suggest_build_commands(
    path: Path,
    package_managers: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Suggest likely build/package commands without executing them."""
    workspace = _safe_resolve(path)
    managers = package_managers or detect_package_managers(workspace)
    commands: list[str] = []
    node_scripts = _node_scripts(workspace)
    node_runner = _node_runner(managers)
    if "build" in node_scripts and node_runner:
        commands.append(f"{node_runner} build")
    if (workspace / "pyproject.toml").exists() and _pyproject_has_build_backend(
        workspace
    ):
        commands.append("python -m build")
    if "cargo" in managers:
        commands.append("cargo build")
    if "go" in managers:
        commands.append("go build ./...")
    if "maven" in managers:
        commands.append("mvn package")
    if "gradle" in managers:
        commands.append("./gradlew build")
    return tuple(dict.fromkeys(commands))


def detect_entrypoints(
    path: Path,
    package_managers: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Detect likely user-facing entrypoints for the target workspace."""
    workspace = _safe_resolve(path)
    managers = package_managers or detect_package_managers(workspace)
    entries: list[str] = []
    pyproject = _read_toml(workspace / "pyproject.toml")
    project = pyproject.get("project", {})
    if isinstance(project, Mapping):
        scripts = project.get("scripts", {})
        if isinstance(scripts, Mapping):
            for name, target in sorted(scripts.items()):
                entries.append(f"{name} -> {target}")
    for filename in ("main.py", "app.py", "cli.py", "manage.py"):
        if (workspace / filename).exists():
            entries.append(filename)
    package_json = _read_package_json(workspace)
    main = package_json.get("main")
    if isinstance(main, str) and main.strip():
        entries.append(main.strip())
    bin_entries = package_json.get("bin")
    if isinstance(bin_entries, str) and bin_entries.strip():
        entries.append(bin_entries.strip())
    elif isinstance(bin_entries, Mapping):
        for name, target in sorted(bin_entries.items()):
            entries.append(f"{name} -> {target}")
    if "cargo" in managers and (workspace / "src" / "main.rs").exists():
        entries.append("src/main.rs")
    if "go" in managers:
        for candidate in ("main.go", "cmd"):
            if (workspace / candidate).exists():
                entries.append(candidate)
    return tuple(dict.fromkeys(str(entry) for entry in entries if str(entry).strip()))


def detect_source_roots(path: Path) -> tuple[str, ...]:
    """Detect common source and test roots for orientation prompts."""
    workspace = _safe_resolve(path)
    roots: list[str] = []
    for name in (
        "src",
        "app",
        "lib",
        "packages",
        "cmd",
        "internal",
        "crates",
        "tests",
        "test",
    ):
        if (workspace / name).is_dir():
            roots.append(name)
    return tuple(roots)


def detect_scope_candidates(path: Path) -> tuple[str, ...]:
    """Detect likely monorepo/package scope candidates without executing code."""
    workspace = _safe_resolve(path)
    candidates: list[str] = []
    candidates.extend(_node_workspace_scope_candidates(workspace))
    for parent_name in SCOPE_PARENT_DIRS:
        parent = workspace / parent_name
        if not parent.is_dir():
            continue
        try:
            children = sorted(parent.iterdir(), key=lambda child: child.name)
        except OSError:
            continue
        for child in children:
            if not child.is_dir() or child.name.startswith("."):
                continue
            if _looks_like_scope_candidate(child):
                candidates.append(_relative_scope_candidate(workspace, child))
    return tuple(dict.fromkeys(candidate for candidate in candidates if candidate))


def detect_docs(path: Path) -> tuple[str, ...]:
    """Detect documentation files and folders worth reading first."""
    workspace = _safe_resolve(path)
    docs: list[str] = []
    for name in (
        "README.md",
        "README.en.md",
        "README.ko.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "docs",
    ):
        if (workspace / name).exists():
            docs.append(name)
    return tuple(docs)


def _node_workspace_scope_candidates(workspace: Path) -> tuple[str, ...]:
    data = _read_package_json(workspace)
    raw_workspaces = data.get("workspaces")
    patterns: list[str] = []
    if isinstance(raw_workspaces, list):
        patterns.extend(str(item) for item in raw_workspaces)
    elif isinstance(raw_workspaces, Mapping):
        packages = raw_workspaces.get("packages")
        if isinstance(packages, list):
            patterns.extend(str(item) for item in packages)
    candidates: list[str] = []
    for pattern in patterns:
        candidates.extend(_scope_candidates_from_workspace_pattern(workspace, pattern))
    return tuple(dict.fromkeys(candidate for candidate in candidates if candidate))


def _scope_candidates_from_workspace_pattern(
    workspace: Path,
    pattern: str,
) -> tuple[str, ...]:
    clean = pattern.strip().strip("/")
    if not clean or ".." in Path(clean).parts:
        return ()
    if clean.endswith("/*"):
        parent = workspace / clean[:-2]
        if not parent.is_dir():
            return ()
        candidates: list[str] = []
        try:
            children = sorted(parent.iterdir(), key=lambda child: child.name)
        except OSError:
            return ()
        for child in children:
            if child.is_dir() and _looks_like_scope_candidate(child):
                candidates.append(_relative_scope_candidate(workspace, child))
        return tuple(candidates)
    candidate = workspace / clean
    if candidate.is_dir() and _looks_like_scope_candidate(candidate):
        return (_relative_scope_candidate(workspace, candidate),)
    return ()


def _looks_like_scope_candidate(path: Path) -> bool:
    return any((path / manifest).exists() for manifest in SCOPE_MANIFEST_FILES)


def _relative_scope_candidate(workspace: Path, path: Path) -> str:
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError:
        return ""


def _node_test_command(path: Path, managers: tuple[str, ...]) -> str:
    scripts = _node_scripts(path)
    if "test" not in scripts:
        return ""
    if "pnpm" in managers:
        return "pnpm test"
    if "yarn" in managers:
        return "yarn test"
    return "npm test"


def _node_runner(managers: tuple[str, ...]) -> str:
    if "pnpm" in managers:
        return "pnpm"
    if "yarn" in managers:
        return "yarn"
    if "npm" in managers:
        return "npm run"
    return ""


def _node_scripts(path: Path) -> Mapping[str, Any]:
    data = _read_package_json(path)
    scripts = data.get("scripts", {})
    return scripts if isinstance(scripts, Mapping) else {}


def _read_package_json(path: Path) -> Mapping[str, Any]:
    package_json = path / "package.json"
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, Mapping) else {}


def _pyproject_has_build_backend(path: Path) -> bool:
    data = _read_toml(path / "pyproject.toml")
    build_system = data.get("build-system", {})
    return isinstance(build_system, Mapping) and bool(build_system.get("build-backend"))


def _read_toml(path: Path) -> Mapping[str, Any]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return data if isinstance(data, Mapping) else {}


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


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return _normalize_string_tuple(value)


def _normalize_string_tuple(value: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    items: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            items.append(text)
    return tuple(dict.fromkeys(items))
