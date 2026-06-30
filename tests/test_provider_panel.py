from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.textual_app.widgets.provider_panel import (
    ProviderPanel,
    ProviderPanelState,
    provider_panel_classes,
    provider_panel_state_group,
)


class ProviderPanelHarness(App[None]):
    def __init__(self, panel: ProviderPanel) -> None:
        super().__init__()
        self.panel = panel

    def compose(self) -> ComposeResult:
        yield self.panel


@pytest.mark.parametrize(
    ("status", "expected_state", "expected_label"),
    [
        ("Running", "running", "RUN"),
        ("Queued", "waiting", "WAIT"),
        ("Pending", "waiting", "WAIT"),
        ("needs_user_decision", "waiting", "WAIT"),
        ("waiting_for_external_input", "waiting", "WAIT"),
        ("Idle", "idle", "IDLE"),
        ("Ready", "done", "DONE"),
        ("Done", "done", "DONE"),
        ("succeeded", "done", "DONE"),
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

    assert provider_panel_state_group(state) == expected_state
    assert expected_label in panel._status_label()
    assert f"provider-state-{expected_state}" in provider_panel_classes(state)


def test_provider_panel_uses_off_state_for_disabled_provider() -> None:
    state = ProviderPanelState(
        name="codex",
        provider="codex",
        enabled=False,
        status="Running",
    )
    panel = ProviderPanel(state)

    assert provider_panel_state_group(state) == "off"
    assert panel._status_label() == "OFF"
    assert "provider-disabled" in provider_panel_classes(state)


def test_provider_panel_supports_korean_status_labels() -> None:
    state = ProviderPanelState(
        name="claude",
        provider="claude-code",
        enabled=True,
        status="Running",
    )
    panel = ProviderPanel(state, lang="ko")

    assert "실행" in panel._status_label()


@pytest.mark.parametrize(
    ("status", "enabled", "expected_label"),
    [
        ("Running", True, "실행"),
        ("Queued", True, "대기"),
        ("needs_user_decision", True, "대기"),
        ("waiting_for_external_input", True, "대기"),
        ("Idle", True, "휴식"),
        ("Done", True, "완료"),
        ("succeeded", True, "완료"),
        ("Failed", True, "문제"),
        ("mystery", True, "?"),
        ("Running", False, "끔"),
    ],
)
def test_provider_panel_supports_all_korean_status_labels(
    status: str,
    enabled: bool,
    expected_label: str,
) -> None:
    state = ProviderPanelState(
        name="claude",
        provider="claude-code",
        enabled=enabled,
        status=status,
    )
    panel = ProviderPanel(state, lang="ko")

    assert expected_label in panel._status_label()


@pytest.mark.asyncio
async def test_provider_panel_activity_frame_updates_only_running_status() -> None:
    ready_panel = ProviderPanel(
        ProviderPanelState(
            name="codex",
            provider="codex",
            enabled=True,
            status="Ready",
        )
    )
    app = ProviderPanelHarness(ready_panel)

    async with app.run_test(size=(60, 10)) as pilot:
        await pilot.pause()
        status = ready_panel.query_one(".provider-status", Static)
        updates: list[str] = []
        original_update = status.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        status.update = counted_update

        ready_panel.set_activity_frame(1)
        await pilot.pause()

        assert ready_panel._activity_frame == 1
        assert updates == []


@pytest.mark.asyncio
async def test_provider_panel_activity_frame_updates_running_status() -> None:
    running_panel = ProviderPanel(
        ProviderPanelState(
            name="codex",
            provider="codex",
            enabled=True,
            status="Running",
        )
    )
    app = ProviderPanelHarness(running_panel)

    async with app.run_test(size=(60, 10)) as pilot:
        await pilot.pause()
        status = running_panel.query_one(".provider-status", Static)
        updates: list[str] = []
        original_update = status.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        status.update = counted_update

        running_panel.set_activity_frame(1)
        await pilot.pause()

        assert updates == ["/ RUN"]

        updates.clear()
        running_panel.set_activity_frame(1)
        await pilot.pause()

        assert updates == []


@pytest.mark.asyncio
async def test_provider_panel_activity_frame_uses_cached_status_widget() -> None:
    running_panel = ProviderPanel(
        ProviderPanelState(
            name="codex",
            provider="codex",
            enabled=True,
            status="Running",
        )
    )
    app = ProviderPanelHarness(running_panel)

    async with app.run_test(size=(60, 10)) as pilot:
        await pilot.pause()
        queries: list[str] = []
        original_query_one = running_panel.query_one

        def counted_query_one(selector, *args, **kwargs):
            if selector == ".provider-status":
                queries.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        running_panel.query_one = counted_query_one

        running_panel.set_activity_frame(1)
        await pilot.pause()

        assert queries == []
        assert str(
            running_panel._static_cache[".provider-status"].content
        ) == "/ RUN"


@pytest.mark.asyncio
async def test_provider_panel_status_change_updates_only_status_field() -> None:
    panel = ProviderPanel(
        ProviderPanelState(
            name="codex",
            provider="codex",
            enabled=True,
            status="Running",
            summary="Working on task.",
        )
    )
    app = ProviderPanelHarness(panel)

    async with app.run_test(size=(60, 10)) as pilot:
        await pilot.pause()
        widgets = {
            "name": panel.query_one(".provider-name", Static),
            "meta": panel.query_one(".provider-meta", Static),
            "status": panel.query_one(".provider-status", Static),
            "summary": panel.query_one(".provider-summary", Static),
        }
        updates: dict[str, list[str]] = {key: [] for key in widgets}

        for key, widget in widgets.items():
            original_update = widget.update

            def counted_update(
                content,
                *,
                key=key,
                original_update=original_update,
            ) -> None:
                updates[key].append(str(content))
                original_update(content)

            widget.update = counted_update

        panel.update_state(
            ProviderPanelState(
                name="codex",
                provider="codex",
                enabled=True,
                status="Ready",
                summary="Working on task.",
            )
        )
        await pilot.pause()

        assert updates == {
            "name": [],
            "meta": [],
            "status": ["DONE"],
            "summary": [],
        }


@pytest.mark.asyncio
async def test_provider_panel_summary_change_skips_unchanged_classes() -> None:
    panel = ProviderPanel(
        ProviderPanelState(
            name="codex",
            provider="codex",
            enabled=True,
            status="Running",
            summary="First update.",
        )
    )
    app = ProviderPanelHarness(panel)

    async with app.run_test(size=(60, 10)) as pilot:
        await pilot.pause()
        class_updates: list[str] = []
        original_set_classes = panel.set_classes

        def counted_set_classes(classes: str) -> None:
            class_updates.append(classes)
            original_set_classes(classes)

        panel.set_classes = counted_set_classes

        panel.update_state(
            ProviderPanelState(
                name="codex",
                provider="codex",
                enabled=True,
                status="Running",
                summary="Second update.",
            )
        )
        await pilot.pause()

        assert class_updates == []
        assert "Second update." in str(
            panel.query_one(".provider-summary", Static).content
        )


def test_provider_panel_treats_error_summary_as_issue() -> None:
    state = ProviderPanelState(
        name="claude",
        provider="claude-code",
        enabled=True,
        status="Ready",
        summary="[Error: exit code 1]",
    )
    panel = ProviderPanel(state)
    ko_panel = ProviderPanel(state, lang="ko")

    assert provider_panel_state_group(state) == "issue"
    assert "ISSUE" in panel._status_label()
    assert "문제" in ko_panel._status_label()


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


def test_provider_panel_shows_compact_model_context_and_session_metadata() -> None:
    state = ProviderPanelState(
        name="codex",
        provider="codex",
        enabled=True,
        status="Ready",
        configured_model="default",
        actual_model="gpt-5.5",
        context_window=272000,
        budget_source="local_cli_cache",
        session_id="019ea9e3-426f",
        output_contract="execution_v1",
    )
    panel = ProviderPanel(state)

    assert panel._provider_line() == (
        "codex · gpt-5.5 · ctx 272K/local · sid 019ea9e3 · out execution_v1"
    )


def test_provider_panel_localizes_compact_source_metadata() -> None:
    state = ProviderPanelState(
        name="codex",
        provider="codex",
        enabled=True,
        status="Ready",
        actual_model="gpt-5.5",
        context_window=272000,
        budget_source="local_cli_cache",
    )
    panel = ProviderPanel(state, lang="ko")

    assert "컨텍스트 272K/로컬" in panel._provider_line()


def test_provider_panel_localizes_korean_compact_metadata_labels() -> None:
    state = ProviderPanelState(
        name="codex",
        provider="codex",
        enabled=True,
        status="Ready",
        actual_model="gpt-5.5",
        context_window=272000,
        budget_source="local_cli_cache",
        session_id="019ea9e3-426f",
        output_contract="execution_v1",
        quality_signal_count=3,
        quality_success_count=2,
        quality_score=0.667,
    )
    panel = ProviderPanel(state, lang="ko")

    assert panel._provider_line() == (
        "codex · gpt-5.5 · 컨텍스트 272K/로컬 · 세션 019ea9e3 · "
        "출력 실행 v1 · 품질 0.667 2/3"
    )


def test_provider_panel_shows_compact_quality_signal_metadata() -> None:
    state = ProviderPanelState(
        name="codex",
        provider="codex",
        enabled=True,
        status="Ready",
        quality_signal_count=3,
        quality_success_count=2,
        quality_score=0.667,
    )
    panel = ProviderPanel(state)

    assert panel._provider_line() == "codex · q 0.667 2/3"


def test_provider_panel_does_not_duplicate_snapshot_provider_model_label() -> None:
    state = ProviderPanelState(
        name="codex",
        provider="codex · gpt-5.5",
        enabled=True,
        status="Ready",
        configured_model="default",
        actual_model="gpt-5.5",
        context_window=272000,
        budget_source="runtime_metadata",
    )
    panel = ProviderPanel(state)

    assert panel._provider_line().count("gpt-5.5") == 1
    assert "ctx 272K/runtime" in panel._provider_line()
