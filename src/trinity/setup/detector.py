"""CLI tool detector — auto-detect installed AI CLI tools.

Runs `cli --version` for each known provider and reports
installation status, version string, and path.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass

from trinity.models import Provider, provider_default_budget

logger = logging.getLogger(__name__)

LEGACY_GEMINI_CLI = "gemini-cli"

# Provider → CLI binary names to probe (in order of preference)
PROVIDER_BINARIES: dict[Provider | str, list[str]] = {
    Provider.CLAUDE_CODE: ["claude"],
    Provider.CODEX: ["codex"],
    Provider.ANTIGRAVITY_CLI: ["agy"],
    LEGACY_GEMINI_CLI: ["gemini"],
}

# Human-readable names for display
PROVIDER_DISPLAY_NAMES: dict[Provider | str, str] = {
    Provider.CLAUDE_CODE: "Claude Code",
    Provider.CODEX: "Codex CLI",
    Provider.ANTIGRAVITY_CLI: "Antigravity CLI",
    LEGACY_GEMINI_CLI: "Gemini CLI",
}

# Provider → default context budget (tokens)
PROVIDER_DEFAULT_BUDGETS: dict[Provider, int] = {
    provider: provider_default_budget(provider)
    for provider in Provider
}

# Provider → default role prompt
PROVIDER_DEFAULT_ROLES: dict[Provider, str] = {
    Provider.CLAUDE_CODE: (
        "You are the Architect. You design systems, review code, "
        "and make high-level technical decisions. Think carefully "
        "and provide structured, well-reasoned opinions."
    ),
    Provider.CODEX: (
        "You are the Implementer. You write clean, efficient code "
        "based on architectural decisions. Focus on practical "
        "implementation and edge cases."
    ),
    Provider.ANTIGRAVITY_CLI: (
        "You are the Reviewer. You explore alternatives, identify "
        "potential issues, and ensure quality. Think critically "
        "about trade-offs and propose tests."
    ),
}

# Provider → default extra CLI args
PROVIDER_DEFAULT_ARGS: dict[Provider, list[str]] = {
    Provider.CLAUDE_CODE: ["--dangerously-skip-permissions"],
    Provider.CODEX: [],
    Provider.ANTIGRAVITY_CLI: [],
}

# Provider → installation instructions URL
PROVIDER_INSTALL_URLS: dict[Provider | str, str] = {
    Provider.CLAUDE_CODE: "https://docs.anthropic.com/en/docs/claude-code",
    Provider.CODEX: "https://github.com/openai/codex",
    Provider.ANTIGRAVITY_CLI: "https://antigravity.google/docs/cli-getting-started",
    LEGACY_GEMINI_CLI: "https://antigravity.google/docs/gcli-migration",
}

# Provider → default agent name (used to look up role prompts in i18n)
PROVIDER_AGENT_NAMES: dict[Provider, str] = {
    Provider.CLAUDE_CODE: "claude",
    Provider.CODEX: "codex",
    Provider.ANTIGRAVITY_CLI: "antigravity",
}

LEGACY_PROVIDERS: set[str] = {LEGACY_GEMINI_CLI}

PROVIDER_WARNINGS: dict[Provider | str, str] = {
    LEGACY_GEMINI_CLI: (
        "Deprecated: migrate Gemini CLI plugins/settings with `agy plugin import gemini`."
    ),
}


def provider_default_cli_command(provider: Provider | str) -> str:
    """Return the canonical CLI command Trinity should store for a provider."""
    binaries = PROVIDER_BINARIES.get(provider, [])
    if binaries:
        return binaries[0]
    return str(provider)


def get_provider_role(provider: Provider, lang: str = "en") -> str:
    """Get a localized role prompt for a provider.

    Args:
        provider: The AI provider.
        lang: "en" or "ko".

    Returns:
        Localized role prompt string.
    """
    from trinity.i18n import role_prompt

    agent_name = PROVIDER_AGENT_NAMES.get(provider, provider.value)
    return role_prompt(agent_name, lang)


@dataclass
class CLIDetectionResult:
    """Result of detecting a single CLI tool."""

    provider: Provider | str
    installed: bool
    version: str = ""
    path: str = ""
    error: str = ""
    warning: str = ""

    @property
    def display_name(self) -> str:
        return PROVIDER_DISPLAY_NAMES.get(self.provider, str(self.provider))

    @property
    def install_url(self) -> str:
        return PROVIDER_INSTALL_URLS.get(self.provider, "")


class CLIDetector:
    """Detect installed AI CLI tools on the system.

    Runs version commands for each provider and captures results.
    Works synchronously (for init) or can be used in async contexts
    via run_in_executor.
    """

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    def detect_all(self) -> list[CLIDetectionResult]:
        """Detect all known CLI tools.

        Returns:
            List of detection results, one per known provider.
        """
        results = []
        for provider in Provider:
            result = self.detect(provider)
            results.append(result)
        return results

    def detect(self, provider: Provider | str) -> CLIDetectionResult:
        """Detect a single CLI tool.

        Args:
            provider: The provider to detect.

        Returns:
            Detection result with version info if installed.
        """
        binaries = PROVIDER_BINARIES.get(provider, [])
        if not binaries:
            return CLIDetectionResult(
                provider=provider,
                installed=False,
                error=f"No binary names configured for {provider}",
                warning=PROVIDER_WARNINGS.get(provider, ""),
            )

        for binary in binaries:
            result = self._try_detect(binary, provider)
            if result.installed:
                return result

        return CLIDetectionResult(
            provider=provider,
            installed=False,
            error=f"None of {binaries} found in PATH",
            warning=PROVIDER_WARNINGS.get(provider, ""),
        )

    def _try_detect(self, binary: str, provider: Provider | str) -> CLIDetectionResult:
        """Try to detect a single binary.

        Args:
            binary: The binary name to look for.
            provider: The provider this binary belongs to.

        Returns:
            Detection result.
        """
        # 1. Check if binary exists in PATH
        binary_path = shutil.which(binary)
        if not binary_path:
            return CLIDetectionResult(
                provider=provider,
                installed=False,
                error=f"'{binary}' not found in PATH",
                warning=PROVIDER_WARNINGS.get(provider, ""),
            )

        # 2. Try to get version
        version = self._get_version(binary)

        return CLIDetectionResult(
            provider=provider,
            installed=True,
            version=version,
            path=binary_path,
            warning=PROVIDER_WARNINGS.get(provider, ""),
        )

    def _get_version(self, binary: str) -> str:
        """Run `binary --version` and extract version string.

        Args:
            binary: Binary name or path.

        Returns:
            Version string, or empty string if detection failed.
        """
        try:
            result = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding="utf-8",
            )
            # Combine stdout and stderr — some CLIs output version to stderr
            output = (result.stdout + result.stderr).strip()
            if output:
                # Take first line that contains a version-like pattern
                for line in output.splitlines():
                    line = line.strip()
                    if line:
                        return line
            return ""
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as e:
            logger.debug(f"Version detection failed for {binary}: {e}")
            return ""

    def detect_installed_providers(self) -> dict[Provider, CLIDetectionResult]:
        """Detect all installed providers.

        Returns:
            Dict mapping provider → detection result for installed tools only.
        """
        return {
            r.provider: r
            for r in self.detect_all()
            if r.installed and isinstance(r.provider, Provider)
        }
