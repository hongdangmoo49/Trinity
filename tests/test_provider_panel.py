from __future__ import annotations

import pytest

from trinity.textual_app.widgets.provider_panel import (
    ProviderPanel,
    ProviderPanelState,
)


@pytest.mark.parametrize(
    ("status", "expected_state", "expected_label"),
    [
        ("Running", "running", "RUN"),
        ("Queued", "waiting", "WAIT"),
        ("Pending", "waiting", "WAIT"),
        ("Idle", "idle", "IDLE"),
        ("Ready", "done", "DONE"),
        ("Done", "done", "DONE"),
        ("Failed", "issue", "ISSUE"),
        ("Blocked", "issue", "ISSUE"),
        ("mystery", "unknown", "?"),
    ],
)
def test_provider_panel_normalizes_status_labels(
    status: str,
    expected_state: str,
    expected_label: str,
) -> None:
    state = ProviderPanelState(
        name="codex",
        provider="codex",
        enabled=True,
        status=status,
    )
    panel = ProviderPanel(state)

    assert ProviderPanel._state_group(state) == expected_state
    assert expected_label in panel._status_label()
    assert f"provider-state-{expected_state}" in ProviderPanel._classes_for(state)


def test_provider_panel_uses_off_state_for_disabled_provider() -> None:
    state = ProviderPanelState(
        name="codex",
        provider="codex",
        enabled=False,
        status="Running",
    )
    panel = ProviderPanel(state)

    assert ProviderPanel._state_group(state) == "off"
    assert panel._status_label() == "OFF"
    assert "provider-disabled" in ProviderPanel._classes_for(state)


def test_provider_panel_supports_korean_status_labels() -> None:
    state = ProviderPanelState(
        name="claude",
        provider="claude-code",
        enabled=True,
        status="Running",
    )
    panel = ProviderPanel(state, lang="ko")

    assert "실행" in panel._status_label()


def test_provider_panel_compacts_long_summary() -> None:
    state = ProviderPanelState(
        name="claude",
        provider="claude-code",
        enabled=True,
        status="Ready",
        summary=" ".join(f"line-{index}" for index in range(20)),
    )
    panel = ProviderPanel(state)

    assert len(panel._summary_line()) <= 72
    assert panel._summary_line().endswith("…")
