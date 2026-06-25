from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from trinity.textual_app.widgets.agent_recipient_model_selector import AgentToggle


class AgentToggleHarness(App[None]):
    def __init__(self, toggle: AgentToggle) -> None:
        super().__init__()
        self.toggle = toggle

    def compose(self) -> ComposeResult:
        yield self.toggle


@pytest.mark.asyncio
async def test_agent_toggle_set_value_skips_unchanged_refresh() -> None:
    toggle = AgentToggle(
        "claude",
        "Claude",
        value=True,
        enabled=True,
        id="recipient-claude",
    )
    app = AgentToggleHarness(toggle)

    async with app.run_test(size=(40, 8)) as pilot:
        await pilot.pause()
        updates: list[str] = []
        original_update = toggle.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        toggle.update = counted_update

        toggle.set_value(True)
        await pilot.pause()
        assert updates == []

        toggle.set_value(False)
        await pilot.pause()
        assert updates == ["[ ] Claude"]
