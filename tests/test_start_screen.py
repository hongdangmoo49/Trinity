from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Static

from trinity.config import TrinityConfig
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)


class StartScreenHarness(App[None]):
    def __init__(self, screen: StartScreen) -> None:
        super().__init__()
        self.target_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.target_screen)


class _DisplayPath:
    def __init__(self, text: str) -> None:
        self.text = text

    def __str__(self) -> str:
        return self.text


@pytest.mark.asyncio
async def test_start_workspace_label_skips_unchanged_update(tmp_path: Path) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target"
    next_target = tmp_path / "next"
    control_repo.mkdir()
    target.mkdir()
    next_target.mkdir()
    screen = StartScreen(
        TrinityConfig.default_config(project_dir=control_repo),
        workspace_candidate=target,
    )
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        label = screen.query_one("#workspace-candidate", Static)
        updates: list[str] = []
        original_update = label.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        label.update = counted_update

        screen.set_workspace_candidate(target)
        await pilot.pause()
        assert updates == []

        screen.set_workspace_candidate(next_target)
        await pilot.pause()
        assert updates == [f"Target workspace: {next_target}"]


@pytest.mark.asyncio
async def test_start_workspace_candidate_skips_unchanged_widget_query(
    tmp_path: Path,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target"
    next_target = tmp_path / "next"
    control_repo.mkdir()
    target.mkdir()
    next_target.mkdir()
    screen = StartScreen(
        TrinityConfig.default_config(project_dir=control_repo),
        workspace_candidate=target,
    )
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        queries: list[str] = []
        original_query_one = screen.query_one

        def counted_query_one(selector, *args, **kwargs):
            queries.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        screen.query_one = counted_query_one

        screen.set_workspace_candidate(Path(str(target)))
        await pilot.pause()
        assert queries == []

        screen.set_workspace_candidate(next_target)
        await pilot.pause()
        assert queries == []


@pytest.mark.asyncio
async def test_start_workspace_label_skips_query_when_rendered_label_matches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target"
    control_repo.mkdir()
    target.mkdir()
    screen = StartScreen(
        TrinityConfig.default_config(project_dir=control_repo),
        workspace_candidate=target,
    )
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        queries: list[str] = []
        original_query_one = screen.query_one

        def counted_query_one(selector, *args, **kwargs):
            queries.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        monkeypatch.setattr(screen, "query_one", counted_query_one)

        screen.set_workspace_candidate(_DisplayPath(str(target)))
        await pilot.pause()

        assert queries == []


@pytest.mark.asyncio
async def test_start_screen_reuses_composed_action_widgets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target"
    next_target = tmp_path / "next"
    control_repo.mkdir()
    target.mkdir()
    next_target.mkdir()
    screen = StartScreen(
        TrinityConfig.default_config(project_dir=control_repo),
        workspace_candidate=target,
    )
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        queries: list[object] = []
        original_query_one = screen.query_one
        fixed_selectors = {
            "#start-composer",
            "#workspace-candidate",
            AgentRecipientModelSelector,
        }

        def counted_query_one(selector, *args, **kwargs):
            if selector in fixed_selectors:
                queries.append(selector)
            return original_query_one(selector, *args, **kwargs)

        monkeypatch.setattr(screen, "query_one", counted_query_one)

        screen.set_workspace_candidate(next_target)
        screen.action_submit()
        screen._submit("/status")
        screen._submit("Plan the API")
        await pilot.pause()

        assert queries == []
