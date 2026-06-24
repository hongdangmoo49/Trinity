"""Tests for trinity.setup.wizard — interactive setup wizard."""

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from trinity.models import AgentSpec, Provider
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.setup.detector import CLIDetectionResult, LEGACY_GEMINI_CLI
from trinity.setup.wizard import SetupWizard, PROVIDER_AGENT_NAMES


class TestSetupWizard:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=True, width=120)

    @pytest.fixture
    def mock_detector(self):
        """Detector that finds only claude installed."""
        detector = MagicMock()
        detector.detect_all.return_value = [
            CLIDetectionResult(
                provider=Provider.CLAUDE_CODE,
                installed=True,
                version="claude 1.0.0",
                path="/usr/bin/claude",
            ),
            CLIDetectionResult(
                provider=Provider.CODEX,
                installed=False,
                error="codex not found",
            ),
            CLIDetectionResult(
                provider=Provider.ANTIGRAVITY_CLI,
                installed=False,
                error="agy not found",
            ),
            CLIDetectionResult(
                provider=LEGACY_GEMINI_CLI,
                installed=False,
                error="gemini not found",
            ),
        ]
        return detector

    @pytest.fixture
    def mock_detector_all_installed(self):
        """Detector that finds all CLIs installed."""
        detector = MagicMock()
        detector.detect_all.return_value = [
            CLIDetectionResult(
                provider=Provider.CLAUDE_CODE,
                installed=True,
                version="claude 1.0.0",
                path="/usr/bin/claude",
            ),
            CLIDetectionResult(
                provider=Provider.CODEX,
                installed=True,
                version="codex 0.1.0",
                path="/usr/bin/codex",
            ),
            CLIDetectionResult(
                provider=Provider.ANTIGRAVITY_CLI,
                installed=True,
                version="agy 1.0.0",
                path="/usr/bin/agy",
                warning="Experimental in Trinity.",
            ),
            CLIDetectionResult(
                provider=LEGACY_GEMINI_CLI,
                installed=True,
                version="gemini 0.5.0",
                path="/usr/bin/gemini",
            ),
        ]
        return detector

    def test_init_creates_wizard(self, console, mock_detector):
        wizard = SetupWizard(console=console, detector=mock_detector)
        assert wizard.console is console
        assert wizard.detector is mock_detector
        assert wizard.selected_agents == {}

    def test_step_detect_shows_installed(self, console, mock_detector):
        wizard = SetupWizard(console=console, detector=mock_detector)
        result = wizard._step_detect()

        assert result is True  # At least one installed
        assert len(wizard.detections) == 4

    def test_step_detect_hides_legacy_gemini(self, mock_detector_all_installed):
        console = Console(force_terminal=True, width=120, record=True)
        wizard = SetupWizard(console=console, detector=mock_detector_all_installed)

        result = wizard._step_detect()

        assert result is True
        output = console.export_text()
        assert "Antigravity CLI" in output
        assert "Gemini CLI" not in output

    def test_step_detect_no_tools_installed(self, console):
        detector = MagicMock()
        detector.detect_all.return_value = [
            CLIDetectionResult(provider=Provider.CLAUDE_CODE, installed=False, error="not found"),
            CLIDetectionResult(provider=Provider.CODEX, installed=False, error="not found"),
            CLIDetectionResult(
                provider=Provider.ANTIGRAVITY_CLI,
                installed=False,
                error="not found",
            ),
            CLIDetectionResult(provider=LEGACY_GEMINI_CLI, installed=False, error="not found"),
        ]

        wizard = SetupWizard(console=console, detector=detector)
        result = wizard._step_detect()

        assert result is False

    def test_step_detect_legacy_gemini_only_is_not_available(self, console):
        detector = MagicMock()
        detector.detect_all.return_value = [
            CLIDetectionResult(
                provider=LEGACY_GEMINI_CLI,
                installed=True,
                version="gemini 0.5.0",
                path="/usr/bin/gemini",
            ),
        ]

        wizard = SetupWizard(console=console, detector=detector)
        result = wizard._step_detect()

        assert result is False

    def test_step_select_claude_only(self, console, mock_detector):
        """Test agent selection when only Claude is installed."""
        wizard = SetupWizard(console=console, detector=mock_detector)
        wizard.detections = mock_detector.detect_all()

        with patch("trinity.setup.wizard.Confirm.ask", return_value=True):
            result = wizard._step_select()

        assert result is True
        assert "claude" in wizard.selected_agents

    def test_step_select_all_agents(self, console, mock_detector_all_installed):
        """Test selecting all agents."""
        wizard = SetupWizard(console=console, detector=mock_detector_all_installed)
        wizard.detections = mock_detector_all_installed.detect_all()

        with patch("trinity.setup.wizard.Confirm.ask", return_value=True):
            result = wizard._step_select()

        assert result is True
        assert "claude" in wizard.selected_agents
        assert "codex" in wizard.selected_agents
        assert "antigravity" in wizard.selected_agents
        assert "gemini" not in wizard.selected_agents

    def test_step_select_installed_agents_default_to_enabled(
        self,
        console,
        mock_detector_all_installed,
    ):
        """Installed non-legacy agents should default to enabled."""
        wizard = SetupWizard(console=console, detector=mock_detector_all_installed)
        wizard.detections = mock_detector_all_installed.detect_all()

        with patch("trinity.setup.wizard.Confirm.ask", return_value=True) as ask:
            result = wizard._step_select()

        assert result is True
        defaults = [call.kwargs["default"] for call in ask.call_args_list]
        assert defaults == [True, True, True]

    def test_step_select_none_selected(self, console, mock_detector):
        """Test when user declines all agents."""
        wizard = SetupWizard(console=console, detector=mock_detector)
        wizard.detections = mock_detector.detect_all()

        with patch("trinity.setup.wizard.Confirm.ask", return_value=False):
            result = wizard._step_select()

        assert result is False
        assert wizard.selected_agents == {}

    def test_step_customize_roles_default(self, console, mock_detector):
        """Test customizing roles with defaults accepted."""
        wizard = SetupWizard(console=console, detector=mock_detector)
        wizard.detections = mock_detector.detect_all()

        # Pre-populate with claude selected
        wizard.selected_agents["claude"] = AgentSpec(
            name="claude",
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
            role_prompt="You are the Architect.",
            context_budget=200_000,
            enabled=True,
        )

        with patch("trinity.setup.wizard.Prompt.ask", return_value="1"):
            with patch("trinity.setup.wizard.Confirm.ask", return_value=False):
                wizard._step_customize_roles()

        # Role should be unchanged
        assert wizard.selected_agents["claude"].role_prompt == "You are the Architect."
        assert wizard.selected_agents["claude"].model == "default"
        assert wizard.selected_agents["claude"].context_budget == 200_000

    def test_step_customize_roles_selects_model_budget(self, console, mock_detector):
        """Test model selection updates model id and context budget."""
        wizard = SetupWizard(console=console, detector=mock_detector)
        wizard.selected_agents["claude"] = AgentSpec(
            name="claude",
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
            role_prompt="You are the Architect.",
            context_budget=200_000,
            enabled=True,
        )

        # Claude option 3 is opus[1m].
        with patch("trinity.setup.wizard.Prompt.ask", return_value="3"):
            with patch("trinity.setup.wizard.Confirm.ask", return_value=False):
                wizard._step_customize_roles()

        assert wizard.selected_agents["claude"].model == "opus[1m]"
        assert wizard.selected_agents["claude"].context_budget == 1_000_000

    def test_step_customize_roles_custom_model_budget(self, console, mock_detector):
        """Test custom model selection asks for model id and budget."""
        wizard = SetupWizard(console=console, detector=mock_detector)
        wizard.selected_agents["codex"] = AgentSpec(
            name="codex",
            provider=Provider.CODEX,
            cli_command="codex",
            role_prompt="You are the Implementer.",
            context_budget=128_000,
            enabled=True,
        )

        with patch(
            "trinity.setup.wizard.Prompt.ask",
            side_effect=["c", "my-codex-model"],
        ):
            with patch("trinity.setup.wizard.IntPrompt.ask", return_value=256_000):
                with patch("trinity.setup.wizard.Confirm.ask", return_value=False):
                    wizard._step_customize_roles()

        assert wizard.selected_agents["codex"].model == "my-codex-model"
        assert wizard.selected_agents["codex"].context_budget == 256_000

    def test_ask_model_choice_uses_provider_discovery(self, console):
        """Model choices should come from the provider CLI discovery layer."""
        wizard = SetupWizard(console=console)
        spec = AgentSpec(
            name="codex",
            provider=Provider.CODEX,
            cli_command="codex",
            model="default",
            role_prompt="You are the Implementer.",
            context_budget=128_000,
            enabled=True,
        )

        discovered = [
            ProviderModelChoice(
                provider=Provider.CODEX,
                model="default",
                label="codex(default)",
                source="static-fallback",
                is_default=True,
                context_budget=128_000,
            ),
            ProviderModelChoice(
                provider=Provider.CODEX,
                model="gpt-5.5",
                label="gpt-5.5",
                source="cli-live",
                context_budget=None,
            ),
        ]
        with patch(
            "trinity.setup.wizard.discover_provider_models",
            return_value=discovered,
        ) as discover:
            with patch("trinity.setup.wizard.Prompt.ask", return_value="2"):
                selected = wizard._ask_model_choice(spec)

        discover.assert_called_once_with(
            Provider.CODEX,
            "codex",
            timeout_seconds=10.0,
            use_cache=False,
        )
        assert selected is not None
        assert selected.model == "gpt-5.5"
        assert selected.source == "cli-live"

    def test_ask_model_choice_localizes_source_labels_in_korean(self):
        """Korean setup should render model source labels without changing metadata."""
        console = Console(force_terminal=True, width=120, record=True)
        wizard = SetupWizard(console=console)
        wizard.lang = "ko"
        spec = AgentSpec(
            name="codex",
            provider=Provider.CODEX,
            cli_command="codex",
            model="default",
            role_prompt="You are the Implementer.",
            context_budget=128_000,
            enabled=True,
        )

        discovered = [
            ProviderModelChoice(
                provider=Provider.CODEX,
                model="default",
                label="codex(default)",
                source="static-fallback",
                is_default=True,
                context_budget=128_000,
            ),
            ProviderModelChoice(
                provider=Provider.CODEX,
                model="gpt-5.5",
                label="gpt-5.5",
                source="cli-live",
                context_budget=None,
            ),
        ]
        with patch(
            "trinity.setup.wizard.discover_provider_models",
            return_value=discovered,
        ):
            with patch("trinity.setup.wizard.Prompt.ask", return_value="2"):
                selected = wizard._ask_model_choice(spec)

        assert selected is not None
        assert selected.source == "cli-live"
        output = console.export_text()
        assert "정적 기본값" in output
        assert "CLI 실시간" in output

    def test_step_review_accept(self, console, mock_detector):
        """Test review step with acceptance."""
        wizard = SetupWizard(console=console, detector=mock_detector)
        wizard.selected_agents["claude"] = AgentSpec(
            name="claude",
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
            role_prompt="Test role",
            context_budget=200_000,
            enabled=True,
        )

        with patch("trinity.setup.wizard.Confirm.ask", return_value=True):
            result = wizard._step_review()

        assert result is True

    def test_step_review_reject(self, console, mock_detector):
        """Test review step with rejection."""
        wizard = SetupWizard(console=console, detector=mock_detector)
        wizard.selected_agents["claude"] = AgentSpec(
            name="claude",
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
            role_prompt="Test role",
            context_budget=200_000,
            enabled=True,
        )

        with patch("trinity.setup.wizard.Confirm.ask", return_value=False):
            result = wizard._step_review()

        assert result is False

    def test_build_missing_agent_specs(self, console, mock_detector):
        """Test building specs for missing CLIs."""
        wizard = SetupWizard(console=console, detector=mock_detector)
        wizard.detections = mock_detector.detect_all()

        missing = wizard.build_missing_agent_specs()

        assert "codex" in missing
        assert "antigravity" in missing
        assert "gemini" not in missing
        assert "claude" not in missing
        assert missing["antigravity"].cli_command == "agy"

        # All missing should be disabled
        for spec in missing.values():
            assert spec.enabled is False

    def test_selected_agents_have_correct_providers(self, console, mock_detector_all_installed):
        """Test that selected agents have correct provider assignments."""
        wizard = SetupWizard(console=console, detector=mock_detector_all_installed)
        wizard.detections = mock_detector_all_installed.detect_all()

        with patch("trinity.setup.wizard.Confirm.ask", return_value=True):
            wizard._step_select()

        assert wizard.selected_agents["claude"].provider == Provider.CLAUDE_CODE
        assert wizard.selected_agents["codex"].provider == Provider.CODEX
        assert wizard.selected_agents["antigravity"].provider == Provider.ANTIGRAVITY_CLI
        assert wizard.selected_agents["claude"].model == "default"


class TestProviderAgentNames:
    def test_all_providers_mapped(self):
        for provider in Provider:
            assert provider in PROVIDER_AGENT_NAMES

    def test_names_are_standard(self):
        assert PROVIDER_AGENT_NAMES[Provider.CLAUDE_CODE] == "claude"
        assert PROVIDER_AGENT_NAMES[Provider.CODEX] == "codex"
        assert PROVIDER_AGENT_NAMES[Provider.ANTIGRAVITY_CLI] == "antigravity"
