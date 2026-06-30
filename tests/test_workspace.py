"""Tests for trinity.workspace.isolation — WorkspaceIsolation."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from trinity.workspace.isolation import WorkspaceIsolation, WorkspaceError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project_root(tmp_path):
    """Create a fake git repo root."""
    root = tmp_path / "project"
    root.mkdir()
    (root / ".git").mkdir()
    return root


@pytest.fixture
def state_dir(tmp_path):
    return tmp_path / "state" / "workspace"


@pytest.fixture
def wi(project_root, state_dir):
    return WorkspaceIsolation(project_root=project_root, state_dir=state_dir)


def _mock_git_success(stdout="", stderr=""):
    """Return a mock for a successful git command."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = stdout
    result.stderr = stderr
    return result


def _mock_git_failure(stderr="error"):
    """Return a mock for a failed git command."""
    result = MagicMock()
    result.returncode = 1
    result.stdout = ""
    result.stderr = stderr
    return result


# ===========================================================================
# Branch name generation
# ===========================================================================

class TestBranchName:
    def test_format(self, wi):
        assert wi.branch_name("claude") == "trinity/claude"

    def test_with_hyphen(self, wi):
        assert wi.branch_name("code-reviewer") == "trinity/code-reviewer"


# ===========================================================================
# Worktree path
# ===========================================================================

class TestWorktreePath:
    def test_path_format(self, wi):
        path = wi._worktree_path("claude")
        assert path.name == "claude"
        assert "workspace" in str(path)


# ===========================================================================
# Create worktree
# ===========================================================================

class TestCreate:
    def test_creates_branch_and_worktree(self, wi):
        with patch.object(wi, "_run_git") as mock_git:
            mock_git.side_effect = [
                _mock_git_success(),  # git branch
                _mock_git_success(),  # git worktree add
            ]
            path = wi.create("claude")

        assert path == wi._worktree_path("claude")

    def test_reuses_existing_branch(self, wi):
        """이미 존재하는 브랜치는 재사용."""
        with patch.object(wi, "_run_git") as mock_git:
            mock_git.side_effect = [
                _mock_git_failure("already exists"),  # git branch → already exists
                _mock_git_success(),                   # git worktree add
            ]
            path = wi.create("codex")

        assert path == wi._worktree_path("codex")

    def test_raises_on_branch_failure(self, wi):
        """브랜치 생성 실패 시 WorkspaceError."""
        with patch.object(wi, "_run_git") as mock_git:
            mock_git.return_value = _mock_git_failure("fatal: not a git repo")

            with pytest.raises(WorkspaceError, match="Failed to create branch"):
                wi.create("antigravity")

    def test_raises_on_worktree_failure(self, wi):
        """worktree add 실패 시 WorkspaceError."""
        with patch.object(wi, "_run_git") as mock_git:
            mock_git.side_effect = [
                _mock_git_success(),                   # git branch
                _mock_git_failure("worktree exists"),  # git worktree add
            ]

            with pytest.raises(WorkspaceError, match="Failed to create worktree"):
                wi.create("claude")

    def test_returns_existing_path_if_exists(self, wi):
        """worktree 디렉토리가 이미 존재하면 경로만 반환."""
        worktree_path = wi._worktree_path("claude")
        worktree_path.mkdir(parents=True)

        path = wi.create("claude")
        assert path == worktree_path

    def test_uses_custom_base_ref(self, wi):
        """base_ref 파라미터가 git branch 명령에 전달됨."""
        with patch.object(wi, "_run_git") as mock_git:
            mock_git.side_effect = [
                _mock_git_success(),
                _mock_git_success(),
            ]
            wi.create("claude", base_ref="v1.0")

        mock_git.assert_any_call("branch", "trinity/claude", "v1.0")


# ===========================================================================
# Cleanup
# ===========================================================================

