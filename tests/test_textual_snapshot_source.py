from __future__ import annotations

from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.snapshot_source import (
    current_textual_snapshot,
    fresh_textual_snapshot,
)


def _snapshot(session_id: str) -> WorkflowNexusSnapshot:
    return WorkflowNexusSnapshot(session_id=session_id)


def test_current_textual_snapshot_prefers_active_without_loading_fallbacks() -> None:
    calls: list[str] = []

    selected = current_textual_snapshot(
        active_snapshot=_snapshot("active"),
        controller_snapshot=lambda: calls.append("controller") or _snapshot("controller"),
        persisted_snapshot=lambda: calls.append("persisted") or _snapshot("persisted"),
    )

    assert selected.session_id == "active"
    assert calls == []


def test_current_textual_snapshot_uses_controller_before_persisted() -> None:
    calls: list[str] = []

    selected = current_textual_snapshot(
        active_snapshot=None,
        controller_snapshot=lambda: calls.append("controller") or _snapshot("controller"),
        persisted_snapshot=lambda: calls.append("persisted") or _snapshot("persisted"),
    )

    assert selected.session_id == "controller"
    assert calls == ["controller"]


def test_current_textual_snapshot_falls_back_to_persisted() -> None:
    calls: list[str] = []

    selected = current_textual_snapshot(
        active_snapshot=None,
        controller_snapshot=lambda: calls.append("controller") or None,
        persisted_snapshot=lambda: calls.append("persisted") or _snapshot("persisted"),
    )

    assert selected.session_id == "persisted"
    assert calls == ["controller", "persisted"]


def test_fresh_textual_snapshot_ignores_active_state_and_prefers_controller() -> None:
    calls: list[str] = []

    selected = fresh_textual_snapshot(
        controller_snapshot=lambda: calls.append("controller") or _snapshot("controller"),
        persisted_snapshot=lambda: calls.append("persisted") or _snapshot("persisted"),
    )

    assert selected.session_id == "controller"
    assert calls == ["controller"]


def test_fresh_textual_snapshot_falls_back_to_persisted() -> None:
    calls: list[str] = []

    selected = fresh_textual_snapshot(
        controller_snapshot=lambda: calls.append("controller") or None,
        persisted_snapshot=lambda: calls.append("persisted") or _snapshot("persisted"),
    )

    assert selected.session_id == "persisted"
    assert calls == ["controller", "persisted"]
