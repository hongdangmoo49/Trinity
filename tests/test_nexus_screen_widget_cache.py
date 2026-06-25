from __future__ import annotations

import pytest
from textual.app import App

from trinity.config import TrinityConfig
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.snapshot import (
    ProviderSnapshot,
    QuestionSnapshot,
    WorkflowNexusSnapshot,
)
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)
from trinity.textual_app.widgets.central_agent import CentralAgentView
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.textual_app.widgets.inspector import WorkflowInspector
from trinity.textual_app.widgets.question_panel import QuestionPanel


class NexusHarness(App[None]):
    def __init__(self, screen: NexusScreen) -> None:
        super().__init__()
        self.nexus = screen

    def on_mount(self) -> None:
        self.push_screen(self.nexus)


@pytest.mark.asyncio
async def test_nexus_screen_reuses_composed_fixed_widgets(
    tmp_path,
    monkeypatch,
) -> None:
    screen = NexusScreen(TrinityConfig.default_config(project_dir=tmp_path))
    app = NexusHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        query_calls: list[str] = []
        original_query = screen.query
        original_query_one = screen.query_one
        fixed_string_selectors = {
            "#provider-claude",
            "#nexus-target-workspace",
            "#nexus-composer",
        }
        fixed_type_selectors = {
            AgentRecipientModelSelector,
            CentralAgentView,
            QuestionPanel,
            WorkflowInspector,
        }

        def counted_query(selector, *args, **kwargs):
            if selector in fixed_string_selectors:
                query_calls.append(str(selector))
            return original_query(selector, *args, **kwargs)

        def counted_query_one(selector, *args, **kwargs):
            if selector in fixed_string_selectors or selector in fixed_type_selectors:
                query_calls.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        monkeypatch.setattr(screen, "query", counted_query)
        monkeypatch.setattr(screen, "query_one", counted_query_one)

        screen.set_workspace_candidate(tmp_path / "project-a")
        screen.set_agent_selection(("claude",), {})
        screen._submit_follow_up("Clarify the API contract")
        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                state="deliberating",
                goal="Build API",
                target_workspace=str(tmp_path / "project-a"),
                providers=[
                    ProviderSnapshot(
                        name="claude",
                        provider="claude-code",
                        enabled=True,
                        status="Running",
                        summary="Drafting architecture.",
                    )
                ],
                questions=[
                    QuestionSnapshot(
                        id="q-1",
                        question="Choose the API style?",
                        options=["REST", "GraphQL"],
                    )
                ],
            )
        )
        screen.update_provider("claude", status="Ready", summary="Done.")
        screen.advance_activity_frame()
        await pilot.pause()

        assert query_calls == []
