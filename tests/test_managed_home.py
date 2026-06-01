"""Tests for trinity.workspace.managed_home — ManagedHome."""

import pytest
from pathlib import Path

from trinity.workspace.managed_home import ManagedHome


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def state_dir(tmp_path):
    return tmp_path / ".trinity"


@pytest.fixture
def mh(state_dir):
    return ManagedHome(state_dir=state_dir)


# ===========================================================================
# Setup
# ===========================================================================

class TestSetup:
    def test_creates_home_directory(self, mh, state_dir):
        home = mh.setup("claude")
        assert home.exists()
        assert home == state_dir / "agents" / "claude" / "provider-state"

    def test_creates_provider_dirs(self, mh):
        home = mh.setup("claude", provider="claude-code")
        assert (home / ".claude").exists()

    def test_creates_codex_dirs(self, mh):
        home = mh.setup("codex", provider="codex")
        assert (home / ".codex").exists()

    def test_creates_gemini_dirs(self, mh):
        home = mh.setup("gemini", provider="gemini-cli")
        assert (home / ".config").exists()
        assert (home / ".config" / "gemini").exists()

    def test_idempotent(self, mh):
        """setup을 두 번 호출해도 에러 없음."""
        mh.setup("claude")
        mh.setup("claude")
        assert mh.exists("claude")

    def test_without_provider(self, mh):
        """provider 없이 호출하면 빈 홈만 생성."""
        home = mh.setup("agent1")
        assert home.exists()
        # No provider-specific subdirs
        assert not (home / ".claude").exists()


# ===========================================================================
# Query
# ===========================================================================

class TestQuery:
    def test_get_home_none_when_not_exists(self, mh):
        assert mh.get_home("nonexistent") is None

    def test_get_home_returns_path(self, mh):
        mh.setup("claude")
        home = mh.get_home("claude")
        assert home is not None
        assert home.exists()

    def test_exists_false(self, mh):
        assert mh.exists("ghost") is False

    def test_exists_true(self, mh):
        mh.setup("claude")
        assert mh.exists("claude") is True

    def test_list_agents_empty(self, mh):
        assert mh.list_agents() == []

    def test_list_agents_returns_names(self, mh):
        mh.setup("claude")
        mh.setup("codex")
        mh.setup("gemini")
        assert sorted(mh.list_agents()) == ["claude", "codex", "gemini"]


# ===========================================================================
# Environment overrides
# ===========================================================================

class TestEnvOverrides:
    def test_returns_empty_when_no_home(self, mh):
        assert mh.get_env_overrides("nonexistent") == {}

    def test_includes_home(self, mh):
        mh.setup("claude")
        env = mh.get_env_overrides("claude")
        assert "HOME" in env
        assert "provider-state" in env["HOME"]

    def test_includes_xdg_dirs(self, mh):
        mh.setup("claude")
        env = mh.get_env_overrides("claude")
        assert "XDG_CONFIG_HOME" in env
        assert "XDG_DATA_HOME" in env
        assert "XDG_CACHE_HOME" in env

    def test_xdg_paths_inside_home(self, mh):
        home = mh.setup("claude")
        env = mh.get_env_overrides("claude")
        assert env["XDG_CONFIG_HOME"] == str(home / ".config")


# ===========================================================================
# Config file operations
# ===========================================================================

class TestConfigIO:
    def test_write_and_read_config(self, mh):
        mh.setup("claude")
        path = mh.write_config("claude", ".claude/settings.json", '{"theme":"dark"}')
        assert path.exists()

        content = mh.read_config("claude", ".claude/settings.json")
        assert content == '{"theme":"dark"}'

    def test_read_nonexistent_returns_none(self, mh):
        mh.setup("claude")
        assert mh.read_config("claude", "nope.txt") is None

    def test_write_creates_parent_dirs(self, mh):
        mh.setup("codex")
        path = mh.write_config("codex", "deep/nested/config.toml", "key = 'value'")
        assert path.exists()
        assert path.read_text() == "key = 'value'"

    def test_overwrites_existing(self, mh):
        mh.setup("gemini")
        mh.write_config("gemini", "config.txt", "old")
        mh.write_config("gemini", "config.txt", "new")
        assert mh.read_config("gemini", "config.txt") == "new"


# ===========================================================================
# Cleanup
# ===========================================================================

class TestCleanup:
    def test_removes_home(self, mh):
        mh.setup("claude")
        assert mh.exists("claude")

        result = mh.cleanup("claude")
        assert result is True
        assert not mh.exists("claude")

    def test_returns_true_when_no_home(self, mh):
        result = mh.cleanup("nonexistent")
        assert result is True

    def test_cleanup_all(self, mh):
        mh.setup("claude")
        mh.setup("codex")

        count = mh.cleanup_all()
        assert count == 2
        assert mh.list_agents() == []

    def test_cleanup_all_empty(self, mh):
        count = mh.cleanup_all()
        assert count == 0


# ===========================================================================
# Disk usage
# ===========================================================================

class TestDiskUsage:
    def test_zero_when_no_home(self, mh):
        assert mh.get_disk_usage("nonexistent") == 0

    def test_counts_files(self, mh):
        home = mh.setup("claude")
        (home / "test.txt").write_text("hello world")
        usage = mh.get_disk_usage("claude")
        assert usage > 0

    def test_nested_files(self, mh):
        home = mh.setup("codex")
        nested = home / "deep" / "dir"
        nested.mkdir(parents=True)
        (nested / "file.txt").write_text("content")
        assert mh.get_disk_usage("codex") > 0
