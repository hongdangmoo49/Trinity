from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.textual_app.snapshot import QuestionSnapshot
from trinity.textual_app.widgets.question_panel import QuestionPanel


class QuestionPanelHarness(App[None]):
    def __init__(self, panel: QuestionPanel) -> None:
        super().__init__()
        self.panel = panel

    def compose(self) -> ComposeResult:
        yield self.panel


@pytest.mark.asyncio
async def test_question_panel_title_skips_unchanged_update() -> None:
    panel = QuestionPanel()
    question = QuestionSnapshot(
        id="q-1",
        question="Choose a direction?",
        options=["fast", "safe"],
    )
    app = QuestionPanelHarness(panel)

    async with app.run_test(size=(80, 20)) as pilot:
        panel.apply_questions([question])
        await pilot.pause()
        title = panel.query_one("#question-panel-title", Static)
        updates: list[str] = []
        original_update = title.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        title.update = counted_update

        panel.apply_questions([question])
        await pilot.pause()
        assert updates == []

        panel.apply_questions(
            [
                QuestionSnapshot(
                    id="q-1",
                    question="Choose a direction?",
                    options=["fast", "safe"],
                    answer="fast",
                )
            ]
        )
        await pilot.pause()

        assert updates == ["Answered Questions"]