class TestCleanup:
    def test_removes_worktree_and_branch(self, wi):
        with patch.object(wi, "_run_git") as mock_git:
            mock_git.side_effect = [
                _mock_git_success(),  # git worktree remove
                _mock_git_success(),  # git branch -D
            ]
            result = wi.cleanup("claude")

        assert result is True

    def test_handles_nonexistent_worktree(self, wi):
        """worktree가 없어도 cleanup은 성공."""
        with patch.object(wi, "_run_git") as mock_git:
            mock_git.side_effect = [
                _mock_git_success(),  # git worktree remove (not exist)
                _mock_git_success(),  # git branch -D
            ]
            result = wi.cleanup("nonexistent")

        assert result is True

    def test_returns_false_on_remove_failure(self, wi):
        worktree_path = wi._worktree_path("claude")
        worktree_path.mkdir(parents=True)

        with patch.object(wi, "_run_git") as mock_git:
            mock_git.side_effect = [
                _mock_git_failure("locked"),  # git worktree remove fails
                _mock_git_success(),          # git branch -D
            ]
            result = wi.cleanup("claude")

        assert result is False


# ===========================================================================
# Exists / List / Get
# ===========================================================================

class TestQuery:
    def test_exists_false(self, wi):
        assert wi.exists("claude") is False

    def test_exists_true(self, wi):
        wi._worktree_path("claude").mkdir(parents=True)
        # Need .git marker for list_worktrees
        (wi._worktree_path("claude") / ".git").mkdir()
        assert wi.exists("claude") is True

    def test_list_worktrees_empty(self, wi):
        assert wi.list_worktrees() == {}

    def test_list_worktrees_returns_existing(self, wi):
        for name in ["claude", "codex"]:
            path = wi._worktree_path(name)
            path.mkdir(parents=True)
            (path / ".git").mkdir()

        result = wi.list_worktrees()
        assert set(result.keys()) == {"claude", "codex"}

    def test_get_worktree_none(self, wi):
        assert wi.get_worktree("nonexistent") is None

    def test_get_worktree_returns_path(self, wi):
        path = wi._worktree_path("claude")
        path.mkdir(parents=True)
        assert wi.get_worktree("claude") == path


# ===========================================================================
# Has changes / Diff
# ===========================================================================

class TestChanges:
    def test_has_changes_false_when_no_worktree(self, wi):
        assert wi.has_changes("claude") is False

    def test_has_changes_with_dirty_worktree(self, wi):
        wi._worktree_path("claude").mkdir(parents=True)
        with patch.object(wi, "_run_git") as mock_git:
            mock_git.return_value = _mock_git_success(stdout="M file.py\n")
            assert wi.has_changes("claude") is True

    def test_has_changes_with_clean_worktree(self, wi):
        wi._worktree_path("claude").mkdir(parents=True)
        with patch.object(wi, "_run_git") as mock_git:
            mock_git.return_value = _mock_git_success(stdout="")
            assert wi.has_changes("claude") is False

    def test_get_diff_empty_when_no_worktree(self, wi):
        assert wi.get_diff("nonexistent") == ""

    def test_get_diff_returns_output(self, wi):
        wi._worktree_path("claude").mkdir(parents=True)
        with patch.object(wi, "_run_git") as mock_git:
            mock_git.return_value = _mock_git_success(stdout="diff content here")
            assert wi.get_diff("claude") == "diff content here"


# ===========================================================================
# Merge back
# ===========================================================================

class TestMergeBack:
    def test_merge_success(self, wi):
        with patch.object(wi, "_run_git") as mock_git:
            mock_git.return_value = _mock_git_success()
            result = wi.merge_back("claude")

        assert result is True
        mock_git.assert_called_with("merge", "trinity/claude", "--no-edit")

    def test_merge_conflict_aborts(self, wi):
        with patch.object(wi, "_run_git") as mock_git:
            mock_git.side_effect = [
                _mock_git_failure("CONFLICT"),  # git merge fails
                _mock_git_success(),             # git merge --abort
            ]
            result = wi.merge_back("claude")

        assert result is False


# ===========================================================================
# Cleanup all
# ===========================================================================

class TestCleanupAll:
    def test_cleans_all_worktrees(self, wi):
        with patch.object(wi, "cleanup") as mock_cleanup:
            mock_cleanup.return_value = True
            # Create fake worktree dirs
            for name in ["claude", "codex"]:
                path = wi._worktree_path(name)
                path.mkdir(parents=True)
                (path / ".git").mkdir()

            count = wi.cleanup_all()
        assert count == 2

    def test_empty_workspace(self, wi):
        count = wi.cleanup_all()
        assert count == 0
