"""Workspace isolation — git-worktree creation and management.

Each agent gets its own git worktree so they can work on files
independently without stepping on each other's changes.

Directory layout:
    .trinity/workspace/
        <agent-name>/     ← worktree root (branch: trinity/<agent-name>)
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class WorkspaceIsolation:
    """Manages per-agent git worktrees for file-level isolation.

    Usage:
        wi = WorkspaceIsolation(project_root=Path("."))
        worktree_path = wi.create("claude")
        # agent works in worktree_path ...
        wi.cleanup("claude")  # remove when done
    """

    def __init__(self, project_root: Path, state_dir: Path | None = None):
        """
        Args:
            project_root: The git repository root.
            state_dir: Where worktrees live. Defaults to project_root/.trinity/workspace.
        """
        self.project_root = project_root.resolve()
        self.workspace_root = (state_dir or project_root / ".trinity" / "workspace").resolve()

    def _branch_name(self, agent_name: str) -> str:
        """Generate branch name for an agent."""
        return f"trinity/{agent_name}"

    def _worktree_path(self, agent_name: str) -> Path:
        """Return the worktree directory path for an agent."""
        return self.workspace_root / agent_name

    def _run_git(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        """Run a git command."""
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd or self.project_root,
            timeout=30,
        )

    def create(self, agent_name: str, base_ref: str = "HEAD") -> Path:
        """Create a git worktree for the given agent.

        Args:
            agent_name: Unique agent identifier.
            base_ref: Git ref to branch from (default: HEAD).

        Returns:
            Path to the worktree directory.

        Raises:
            WorkspaceError: If worktree creation fails.
        """
        worktree_path = self._worktree_path(agent_name)
        branch_name = self._branch_name(agent_name)

        if worktree_path.exists():
            logger.info(f"Worktree already exists for '{agent_name}': {worktree_path}")
            return worktree_path

        # Create branch from base_ref
        result = self._run_git("branch", branch_name, base_ref)
        if result.returncode != 0:
            # Branch might already exist — that's okay
            if "already exists" not in result.stderr:
                raise WorkspaceError(
                    f"Failed to create branch '{branch_name}': {result.stderr.strip()}"
                )
            logger.debug(f"Branch '{branch_name}' already exists, reusing")

        # Create worktree
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        result = self._run_git(
            "worktree", "add", str(worktree_path), branch_name,
        )
        if result.returncode != 0:
            raise WorkspaceError(
                f"Failed to create worktree for '{agent_name}': {result.stderr.strip()}"
            )

        logger.info(f"Created worktree for '{agent_name}': {worktree_path}")
        return worktree_path

    def cleanup(self, agent_name: str) -> bool:
        """Remove the worktree and branch for the given agent.

        Args:
            agent_name: Agent whose workspace to remove.

        Returns:
            True if cleanup succeeded.
        """
        worktree_path = self._worktree_path(agent_name)
        branch_name = self._branch_name(agent_name)
        success = True

        # Remove worktree
        if worktree_path.exists():
            result = self._run_git("worktree", "remove", str(worktree_path), "--force")
            if result.returncode != 0:
                logger.warning(f"Failed to remove worktree: {result.stderr.strip()}")
                success = False
            else:
                logger.info(f"Removed worktree for '{agent_name}'")

        # Delete branch
        result = self._run_git("branch", "-D", branch_name)
        if result.returncode != 0:
            logger.debug(f"Branch '{branch_name}' deletion note: {result.stderr.strip()}")
        else:
            logger.info(f"Deleted branch '{branch_name}'")

        return success

    def exists(self, agent_name: str) -> bool:
        """Check if a worktree exists for the given agent."""
        return self._worktree_path(agent_name).exists()

    def list_worktrees(self) -> dict[str, Path]:
        """List all agent worktrees.

        Returns:
            Dict mapping agent_name → worktree_path.
        """
        result = {}
        if not self.workspace_root.exists():
            return result

        for path in self.workspace_root.iterdir():
            if path.is_dir() and (path / ".git").exists():
                result[path.name] = path

        return result

    def get_worktree(self, agent_name: str) -> Path | None:
        """Get the worktree path for an agent, or None if not created."""
        path = self._worktree_path(agent_name)
        return path if path.exists() else None

    def has_changes(self, agent_name: str) -> bool:
        """Check if the worktree has uncommitted changes."""
        worktree_path = self._worktree_path(agent_name)
        if not worktree_path.exists():
            return False

        result = self._run_git("status", "--porcelain", cwd=worktree_path)
        return bool(result.stdout.strip())

    def get_diff(self, agent_name: str) -> str:
        """Get the diff of uncommitted changes in the worktree."""
        worktree_path = self._worktree_path(agent_name)
        if not worktree_path.exists():
            return ""

        result = self._run_git("diff", cwd=worktree_path)
        return result.stdout

    def merge_back(self, agent_name: str, target_branch: str = "main") -> bool:
        """Merge the agent's branch back to a target branch.

        Args:
            agent_name: Agent whose work to merge.
            target_branch: Branch to merge into (default: main).

        Returns:
            True if merge succeeded.
        """
        branch_name = self._branch_name(agent_name)
        result = self._run_git("merge", branch_name, "--no-edit")
        if result.returncode != 0:
            # Abort merge on conflict
            self._run_git("merge", "--abort")
            logger.error(f"Merge failed for '{agent_name}': {result.stderr.strip()}")
            return False

        logger.info(f"Merged '{branch_name}' into '{target_branch}'")
        return True

    def cleanup_all(self) -> int:
        """Remove all worktrees and branches. Returns count cleaned."""
        worktrees = self.list_worktrees()
        count = 0
        for name in list(worktrees.keys()):
            if self.cleanup(name):
                count += 1
        return count


class WorkspaceError(Exception):
    """Error in workspace operations."""
    pass
