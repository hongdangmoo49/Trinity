"""Tests for trinity.cli — CLI commands."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from trinity.cli import (
    _configure_stdio_encoding_errors,
    _maybe_run_startup_update,
    _resolve_init_project_mode,
    main,
    load_config,
    find_config_path,
)
from trinity.context.analytics import RoundRecord, TokenAnalytics, analytics_history_path
from trinity.models import Provider
from trinity.updater import StartupUpdate, StartupUpdateResult


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def trinity_project(tmp_path):
    """Create a minimal trinity project directory."""
    state = tmp_path / ".trinity"
    state.mkdir()
    (state / "agents" / "claude").mkdir(parents=True)
    (state / "agents" / "codex").mkdir(parents=True)
    (state / "agents" / "antigravity").mkdir(parents=True)
    (state / "history").mkdir()
    (state / "logs").mkdir()
    (state / "workspace").mkdir()
    (state / "shared.md").write_text(
        "# Shared Context\n\n## Current Goal\nTest goal\n", encoding="utf-8"
    )
    (state / "trinity.config").write_text(
        '[general]\nsession_name = "test"\n\n'
        '[agents.claude]\nprovider = "claude-code"\ncli_command = "claude"\nenabled = true\n',
        encoding="utf-8",
    )
    return tmp_path


def _run_git(path: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


class TestVersion:
    def test_version_flag(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert __import__("trinity").__version__ in result.output


class TestInteractiveEntrypoint:
    def test_default_launches_textual_workbench(self, runner, trinity_project):
        config_path = trinity_project / ".trinity" / "trinity.config"
        with patch("trinity.cli.find_config_path", return_value=config_path):
            with patch("trinity.textual_app.app.run_textual_app") as run_textual:
                result = runner.invoke(main, [])

        assert result.exit_code == 0
        run_textual.assert_called_once()

    def test_plain_flag_launches_legacy_tui(self, runner, trinity_project):
        config_path = trinity_project / ".trinity" / "trinity.config"
        with patch("trinity.cli.find_config_path", return_value=config_path):
            with patch("trinity.tui.session.InteractiveSession") as session_cls:
                result = runner.invoke(main, ["--plain"])

        assert result.exit_code == 0
        session_cls.assert_called_once()
        session_cls.return_value.run.assert_called_once()

    def test_plain_environment_launches_legacy_tui(self, runner, trinity_project):
        config_path = trinity_project / ".trinity" / "trinity.config"
        with patch("trinity.cli.find_config_path", return_value=config_path):
            with patch("trinity.tui.session.InteractiveSession") as session_cls:
                result = runner.invoke(main, [], env={"TRINITY_TUI": "plain"})

        assert result.exit_code == 0
        session_cls.assert_called_once()
        session_cls.return_value.run.assert_called_once()

    def test_textual_unavailable_falls_back_to_legacy_tui(self, runner, trinity_project):
        from trinity.textual_app.runtime import TuiRuntimeMode

        config_path = trinity_project / ".trinity" / "trinity.config"
        runtime = TuiRuntimeMode(
            requested="auto",
            selected="plain",
            textual_available=False,
            reason="textual-unavailable",
        )
        with patch("trinity.cli.find_config_path", return_value=config_path):
            with patch("trinity.cli.resolve_tui_runtime", return_value=runtime):
                with patch("trinity.tui.session.InteractiveSession") as session_cls:
                    result = runner.invoke(main, [])

        assert result.exit_code == 0
        session_cls.assert_called_once()
        session_cls.return_value.run.assert_called_once()


class TestStartupUpdatePrompt:
    def _update(self, tmp_path: Path) -> StartupUpdate:
        return StartupUpdate(
            source="git",
            current_version="0.11.1",
            latest_version="0.12.0",
            detail="origin/main has 1 new commit.",
            repo_root=tmp_path,
            upstream="origin/main",
            behind_count=1,
            command=("git", "-C", str(tmp_path), "pull", "--ff-only"),
        )

    def test_startup_update_skips_when_not_interactive(self):
        with patch("trinity.cli._stdio_is_interactive", return_value=False):
            with patch("trinity.cli.check_for_startup_update") as check:
                assert _maybe_run_startup_update() is False

        check.assert_not_called()

    def test_startup_update_decline_continues_current_version(self, tmp_path):
        update = self._update(tmp_path)
        with patch("trinity.cli._stdio_is_interactive", return_value=True):
            with patch("trinity.cli.startup_update_check_disabled", return_value=False):
                with patch("trinity.cli._startup_update_lang", return_value="en"):
                    with patch("trinity.cli.check_for_startup_update", return_value=update):
                        with patch("trinity.cli.Confirm.ask", return_value=False):
                            with patch("trinity.cli.apply_startup_update") as apply:
                                assert _maybe_run_startup_update() is False

        apply.assert_not_called()

    def test_startup_update_accept_applies_and_exits(self, tmp_path):
        update = self._update(tmp_path)
        result = StartupUpdateResult(True, "done", "pulled")
        with patch("trinity.cli._stdio_is_interactive", return_value=True):
            with patch("trinity.cli.startup_update_check_disabled", return_value=False):
                with patch("trinity.cli._startup_update_lang", return_value="ko"):
                    with patch("trinity.cli.check_for_startup_update", return_value=update):
                        with patch("trinity.cli.Confirm.ask", return_value=True):
                            with patch(
                                "trinity.cli.apply_startup_update",
                                return_value=result,
                            ) as apply:
                                assert _maybe_run_startup_update() is True

        apply.assert_called_once_with(update)


class TestOutputEncoding:
    def test_configure_stdio_encoding_errors_uses_replacement(self):
        class FakeStream:
            def __init__(self):
                self.kwargs = None

            def reconfigure(self, **kwargs):
                self.kwargs = kwargs

        stdout = FakeStream()
        stderr = FakeStream()

        _configure_stdio_encoding_errors(stdout, stderr)

        assert stdout.kwargs == {"errors": "replace"}
        assert stderr.kwargs == {"errors": "replace"}

    def test_configure_stdio_encoding_errors_ignores_unsupported_streams(self):
        _configure_stdio_encoding_errors(object())


class TestInit:
    def test_init_creates_structure(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init", "--non-interactive"])
            assert result.exit_code == 0

            # Check directory structure
            assert Path(".trinity").exists()
            assert Path(".trinity/trinity.config").exists()
            assert Path(".trinity/shared.md").exists()
            assert Path(".trinity/agents/claude/role.md").exists()
            assert Path(".trinity/agents/codex/role.md").exists()
            assert Path(".trinity/agents/antigravity/role.md").exists()
            assert Path(".trinity/history").exists()
            assert Path(".trinity/logs").exists()
            assert Path(".trinity/workspace").exists()
            assert not Path(".trinity/project-intake.json").exists()

    def test_init_shared_md_content(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init", "--non-interactive"])
            assert result.exit_code == 0

            shared = Path(".trinity/shared.md").read_text(encoding="utf-8")
            assert "Shared Context" in shared
            assert "Current Goal" in shared

    def test_init_adds_gitignore(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init", "--non-interactive"])
            assert result.exit_code == 0

            gitignore = Path(".gitignore").read_text(encoding="utf-8")
            assert ".trinity/" in gitignore

    def test_init_existing_without_force(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(main, ["init", "--non-interactive"])  # First init
            result = runner.invoke(main, ["init"])  # Second init without --force
            assert "already exists" in result.output

    def test_init_with_force(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(main, ["init", "--non-interactive"])  # First init
            result = runner.invoke(main, ["init", "--force", "--non-interactive"])  # Force re-init
            assert result.exit_code == 0
            assert "initialized" in result.output.lower() or "✓" in result.output

    def test_init_gitignore_no_duplicate(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(main, ["init", "--non-interactive"])
            runner.invoke(main, ["init", "--force", "--non-interactive"])

            gitignore = Path(".gitignore").read_text(encoding="utf-8")
            assert gitignore.count(".trinity/") == 1

    def test_init_mode_existing_writes_project_intake(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            cwd = Path.cwd()
            (cwd / "pyproject.toml").write_text(
                "[project]\nname='customer-app'\n",
                encoding="utf-8",
            )
            (cwd / "uv.lock").write_text("", encoding="utf-8")
            _run_git(cwd, "init")
            _run_git(cwd, "add", "pyproject.toml", "uv.lock")

            result = runner.invoke(
                main,
                ["init", "--non-interactive", "--mode", "existing"],
            )

            assert result.exit_code == 0
            assert "Project intake:" in result.output
            data = json.loads(
                Path(".trinity/project-intake.json").read_text(encoding="utf-8")
            )
            assert data["mode"] == "existing"
            assert data["target_workspace"] == str(cwd.resolve())
            assert data["dirty_count"] == 2
            assert data["untracked_count"] == 0
            assert data["package_managers"] == ["uv"]
            assert data["test_commands"] == ["uv run pytest"]

    def test_resolve_init_project_mode_prompt_policy(self):
        assert (
            _resolve_init_project_mode("new", lang="en", interactive=True)
            == "new"
        )
        assert _resolve_init_project_mode(None, lang="en", interactive=False) is None
        with patch("trinity.cli.Prompt.ask", return_value="existing") as ask:
            assert (
                _resolve_init_project_mode(None, lang="ko", interactive=True)
                == "existing"
            )
        ask.assert_called_once()


class TestProjectAnalyze:
    def test_project_new_requires_trinity_project(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["project", "new", "app"])

            assert result.exit_code == 1
            assert "No Trinity project found" in result.output
            assert not Path("app").exists()

    def test_project_new_creates_workspace_and_intake(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            init_result = runner.invoke(main, ["init", "--non-interactive"])
            assert init_result.exit_code == 0
            parent = Path("workspace")
            parent.mkdir()

            result = runner.invoke(
                main,
                [
                    "project",
                    "new",
                    "snake-game",
                    "--parent",
                    str(parent),
                    "--no-git",
                    "--notes",
                    "Build a terminal snake game.",
                ],
            )

            target = parent / "snake-game"
            assert result.exit_code == 0
            assert "New project workspace created." in result.output
            assert "Git init: skipped" in result.output
            assert "Next steps:" in result.output
            assert "trinity project status" in result.output
            assert target.is_dir()
            data = json.loads(
                Path(".trinity/project-intake.json").read_text(encoding="utf-8")
            )
            markdown = Path(".trinity/project-intake.md").read_text(encoding="utf-8")
            assert data["mode"] == "new"
            assert data["target_workspace"] == str(target.resolve())
            assert data["git_repo"] is False
            assert data["notes"] == "Build a terminal snake game."
            assert "Build a terminal snake game." in markdown

    def test_project_new_can_initialize_git_repository(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            init_result = runner.invoke(main, ["init", "--non-interactive"])
            assert init_result.exit_code == 0

            result = runner.invoke(main, ["project", "new", "git-app", "--git"])

            target = Path("git-app")
            assert result.exit_code == 0
            assert "Git init: initialized" in result.output
            assert (target / ".git").exists()
            data = json.loads(
                Path(".trinity/project-intake.json").read_text(encoding="utf-8")
            )
            assert data["mode"] == "new"
            assert data["target_workspace"] == str(target.resolve())
            assert data["git_repo"] is True

    def test_project_new_rejects_existing_or_nested_project_name(
        self,
        runner,
        tmp_path,
    ):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            init_result = runner.invoke(main, ["init", "--non-interactive"])
            assert init_result.exit_code == 0
            Path("existing").mkdir()

            existing_result = runner.invoke(main, ["project", "new", "existing"])
            nested_result = runner.invoke(main, ["project", "new", "apps/new"])

            assert existing_result.exit_code == 1
            assert "Project directory already exists" in existing_result.output
            assert nested_result.exit_code == 1
            assert "single folder name" in nested_result.output

    def test_project_analyze_requires_trinity_project(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["project", "analyze"])

            assert result.exit_code == 1
            assert "No Trinity project found" in result.output
            assert not Path(".trinity/project-intake.json").exists()

    def test_project_analyze_writes_project_intake(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            init_result = runner.invoke(main, ["init", "--non-interactive"])
            assert init_result.exit_code == 0

            target = Path("customer-app")
            target.mkdir()
            (target / "pyproject.toml").write_text(
                "[project]\nname='customer-app'\n",
                encoding="utf-8",
            )
            (target / "uv.lock").write_text("", encoding="utf-8")
            (target / "notes.txt").write_text("review me\n", encoding="utf-8")
            _run_git(target, "init")
            _run_git(target, "add", "pyproject.toml", "uv.lock")

            result = runner.invoke(
                main,
                [
                    "project",
                    "analyze",
                    str(target),
                    "--mode",
                    "existing",
                    "--notes",
                    "Read before write.",
                ],
            )

            assert result.exit_code == 0
            assert "Project intake written." in result.output
            assert "uv run pytest" in result.output
            assert "Next steps:" in result.output
            assert "trinity project status" in result.output
            data = json.loads(
                Path(".trinity/project-intake.json").read_text(encoding="utf-8")
            )
            markdown = Path(".trinity/project-intake.md").read_text(encoding="utf-8")
            assert data["mode"] == "existing"
            assert data["target_workspace"] == str(target.resolve())
            assert data["git_repo"] is True
            assert data["dirty_count"] == 2
            assert data["untracked_count"] == 1
            assert data["package_managers"] == ["uv"]
            assert data["test_commands"] == ["uv run pytest"]
            assert "Read before write." in markdown

    def test_project_status_guides_when_intake_is_missing(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            init_result = runner.invoke(main, ["init", "--non-interactive"])
            assert init_result.exit_code == 0

            result = runner.invoke(main, ["project", "status"])

            assert result.exit_code == 0
            assert "No project intake recorded." in result.output
            assert "trinity project analyze [PATH]" in result.output
            assert "trinity project new NAME" in result.output
            assert "Then run `trinity` to start planning." in result.output

    def test_project_status_json_guides_when_intake_is_missing(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            init_result = runner.invoke(main, ["init", "--non-interactive"])
            assert init_result.exit_code == 0

            result = runner.invoke(main, ["project", "status", "--json"])

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["project_intake"] is None
            assert data["current_analysis"] is None
            assert data["next_steps"] == [
                "trinity project analyze [PATH]",
                "trinity project new NAME",
                "trinity",
            ]

    def test_project_status_shows_saved_and_current_analysis(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            init_result = runner.invoke(main, ["init", "--non-interactive"])
            assert init_result.exit_code == 0

            target = Path("customer-app")
            target.mkdir()
            (target / "pyproject.toml").write_text(
                "[project]\nname='customer-app'\n",
                encoding="utf-8",
            )
            (target / "uv.lock").write_text("", encoding="utf-8")
            analyze_result = runner.invoke(
                main,
                ["project", "analyze", str(target), "--notes", "Use this target."],
            )
            assert analyze_result.exit_code == 0

            result = runner.invoke(main, ["project", "status"])

            assert result.exit_code == 0
            assert "Project intake active." in result.output
            assert "Mode: existing" in result.output
            assert "Target name: customer-app" in result.output
            assert "Target workspace:" in result.output
            assert "customer-app" in result.output
            assert "Target exists: True" in result.output
            assert "Saved analysis:" in result.output
            assert "Current analysis:" in result.output
            assert "uv run pytest" in result.output
            assert "Next step: run `trinity`" in result.output

    def test_project_status_json_shows_saved_and_current_analysis(
        self,
        runner,
        tmp_path,
    ):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            init_result = runner.invoke(main, ["init", "--non-interactive"])
            assert init_result.exit_code == 0

            target = Path("customer-app")
            target.mkdir()
            (target / "pyproject.toml").write_text(
                "[project]\nname='customer-app'\n",
                encoding="utf-8",
            )
            (target / "uv.lock").write_text("", encoding="utf-8")
            analyze_result = runner.invoke(main, ["project", "analyze", str(target)])
            assert analyze_result.exit_code == 0

            result = runner.invoke(main, ["project", "status", "--json"])

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["project_intake"]["mode"] == "existing"
            assert data["project_intake"]["target_name"] == "customer-app"
            assert data["project_intake"]["target_workspace"] == str(target.resolve())
            assert data["current_analysis"]["target_exists"] is True
            assert data["current_analysis"]["package_managers"] == ["uv"]
            assert data["current_analysis"]["test_commands"] == ["uv run pytest"]
            assert data["next_steps"] == ["trinity"]

    def test_project_status_refresh_updates_saved_intake(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            init_result = runner.invoke(main, ["init", "--non-interactive"])
            assert init_result.exit_code == 0

            target = Path("customer-app")
            target.mkdir()
            (target / "pyproject.toml").write_text(
                "[project]\nname='customer-app'\n",
                encoding="utf-8",
            )
            (target / "uv.lock").write_text("", encoding="utf-8")
            analyze_result = runner.invoke(main, ["project", "analyze", str(target)])
            assert analyze_result.exit_code == 0
            (target / "package.json").write_text(
                json.dumps({"scripts": {"test": "vitest run"}}),
                encoding="utf-8",
            )

            result = runner.invoke(main, ["project", "status", "--refresh"])

            assert result.exit_code == 0
            assert "Project intake refreshed." in result.output
            assert "npm test" in result.output
            data = json.loads(
                Path(".trinity/project-intake.json").read_text(encoding="utf-8")
            )
            markdown = Path(".trinity/project-intake.md").read_text(encoding="utf-8")
            assert data["package_managers"] == ["uv", "npm"]
            assert data["test_commands"] == ["npm test", "uv run pytest"]
            assert "npm test" in markdown

    def test_project_status_refresh_json_updates_saved_intake(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            init_result = runner.invoke(main, ["init", "--non-interactive"])
            assert init_result.exit_code == 0

            target = Path("customer-app")
            target.mkdir()
            (target / "pyproject.toml").write_text(
                "[project]\nname='customer-app'\n",
                encoding="utf-8",
            )
            analyze_result = runner.invoke(main, ["project", "analyze", str(target)])
            assert analyze_result.exit_code == 0
            (target / "uv.lock").write_text("", encoding="utf-8")

            result = runner.invoke(main, ["project", "status", "--refresh", "--json"])

            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert payload["refreshed"] is True
            json_path = payload["project_intake_paths"]["json"].replace("\\", "/")
            assert json_path.endswith(
                ".trinity/project-intake.json"
            )
            assert payload["project_intake"]["package_managers"] == ["uv"]
            assert payload["project_intake"]["test_commands"] == ["uv run pytest"]
            data = json.loads(
                Path(".trinity/project-intake.json").read_text(encoding="utf-8")
            )
            assert data["package_managers"] == ["uv"]


class TestStatus:
    def test_status_shows_agents(self, runner, trinity_project):
        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            result = runner.invoke(main, ["status"])
            assert result.exit_code == 0
            assert "claude" in result.output
            assert "claude-code" in result.output

    def test_status_shows_shared_context_path(self, runner, trinity_project):
        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            result = runner.invoke(main, ["status"])
            assert "shared context" in result.output.lower() or "shared.md" in result.output


class TestDoctor:
    def test_doctor_shows_platform_config_and_provider_rows(self, runner, trinity_project):
        with (
            patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"),
            patch("trinity.cli.has_command", return_value=False),
            patch("trinity.cli.CLIDetector") as MockDetector,
        ):
            detector = MockDetector.return_value
            detector.detect.return_value = SimpleNamespace(
                installed=False,
                path="",
                error="'claude' not found in PATH",
            )

            result = runner.invoke(main, ["doctor"])

        assert result.exit_code == 0
        assert "Trinity Doctor" in result.output
        assert "Render Mode" in result.output
        assert "Transport" in result.output
        assert "Provider claude" in result.output
        assert "one-shot" in result.output

    def test_doctor_works_without_project_config(self, runner):
        with (
            patch("trinity.cli.find_config_path", return_value=None),
            patch("trinity.cli.has_command", return_value=False),
            patch("trinity.cli.CLIDetector") as MockDetector,
        ):
            detector = MockDetector.return_value
            detector.detect.return_value = SimpleNamespace(
                installed=False,
                path="",
                error="not found",
            )

            result = runner.invoke(main, ["doctor"])

        assert result.exit_code == 0
        assert "default" in result.output
        assert "Provider claude" in result.output


class TestBootstrap:
    def test_bootstrap_requires_project_config(self, runner):
        with patch("trinity.cli.find_config_path", return_value=None):
            result = runner.invoke(main, ["bootstrap", "--no-attach"])

        assert result.exit_code == 1
        assert "trinity init" in result.output

    def test_bootstrap_runs_sequential_by_default(self, runner, trinity_project):
        mock_target = SimpleNamespace(
            agent_name="claude",
            spec=SimpleNamespace(
                provider=Provider.CLAUDE_CODE,
                cli_command="claude",
                model="default",
                extra_args=[],
            ),
            managed_home=trinity_project / ".trinity" / "agents" / "claude" / "provider-state",
            cwd=trinity_project,
        )
        mock_check = SimpleNamespace(installed=True)
        mock_result = SimpleNamespace(
            targets=(mock_target,),
            commands={"claude": ("claude",)},
            checks={"claude": mock_check},
            exit_codes={"claude": 0},
            check_only=False,
            failed_agents=(),
        )

        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            with patch("trinity.cli.ProviderBootstrapper") as MockBootstrapper:
                instance = MockBootstrapper.return_value
                instance.run_sequential.return_value = mock_result

                result = runner.invoke(
                    main,
                    [
                        "bootstrap",
                        "--agents",
                        "claude,codex",
                        "--check-only",
                        "--continue-on-error",
                    ],
                )

        assert result.exit_code == 0
        instance.run_sequential.assert_called_once()
        kwargs = instance.run_sequential.call_args.kwargs
        assert kwargs["agent_names"] == ["claude", "codex"]
        assert kwargs["check_only"] is True
        assert kwargs["continue_on_error"] is True
        assert instance.launch_legacy_tmux_session.call_count == 0

    def test_bootstrap_legacy_tmux_starts_session_without_attach(self, runner, trinity_project):
        mock_target = SimpleNamespace(
            agent_name="claude",
            spec=SimpleNamespace(provider=Provider.CLAUDE_CODE),
            managed_home=trinity_project / ".trinity" / "agents" / "claude" / "provider-state",
            cwd=trinity_project,
        )
        mock_result = SimpleNamespace(
            session_name="test-bootstrap",
            targets=(mock_target,),
            commands={"claude": "env HOME=/tmp claude"},
        )

        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            with patch("trinity.cli.ProviderBootstrapper") as MockBootstrapper:
                with patch("trinity.cli.attach_to_bootstrap_session") as mock_attach:
                    instance = MockBootstrapper.return_value
                    instance.launch_legacy_tmux_session.return_value = mock_result

                    result = runner.invoke(
                        main,
                        [
                            "bootstrap",
                            "--legacy-tmux",
                            "--agents",
                            "claude,codex",
                            "--session-name",
                            "test-bootstrap",
                            "--no-attach",
                        ],
                    )

        assert result.exit_code == 0
        instance.launch_legacy_tmux_session.assert_called_once()
        kwargs = instance.launch_legacy_tmux_session.call_args.kwargs
        assert kwargs["agent_names"] == ["claude", "codex"]
        assert kwargs["session_name"] == "test-bootstrap"
        assert "test-bootstrap" in result.output
        mock_attach.assert_not_called()


class TestContext:
    def test_context_shows_all(self, runner, trinity_project):
        """Test context command reads shared.md via TrinityConfig.shared_context_path."""
        from trinity.config import TrinityConfig

        config_path = trinity_project / ".trinity" / "trinity.config"
        config = TrinityConfig.load(config_path)

        # Ensure shared.md exists at the path config resolves to
        shared_path = config.shared_context_path
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        shared_path.write_text(
            "# Shared Context\n\n## Current Goal\nTest goal\n", encoding="utf-8"
        )

        with patch("trinity.cli.find_config_path", return_value=config_path):
            result = runner.invoke(main, ["context"])
            assert result.exit_code == 0
            assert "Test goal" in result.output

    def test_context_specific_section(self, runner, trinity_project):
        """Test context --section reads a specific section."""
        from trinity.config import TrinityConfig

        config_path = trinity_project / ".trinity" / "trinity.config"
        config = TrinityConfig.load(config_path)

        shared_path = config.shared_context_path
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        shared_path.write_text(
            "# Shared Context\n\n## Current Goal\nTest goal\n", encoding="utf-8"
        )

        with patch("trinity.cli.find_config_path", return_value=config_path):
            result = runner.invoke(main, ["context", "--section", "Current Goal"])
            assert result.exit_code == 0
            assert "Test goal" in result.output

    def test_context_nonexistent_section(self, runner, trinity_project):
        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            result = runner.invoke(main, ["context", "--section", "Nonexistent"])
            assert "not found" in result.output


class TestAsk:
    def test_ask_with_mock(self, runner, trinity_project):
        from trinity.models import DeliberationResult, ConsensusResult

        mock_result = DeliberationResult(
            user_prompt="test question",
            rounds_completed=2,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={"claude": "I agree."},
                summary="Test consensus reached.",
            ),
            total_tokens_used=500,
            duration_seconds=1.5,
        )

        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            with patch("trinity.cli.TrinityOrchestrator") as MockOrch:
                mock_orch_instance = MagicMock()
                mock_orch_instance.ask = AsyncMock(return_value=mock_result)
                MockOrch.return_value = mock_orch_instance

                result = runner.invoke(main, ["ask", "test question"])
                assert result.exit_code == 0
                assert "Consensus" in result.output or "consensus" in result.output
                MockOrch.assert_called_once()
                assert MockOrch.call_args.kwargs["interactive"] is False

    def test_ask_interactive_flag_forces_tmux_transport(self, runner, trinity_project):
        from trinity.models import DeliberationResult, ConsensusResult

        mock_result = DeliberationResult(
            user_prompt="test question",
            rounds_completed=1,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={"claude": "I agree."},
                summary="Done.",
            ),
            total_tokens_used=10,
            duration_seconds=0.5,
        )

        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            with patch("trinity.cli.TrinityOrchestrator") as MockOrch:
                mock_orch_instance = MagicMock()
                mock_orch_instance.ask = AsyncMock(return_value=mock_result)
                MockOrch.return_value = mock_orch_instance

                result = runner.invoke(main, ["ask", "test question", "-i"])

        assert result.exit_code == 0
        assert "Using legacy tmux agent transport" in result.output
        assert "Mode: legacy tmux" in result.output
        MockOrch.assert_called_once()
        assert MockOrch.call_args.kwargs["interactive"] is True

    def test_ask_with_max_rounds_override(self, runner, trinity_project):
        from trinity.models import DeliberationResult, ConsensusResult

        mock_result = DeliberationResult(
            user_prompt="test",
            rounds_completed=2,
            consensus=None,
        )

        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            with patch("trinity.cli.TrinityOrchestrator") as MockOrch:
                mock_orch_instance = MagicMock()
                mock_orch_instance.ask = AsyncMock(return_value=mock_result)
                MockOrch.return_value = mock_orch_instance

                result = runner.invoke(main, ["ask", "test", "--max-rounds", "3"])
                assert result.exit_code == 0

    def test_ask_with_agents_filter(self, runner, trinity_project):
        from trinity.models import DeliberationResult

        mock_result = DeliberationResult(user_prompt="test", rounds_completed=1, consensus=None)

        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            with patch("trinity.cli.TrinityOrchestrator") as MockOrch:
                mock_orch_instance = MagicMock()
                mock_orch_instance.ask = AsyncMock(return_value=mock_result)
                MockOrch.return_value = mock_orch_instance

                result = runner.invoke(main, ["ask", "test", "--agents", "claude"])
                assert result.exit_code == 0


class TestAnalytics:
    def test_analytics_command_no_data(self, runner):
        """trinity analytics should handle no-data case gracefully."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["analytics"])
            assert result.exit_code == 0

    def test_analytics_command_reads_persisted_history(self, runner, trinity_project):
        """trinity analytics should display saved records without a live session."""
        state_dir = trinity_project / ".trinity"
        token_analytics = TokenAnalytics(history_path=analytics_history_path(state_dir))
        token_analytics.record(
            RoundRecord(1, {"claude": 100, "codex": 50}, 20, 1.0)
        )
        token_analytics.record(
            RoundRecord(2, {"claude": 150, "codex": 100}, 25, 1.5)
        )

        config_path = state_dir / "trinity.config"
        with patch("trinity.cli.find_config_path", return_value=config_path):
            result = runner.invoke(main, ["analytics"])

        assert result.exit_code == 0
        assert "Rounds: 2" in result.output
        assert "Total tokens: 400" in result.output
        assert "Avg tokens/round: 200" in result.output
        assert "claude" in result.output
        assert "codex" in result.output


class TestFindConfigPath:
    def test_finds_config_in_current_dir(self, trinity_project):
        with patch("trinity.cli.Path.cwd", return_value=trinity_project):
            path = find_config_path()
            assert path is not None
            assert path.name == "trinity.config"

    def test_returns_none_when_no_config(self, tmp_path):
        with patch("trinity.cli.Path.cwd", return_value=tmp_path):
            path = find_config_path()
            assert path is None


class TestLoadConfig:
    def test_loads_from_path(self, trinity_project):
        config_path = trinity_project / ".trinity" / "trinity.config"
        with patch("trinity.cli.find_config_path", return_value=config_path):
            config = load_config()
            assert config.session_name == "test"
            assert "claude" in config.agents

    def test_returns_default_when_no_path(self, tmp_path):
        with patch("trinity.cli.find_config_path", return_value=None):
            config = load_config()
            assert config.session_name == "trinity"  # default
