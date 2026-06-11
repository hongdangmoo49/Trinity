from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence

from trinity.models import Provider
from trinity.providers.model_discovery import (
    ProviderModelChoice,
    clear_model_discovery_cache,
    discover_provider_models,
    fallback_provider_models,
    parse_antigravity_model_lines,
    parse_codex_model_slugs,
)


def _completed(
    argv: Sequence[str],
    stdout: str,
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=list(argv),
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


def test_parse_codex_model_slugs_only_visible_list_models() -> None:
    payload = {
        "models": [
            {"slug": "gpt-5.5", "display_name": "GPT-5.5", "visibility": "list"},
            {"slug": "codex-auto-review", "visibility": "hide"},
            {"slug": "gpt-5.4-mini", "visibility": "list"},
            {"slug": "gpt-5.5", "visibility": "list"},
        ]
    }

    assert parse_codex_model_slugs(json.dumps(payload)) == [
        "gpt-5.5",
        "gpt-5.4-mini",
    ]


def test_parse_codex_model_slugs_handles_malformed_json() -> None:
    assert parse_codex_model_slugs("{not-json") == []


def test_parse_antigravity_model_lines_dedupes_non_empty_lines() -> None:
    assert parse_antigravity_model_lines(
        "\nGemini 3.5 Flash (Medium)\n\nClaude Sonnet 4.6 (Thinking)\n"
        "Gemini 3.5 Flash (Medium)\n"
    ) == [
        "Gemini 3.5 Flash (Medium)",
        "Claude Sonnet 4.6 (Thinking)",
    ]


def test_discover_codex_models_uses_live_json() -> None:
    clear_model_discovery_cache()

    def runner(
        argv: Sequence[str],
        timeout_seconds: float,
    ) -> subprocess.CompletedProcess[str]:
        assert timeout_seconds == 3.0
        return _completed(
            argv,
            json.dumps(
                {
                    "models": [
                        {"slug": "gpt-5.5", "visibility": "list"},
                        {"slug": "codex-auto-review", "visibility": "hide"},
                    ]
                }
            ),
        )

    choices = discover_provider_models(
        Provider.CODEX,
        "codex",
        use_cache=False,
        runner=runner,
    )

    assert [choice.label for choice in choices] == ["codex(default)", "gpt-5.5"]
    assert [choice.model for choice in choices] == ["default", "gpt-5.5"]
    assert choices[1].source == "cli-live"


def test_discover_codex_models_falls_back_to_bundled_json() -> None:
    clear_model_discovery_cache()
    calls: list[tuple[str, ...]] = []

    def runner(
        argv: Sequence[str],
        timeout_seconds: float,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(tuple(argv))
        if "--bundled" in argv:
            return _completed(
                argv,
                json.dumps({"models": [{"slug": "gpt-5.4", "visibility": "list"}]}),
            )
        return _completed(argv, "{bad-json")

    choices = discover_provider_models(
        Provider.CODEX,
        "codex",
        use_cache=False,
        runner=runner,
    )

    assert calls == [
        ("codex", "debug", "models"),
        ("codex", "debug", "models", "--bundled"),
    ]
    assert [choice.label for choice in choices] == ["codex(default)", "gpt-5.4"]
    assert choices[1].source == "cli-bundled"


def test_discover_antigravity_models_uses_cli_lines() -> None:
    clear_model_discovery_cache()

    def runner(
        argv: Sequence[str],
        timeout_seconds: float,
    ) -> subprocess.CompletedProcess[str]:
        assert tuple(argv) == ("agy", "models")
        return _completed(argv, "Gemini 3.5 Flash (Medium)\nGPT-OSS 120B (Medium)\n")

    choices = discover_provider_models(
        Provider.ANTIGRAVITY_CLI,
        "agy",
        use_cache=False,
        runner=runner,
    )

    assert [choice.label for choice in choices] == [
        "agy(default)",
        "Gemini 3.5 Flash (Medium)",
        "GPT-OSS 120B (Medium)",
    ]
    assert choices[1].source == "cli-live"


def test_discover_claude_models_uses_static_fallback() -> None:
    choices = discover_provider_models(
        Provider.CLAUDE_CODE,
        "claude",
        use_cache=False,
    )

    assert choices[0] == ProviderModelChoice(
        provider=Provider.CLAUDE_CODE,
        model="default",
        label="claude(default)",
        source="static-fallback",
        is_default=True,
        context_budget=200_000,
    )
    assert "opus[1m]" in [choice.model for choice in choices]


def test_fallback_provider_models_puts_default_first() -> None:
    choices = fallback_provider_models(Provider.ANTIGRAVITY_CLI)

    assert choices[0].model == "default"
    assert choices[0].label == "agy(default)"
    assert choices[0].is_default is True
