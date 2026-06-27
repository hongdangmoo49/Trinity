"""Textual provider model discovery helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

from trinity.models import AgentSpec, Provider
from trinity.providers.model_discovery import ProviderModelChoice, discover_provider_models


class ProviderModelDiscoverer(Protocol):
    """Callable used to discover model choices for a provider."""

    def __call__(
        self,
        provider: Provider,
        cli_command: str,
        *,
        timeout_seconds: float,
        use_cache: bool,
    ) -> Sequence[ProviderModelChoice]: ...


def iter_discovered_agent_model_choices(
    agent_specs: Iterable[tuple[str, AgentSpec]],
    *,
    use_cache: bool = True,
    timeout_seconds: float = 10.0,
    max_workers: int = 8,
    discover: ProviderModelDiscoverer | None = None,
) -> Iterable[tuple[str, tuple[ProviderModelChoice, ...]]]:
    """Yield non-empty model choices as each agent discovery finishes."""
    specs = list(agent_specs)
    if not specs:
        return

    discover_models = discover or discover_provider_models
    worker_count = min(len(specs), max_workers)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                discover_models,
                spec.provider,
                spec.cli_command,
                timeout_seconds=timeout_seconds,
                use_cache=use_cache,
            ): name
            for name, spec in specs
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                choices = tuple(future.result())
            except Exception:
                choices = ()
            if choices:
                yield name, choices


def merge_discovered_model_choices(
    current_choices: MutableMapping[str, tuple[ProviderModelChoice, ...]],
    choices_by_agent: Mapping[str, Sequence[ProviderModelChoice]],
) -> dict[str, tuple[ProviderModelChoice, ...]]:
    """Update current choices and return only agents whose choices changed."""
    changed_choices: dict[str, tuple[ProviderModelChoice, ...]] = {}
    for name, choices in choices_by_agent.items():
        next_choices = tuple(choices)
        if current_choices.get(name, ()) == next_choices:
            continue
        current_choices[name] = next_choices
        changed_choices[name] = next_choices
    return changed_choices
