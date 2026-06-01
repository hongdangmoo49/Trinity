"""Tests for trinity.setup.detector — CLI tool detection."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from trinity.models import Provider
from trinity.setup.detector import (
    PROVIDER_DEFAULT_ARGS,
    PROVIDER_DEFAULT_BUDGETS,
    PROVIDER_DEFAULT_ROLES,
    PROVIDER_DISPLAY_NAMES,
    PROVIDER_INSTALL_URLS,
    CLIDetectionResult,
    CLIDetector,
)


class TestCLIDetectionResult:
    def test_display_name(self):
        result = CLIDetectionResult(provider=Provider.CLAUDE_CODE, installed=True)
        assert result.display_name == "Claude Code"

    def test_display_name_codex(self):
        result = CLIDetectionResult(provider=Provider.CODEX, installed=True)
        assert result.display_name == "Codex CLI"

    def test_display_name_gemini(self):
        result = CLIDetectionResult(provider=Provider.GEMINI_CLI, installed=True)
        assert result.display_name == "Gemini CLI"

    def test_install_url(self):
        result = CLIDetectionResult(provider=Provider.CLAUDE_CODE, installed=False)
        assert "anthropic" in result.install_url

    def test_install_url_codex(self):
        result = CLIDetectionResult(provider=Provider.CODEX, installed=False)
        assert result.install_url != ""

    def test_install_url_gemini(self):
        result = CLIDetectionResult(provider=Provider.GEMINI_CLI, installed=False)
        assert result.install_url != ""

    def test_default_values(self):
        result = CLIDetectionResult(provider=Provider.CLAUDE_CODE, installed=False)
        assert result.version == ""
        assert result.path == ""
        assert result.error == ""


class TestCLIDetector:
    def test_detect_all_returns_all_providers(self):
        detector = CLIDetector()
        with patch("trinity.setup.detector.shutil.which", return_value=None):
            results = detector.detect_all()

        assert len(results) == len(Provider)
        providers = {r.provider for r in results}
        assert Provider.CLAUDE_CODE in providers
        assert Provider.CODEX in providers
        assert Provider.GEMINI_CLI in providers

    def test_detect_installed_binary(self):
        detector = CLIDetector()
        with patch("trinity.setup.detector.shutil.which", return_value="/usr/bin/claude"):
            with patch.object(detector, "_get_version", return_value="claude 1.0.0"):
                result = detector.detect(Provider.CLAUDE_CODE)

        assert result.installed
        assert result.version == "claude 1.0.0"
        assert result.path == "/usr/bin/claude"

    def test_detect_missing_binary(self):
        detector = CLIDetector()
        with patch("trinity.setup.detector.shutil.which", return_value=None):
            result = detector.detect(Provider.CLAUDE_CODE)

        assert not result.installed
        assert result.error != ""  # Some error message present

    def test_detect_codex(self):
        detector = CLIDetector()
        with patch("trinity.setup.detector.shutil.which", return_value="/usr/bin/codex"):
            with patch.object(detector, "_get_version", return_value="codex 0.1.0"):
                result = detector.detect(Provider.CODEX)

        assert result.installed
        assert result.provider == Provider.CODEX

    def test_detect_gemini(self):
        detector = CLIDetector()
        with patch("trinity.setup.detector.shutil.which", return_value="/usr/bin/gemini"):
            with patch.object(detector, "_get_version", return_value="gemini 0.5.0"):
                result = detector.detect(Provider.GEMINI_CLI)

        assert result.installed
        assert result.provider == Provider.GEMINI_CLI

    def test_get_version_timeout(self):
        detector = CLIDetector(timeout=0.001)
        with patch(
            "trinity.setup.detector.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="test", timeout=0.001),
        ):
            version = detector._get_version("nonexistent")

        assert version == ""

    def test_get_version_os_error(self):
        detector = CLIDetector()
        with patch(
            "trinity.setup.detector.subprocess.run",
            side_effect=OSError("not found"),
        ):
            version = detector._get_version("nonexistent")

        assert version == ""

    def test_get_version_success(self):
        detector = CLIDetector()
        mock_result = MagicMock()
        mock_result.stdout = "claude 1.0.0\n"
        mock_result.stderr = ""

        with patch("trinity.setup.detector.subprocess.run", return_value=mock_result):
            version = detector._get_version("claude")

        assert "claude" in version

    def test_get_version_stderr_output(self):
        """Some CLIs output version to stderr."""
        detector = CLIDetector()
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "codex version 0.1.0\n"

        with patch("trinity.setup.detector.subprocess.run", return_value=mock_result):
            version = detector._get_version("codex")

        assert "codex" in version

    def test_detect_installed_providers_filters(self):
        detector = CLIDetector()
        with patch("trinity.setup.detector.shutil.which") as mock_which:
            # Only claude is installed
            def which_side_effect(binary):
                if binary == "claude":
                    return "/usr/bin/claude"
                return None

            mock_which.side_effect = which_side_effect
            with patch.object(detector, "_get_version", return_value="v1"):
                installed = detector.detect_installed_providers()

        assert Provider.CLAUDE_CODE in installed
        assert Provider.CODEX not in installed
        assert Provider.GEMINI_CLI not in installed

    def test_custom_timeout(self):
        detector = CLIDetector(timeout=10.0)
        assert detector.timeout == 10.0


class TestProviderConstants:
    def test_all_providers_have_display_names(self):
        for provider in Provider:
            assert provider in PROVIDER_DISPLAY_NAMES

    def test_all_providers_have_budgets(self):
        for provider in Provider:
            assert provider in PROVIDER_DEFAULT_BUDGETS

    def test_all_providers_have_roles(self):
        for provider in Provider:
            assert provider in PROVIDER_DEFAULT_ROLES

    def test_all_providers_have_args(self):
        for provider in Provider:
            assert provider in PROVIDER_DEFAULT_ARGS

    def test_all_providers_have_install_urls(self):
        for provider in Provider:
            assert provider in PROVIDER_INSTALL_URLS

    def test_budgets_reasonable(self):
        assert PROVIDER_DEFAULT_BUDGETS[Provider.CLAUDE_CODE] == 200_000
        assert PROVIDER_DEFAULT_BUDGETS[Provider.CODEX] == 128_000
        assert PROVIDER_DEFAULT_BUDGETS[Provider.GEMINI_CLI] == 1_000_000

    def test_roles_non_empty(self):
        for provider in Provider:
            assert len(PROVIDER_DEFAULT_ROLES[provider]) > 20
