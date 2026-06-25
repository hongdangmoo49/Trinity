from __future__ import annotations

import pytest
from textual.app import App

from trinity.textual_app.widgets.resume_picker import ResumeWorkflowPicker
from trinity.textual_app.workflow_controller import TextualWorkflowArchiveOption


class ResumePickerHarness(App[None]):
    def __init__(self, picker: ResumeWorkflowPicker) -> None:
        super().__init__()
        self.picker = picker

    def on_mount(self) -> None:
        self.push_screen(self.picker)


def _archives() -> list[TextualWorkflowArchiveOption]:
    return [
        TextualWorkflowArchiveOption(
            selector=str(index),
            session_id=f"wf-{index}",
            goal=f"Goal {index}",
            state="idle",
            updated_at=1_700_000_000.0 + index,
        )
        for index in range(3)
    ]


@pytest.mark.asyncio
async def test_resume_picker_reuses_composed_focus_controls() -> None:
    picker = ResumeWorkflowPicker(_archives())
    app = ResumePickerHarness(picker)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        assert len(picker._archive_buttons) == 3
        assert picker._archive_list_widget is not None

        query_calls: list[str] = []
        original_query = picker.query
        original_query_one = picker.query_one

        def counted_query(selector, *args, **kwargs):
            if selector == ".resume-archive-option":
                query_calls.append(str(selector))
            return original_query(selector, *args, **kwargs)

        def counted_query_one(selector, *args, **kwargs):
            if selector == "#resume-archive-list":
                query_calls.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        picker.query = counted_query
        picker.query_one = counted_query_one

        picker.action_cursor_down()
        await pilot.pause()
        picker.action_cursor_up()
        await pilot.pause()

        assert query_calls == []
        assert picker.selected_index == 0
