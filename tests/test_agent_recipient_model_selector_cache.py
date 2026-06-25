from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from trinity.config import TrinityConfig
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)


class SelectorHarness(App[None]):
    def __init__(self, selector: AgentRecipientModelSelector) -> None:
        super().__init__()
        self.selector = selector

    def compose(self) -> ComposeResult:
        yield self.selector


@pytest.mark.asyncio
async def test_agent_selector_reuses_composed_toggle_widgets(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["claude"].enabled = True
    config.agents["codex"].enabled = True
    config.agents["codex"].model = "default"
    selector = AgentRecipientModelSelector(config.agents)
    app = SelectorHarness(selector)

    async with app.run_test(size=(100, 16)) as pilot:
        await pilot.pause()
        query_calls: list[str] = []
        original_query_one = selector.query_one

        def counted_query_one(query, *args, **kwargs):
            if isinstance(query, str) and query.startswith("#recipient-"):
                query_calls.append(query)
            return original_query_one(query, *args, **kwargs)

        selector.query_one = counted_query_one

        selector.set_selected_agents(("codex",))
        assert selector.selected_agents() == ("codex",)

        selector.set_model_overrides({"codex": "gpt-5"})
        assert selector.model_overrides() == {"codex": "gpt-5"}

        selector.set_selected_agents(("claude", "codex"))
        assert selector.selected_agents() == ("claude", "codex")
        await pilot.pause()

        assert query_calls == []
