from __future__ import annotations

from trinity.textual_app.snapshot import ProviderSnapshot
from trinity.textual_app.widgets.provider_inspector import ProviderInspector


def test_provider_inspector_caches_formatted_provider_output(monkeypatch) -> None:
    provider = ProviderSnapshot(
        name="codex",
        provider="codex",
        enabled=True,
        status="Ready",
        raw_output='{"name":"Trinity","items":[{"id":1}]}',
    )
    inspector = ProviderInspector([provider])
    original_format_output = inspector._format_output
    calls: list[str] = []

    def counted_format_output(output: str, *, lang: str = "en") -> str:
        calls.append(output)
        return original_format_output(output, lang=lang)

    monkeypatch.setattr(inspector, "_format_output", counted_format_output)

    first = inspector._provider_output(provider)
    second = inspector._provider_output(provider)

    assert first == second
    assert calls == [provider.raw_output]
    assert '"name": "Trinity"' in first
