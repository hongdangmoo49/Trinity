from __future__ import annotations

import threading
from collections.abc import Sequence

from trinity.config import TrinityConfig
from trinity.models import Provider
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.textual_app.model_discovery import (
    iter_discovered_agent_model_choices,
    merge_discovered_model_choices,
)


def _choice(provider: Provider, model: str = "default") -> ProviderModelChoice:
    return ProviderModelChoice(
        provider=provider,
        model=model,
        label=model,
        source="static-fallback",
        is_default=model == "default",
    )


def test_iter_discovered_agent_model_choices_yields_as_each_provider_finishes(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    config.agents["antigravity"].enabled = True
    fast_discovery_done = threading.Event()
    fast_provider_count = 0
    fast_provider_lock = threading.Lock()

    def discover(
        provider: Provider,
        cli_command: str,
        *,
        timeout_seconds: float,
        use_cache: bool,
    ) -> Sequence[ProviderModelChoice]:
        nonlocal fast_provider_count
        assert timeout_seconds == 10.0
        assert use_cache is False
        if provider == Provider.CLAUDE_CODE:
            assert fast_discovery_done.wait(timeout=2.0)
        else:
            with fast_provider_lock:
                fast_provider_count += 1
                if fast_provider_count == 2:
                    fast_discovery_done.set()
        return [_choice(provider)]

    discovered = list(
        iter_discovered_agent_model_choices(
            config.agents.items(),
            use_cache=False,
            discover=discover,
        )
    )

    assert discovered[-1][0] == "claude"
    assert {name for name, _choices in discovered} >= {"claude", "codex", "antigravity"}


def test_iter_discovered_agent_model_choices_skips_failures_and_empty_choices(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    config.agents["antigravity"].enabled = True

    def discover(
        provider: Provider,
        cli_command: str,
        *,
        timeout_seconds: float,
        use_cache: bool,
    ) -> Sequence[ProviderModelChoice]:
        if provider == Provider.CODEX:
            raise RuntimeError("codex unavailable")
        if provider == Provider.ANTIGRAVITY_CLI:
            return []
        return [_choice(provider)]

    discovered = list(
        iter_discovered_agent_model_choices(
            config.agents.items(),
            use_cache=False,
            discover=discover,
        )
    )

    assert discovered == [("claude", (_choice(Provider.CLAUDE_CODE),))]


def test_merge_discovered_model_choices_returns_only_changed_agents() -> None:
    initial = (_choice(Provider.CLAUDE_CODE),)
    updated = (*initial, _choice(Provider.CLAUDE_CODE, "opus"))
    current = {
        "claude": initial,
        "codex": (_choice(Provider.CODEX),),
    }

    changed = merge_discovered_model_choices(
        current,
        {
            "claude": updated,
            "codex": (_choice(Provider.CODEX),),
        },
    )

    assert changed == {"claude": updated}
    assert current["claude"] == updated
    assert current["codex"] == (_choice(Provider.CODEX),)
