"""Central synthesis view widget."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Grid, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Markdown, Static

from trinity.textual_app.snapshot import QuestionSnapshot, WorkflowNexusSnapshot


@dataclass(frozen=True)
class QuestionAnswer:
    """Question answer selected from the central view."""

    question_id: str
    answer: str


ACTIVITY_FRAMES = ("|", "/", "-", "\\")


class CentralAgentView(VerticalScroll):
    """Render synthesis summary, workflow status, and interactive questions."""

    class QuestionAnswered(Message):
        """Posted when a user selects one of the synthesized options."""

        def __init__(self, answer: QuestionAnswer) -> None:
            super().__init__()
            self.answer = answer

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.snapshot: WorkflowNexusSnapshot | None = None
        self._button_answers: dict[str, QuestionAnswer] = {}
        self._activity_frame = 0

    def compose(self) -> ComposeResult:
        yield Static("Central Agent", id="central-title")
        yield Markdown(self._markdown(), id="central-markdown")
        yield Static("", id="central-question-title")
        with Vertical(id="central-questions"):
            pass

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        self.snapshot = snapshot
        if not self.is_mounted:
            return
        self.set_class(self._is_running(), "central-running")
        self._refresh_title()
        self.query_one("#central-markdown", Markdown).update(self._markdown())
        self.query_one("#central-question-title", Static).update(
            self._question_title(snapshot.questions)
        )
        self._render_questions(snapshot.questions)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        answer = self._button_answers.get(button_id)
        if answer is None:
            return
        event.stop()
        self.post_message(self.QuestionAnswered(answer))

    def set_activity_frame(self, frame: int) -> None:
        self._activity_frame = frame % len(ACTIVITY_FRAMES)
        self._refresh_title()

    def _markdown(self) -> str:
        snapshot = self.snapshot
        if snapshot is None:
            return (
                "Waiting for synthesis.\n\n"
                "Planning does not require a workspace. Execute will ask for one."
            )

        lines = [
            f"**Workflow:** `{snapshot.session_id or '(new)'}`",
            f"**State:** `{snapshot.state}`",
            f"**Round:** `{snapshot.round_num}`",
        ]
        if snapshot.synthesis.consensus_progress:
            lines.append(f"**Synthesis:** `{snapshot.synthesis.consensus_progress}`")
        if snapshot.goal:
            lines.extend(["", "### Goal", snapshot.goal])
        if snapshot.synthesis.summary:
            lines.extend(["", "### Synthesis", snapshot.synthesis.summary])
        elif not snapshot.goal:
            lines.extend(
                [
                    "",
                    "Waiting for synthesis.",
                    "",
                    "Planning does not require a workspace.",
                ]
            )
        if snapshot.decisions:
            lines.extend(["", "### Decisions"])
            lines.extend(f"- {item}" for item in snapshot.decisions[:5])
        if snapshot.work_packages:
            lines.extend(["", "### Work Packages"])
            lines.extend(f"- {item}" for item in snapshot.work_packages[:5])
        return "\n".join(lines)

    def _render_questions(self, questions: list[QuestionSnapshot]) -> None:
        container = self.query_one("#central-questions", Vertical)
        container.remove_children()
        self._button_answers = {}
        for index, question in enumerate(questions[:3], start=1):
            container.mount(Static(f"{index}. {question.question}", classes="question-text"))
            if not question.options:
                continue
            row = Grid(classes="question-options")
            container.mount(row)
            for option_index, option in enumerate(question.options, start=1):
                button_id = f"answer-{question.id}-{option_index}"
                label = (
                    f"{option} (recommended)"
                    if option == question.recommended_option
                    else option
                )
                self._button_answers[button_id] = QuestionAnswer(question.id, option)
                row.mount(Button(label, id=button_id, variant="default", tooltip=label))

    @staticmethod
    def _question_title(questions: list[QuestionSnapshot]) -> str:
        if not questions:
            return ""
        return "Questions for you"

    def _refresh_title(self) -> None:
        if not self.is_mounted:
            return
        title = "Central Agent"
        if self._is_running():
            title = f"{title} {ACTIVITY_FRAMES[self._activity_frame]}"
        self.query_one("#central-title", Static).update(title)

    def _is_running(self) -> bool:
        snapshot = self.snapshot
        return bool(
            snapshot
            and snapshot.synthesis.status == "running"
        )
