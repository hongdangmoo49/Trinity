"""Provider CLI model discovery helpers."""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from trinity.models import (
    ModelContextSpec,
    PROVIDER_MODEL_CONTEXTS,
    Provider,
    model_context_budget,
)

ModelChoiceSource = Literal[
    "cli-live",
    "cli-bundled",
    "static-fallback",
    "unavailable",
]


@dataclass(frozen=True)
class ProviderModelChoice:
    """A model option suitable for provider model selection UI."""

    provider: Provider
    model: str
    label: str
    source: ModelChoiceSource
    is_default: bool = False
    context_budget: int | None = None
    source_reason: str = field(default="", compare=False)


CommandRunner = Callable[
    [Sequence[str], float],
    subprocess.CompletedProcess[str],
]

_CACHE: dict[tuple[Provider, str], tuple[float, tuple[ProviderModelChoice, ...]]] = {}


def discover_provider_models(
    provider: Provider,
    cli_command: str,
    *,
    timeout_seconds: float = 3.0,
    cache_ttl_seconds: float = 300.0,
    use_cache: bool = True,
    runner: CommandRunner | None = None,
) -> list[ProviderModelChoice]:
    """Return model choices discovered from provider CLIs, falling back safely."""
    command = (cli_command or "").strip()
    cache_key = (provider, command)
    now = time.time()
    if use_cache and cache_key in _CACHE:
        cached_at, choices = _CACHE[cache_key]
        if now - cached_at <= cache_ttl_seconds:
            return list(choices)

    choices = _discover_uncached(
        provider,
        command,
        timeout_seconds=timeout_seconds,
        runner=runner or _run_command,
    )
    if use_cache:
        _CACHE[cache_key] = (now, tuple(choices))
    return choices


def fallback_provider_models(
    provider: Provider,
    *,
    source_reason: str = "using Trinity static provider model catalog",
) -> list[ProviderModelChoice]:
    """Return static provider model choices with a provider default first."""
    return _choices_from_models(
        provider,
        [
            spec
            for spec in PROVIDER_MODEL_CONTEXTS.get(provider, ())
            if spec.model != "default"
        ],
        source="static-fallback",
        source_reason=source_reason,
    )


def parse_codex_model_slugs(text: str) -> list[str]:
    """Parse visible Codex model slugs from `codex debug models` JSON."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    models = payload.get("models", [])
    if not isinstance(models, list):
        return []
    slugs: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        if str(item.get("visibility") or "").strip() != "list":
            continue
        slug = str(item.get("slug") or "").strip()
        if slug:
            slugs.append(slug)
    return _dedupe(slugs)


def parse_antigravity_model_lines(text: str) -> list[str]:
    """Parse `agy models` output, one model per non-empty line."""
    return _dedupe(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not _looks_like_structured_payload(line.strip())
    )


def clear_model_discovery_cache() -> None:
    """Clear in-process model discovery cache. Intended for tests."""
    _CACHE.clear()


def _discover_uncached(
    provider: Provider,
    cli_command: str,
    *,
    timeout_seconds: float,
    runner: CommandRunner,
) -> list[ProviderModelChoice]:
    if provider == Provider.CODEX and cli_command:
        live = _run_and_parse_codex(cli_command, timeout_seconds, runner, bundled=False)
        if live:
            return _choices_from_names(provider, live, source="cli-live")
        bundled = _run_and_parse_codex(cli_command, timeout_seconds, runner, bundled=True)
        if bundled:
            return _choices_from_names(provider, bundled, source="cli-bundled")
        return fallback_provider_models(
            provider,
            source_reason=(
                "Codex model discovery returned no listable live or bundled models"
            ),
        )
    if provider == Provider.ANTIGRAVITY_CLI and cli_command:
        models = _run_and_parse_antigravity(cli_command, timeout_seconds, runner)
        if models:
            return _choices_from_names(provider, models, source="cli-live")
        return fallback_provider_models(
            provider,
            source_reason="Antigravity model discovery returned no models",
        )
    reason = (
        "provider does not expose CLI model discovery"
        if provider == Provider.CLAUDE_CODE
        else "no CLI command configured for provider model discovery"
    )
    return fallback_provider_models(provider, source_reason=reason)


def _run_and_parse_codex(
    cli_command: str,
    timeout_seconds: float,
    runner: CommandRunner,
    *,
    bundled: bool,
) -> list[str]:
    argv = [cli_command, "debug", "models"]
    if bundled:
        argv.append("--bundled")
    completed = _safe_run(runner, argv, timeout_seconds)
    if completed is None or completed.returncode != 0:
        return []
    return parse_codex_model_slugs(completed.stdout or "")


def _run_and_parse_antigravity(
    cli_command: str,
    timeout_seconds: float,
    runner: CommandRunner,
) -> list[str]:
    completed = _safe_run(runner, [cli_command, "models"], timeout_seconds)
    if completed is None or completed.returncode != 0:
        return []
    return parse_antigravity_model_lines(completed.stdout or "")


def _safe_run(
    runner: CommandRunner,
    argv: Sequence[str],
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return runner(tuple(argv), timeout_seconds)
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None


def _run_command(
    argv: Sequence[str],
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def _choices_from_names(
    provider: Provider,
    names: list[str],
    *,
    source: ModelChoiceSource,
) -> list[ProviderModelChoice]:
    specs = [
        ModelContextSpec(
            model=name,
            display_name=name,
            context_budget=model_context_budget(provider, name) or 0,
        )
        for name in names
        if name and name != "default"
    ]
    return _choices_from_models(provider, specs, source=source)


def _choices_from_models(
    provider: Provider,
    specs: list[ModelContextSpec],
    *,
    source: ModelChoiceSource,
    source_reason: str = "",
) -> list[ProviderModelChoice]:
    choices = [_default_choice(provider, source_reason=source_reason)]
    seen = {"default"}
    for spec in specs:
        model = spec.model.strip()
        if not model or model in seen:
            continue
        seen.add(model)
        choices.append(
            ProviderModelChoice(
                provider=provider,
                model=model,
                label=model,
                source=source,
                context_budget=spec.context_budget or None,
                source_reason=source_reason,
            )
        )
    return choices


def _default_choice(
    provider: Provider,
    *,
    source_reason: str = "",
) -> ProviderModelChoice:
    return ProviderModelChoice(
        provider=provider,
        model="default",
        label=_default_label(provider),
        source="static-fallback",
        is_default=True,
        context_budget=model_context_budget(provider, "default"),
        source_reason=source_reason,
    )


def _default_label(provider: Provider) -> str:
    labels = {
        Provider.CLAUDE_CODE: "claude(default)",
        Provider.CODEX: "codex(default)",
        Provider.ANTIGRAVITY_CLI: "agy(default)",
    }
    return labels.get(provider, "default")


def _dedupe(values: Sequence[str] | object) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for raw in values:  # type: ignore[union-attr]
        value = str(raw).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _looks_like_structured_payload(text: str) -> bool:
    """Return whether a line looks like provider response data, not a model name."""
    return (
        (text.startswith("{") and text.endswith("}"))
        or (text.startswith("[") and text.endswith("]"))
    )
