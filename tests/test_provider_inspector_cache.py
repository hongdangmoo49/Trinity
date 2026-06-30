from __future__ import annotations

from trinity.textual_app.snapshot import ProviderSnapshot
from trinity.textual_app.widgets.provider_inspector import (
    format_provider_inspector_output,
    provider_inspector_provider_output,
)


def test_provider_inspector_caches_formatted_provider_output() -> None:
    provider = ProviderSnapshot(
        name="codex",
        provider="codex",
        enabled=True,
        status="Ready",
        raw_output='{"name":"Trinity","items":[{"id":1}]}',
    )
    formatted_cache: dict[str, str] = {}
    calls: list[str] = []

    def counted_format_output(output: str, *, lang: str = "en") -> str:
        calls.append(output)
        return format_provider_inspector_output(output, lang=lang)

    first = provider_inspector_provider_output(
        provider,
        formatted_output_cache=formatted_cache,
        format_output=counted_format_output,
    )
    second = provider_inspector_provider_output(
        provider,
        formatted_output_cache=formatted_cache,
        format_output=counted_format_output,
    )

    assert first == second
    assert calls == [provider.raw_output]
    assert '"name": "Trinity"' in first
