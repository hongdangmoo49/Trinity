"""Central synthesis view widget."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Grid, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, DataTable, Markdown, Static

from trinity.textual_app.snapshot import (
    LocalCommandSnapshot,
    QuestionSnapshot,
    WorkflowNexusSnapshot,
)


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
        with Vertical(id="central-local-command-tables"):
            pass
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
        self._render_local_command_tables(snapshot.local_commands)
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
        if snapshot.local_commands:
            lines.extend(["", "### Local Command Results"])
            for item in snapshot.local_commands:
                lines.extend(
                    [
                        f"#### {item.command} - {item.title}",
                        item.body,
                    ]
                )
        if snapshot.decisions:
            lines.extend(["", "### Decisions"])
            lines.extend(f"- {item}" for item in snapshot.decisions)
        if snapshot.central_work_packages:
            lines.extend(["", "### Central WP Graph"])
            lines.extend(f"- {item}" for item in snapshot.central_work_packages)
        if snapshot.work_packages:
            heading = (
                "### Local WP Graph"
                if snapshot.central_work_packages
                else "### Work Packages"
            )
            lines.extend(["", heading])
            lines.extend(f"- {item}" for item in snapshot.work_packages)
        if snapshot.work_package_repairs:
            lines.extend(["", "### Local Policy Repairs"])
            lines.extend(f"- {item}" for item in snapshot.work_package_repairs)
        return "\n".join(lines)

    def _render_local_command_tables(
        self,
        commands: list[LocalCommandSnapshot],
    ) -> None:
        container = self.query_one("#central-local-command-tables", Vertical)
        container.remove_children()
        table_commands = [
            command
            for command in commands
            if command.table_columns and command.table_rows
        ]
        if not table_commands:
            return

        for command in table_commands:
            container.mount(
                Static(
                    f"{command.command} - {command.title}",
                    classes="local-command-table-title",
                )
            )
            table = DataTable(
                classes="local-command-table",
                show_header=True,
            )
            container.mount(table)
            table.add_columns(*command.table_columns)
            table.add_rows(command.table_rows)

    def _render_questions(self, questions: list[QuestionSnapshot]) -> None:
        container = self.query_one("#central-questions", Vertical)
        container.remove_children()
        self._button_answers = {}
        if not questions:
            return

        for question_number, question in enumerate(questions, start=1):
            row = Grid(classes="question-options")
            status = question.status or "open"
            container.mount(
                Static(
                    f"{question_number}. [{status}] {question.question}",
                    classes="question-text",
                )
            )
            if question.answer:
                container.mount(
                    Static(f"Answer: {question.answer}", classes="question-answer")
                )
                continue
            if question.options and status == "open":
                container.mount(row)
                for option_index, option in enumerate(question.options, start=1):
                    button_id = self._answer_button_id(question_number, option_index)
                    label = (
                        f"{option} (recommended)"
                        if option == question.recommended_option
                        else option
                    )
                    self._button_answers[button_id] = QuestionAnswer(question.id, option)
                    row.mount(Button(label, id=button_id, variant="default", tooltip=label))

    @staticmethod
    def _answer_button_id(question_number: int, option_index: int) -> str:
        return f"answer-q-{question_number}-{option_index}"

    def _question_title(self, questions: list[QuestionSnapshot]) -> str:
        if not questions:
            return ""
        if len(questions) == 1:
            return "Question for you"
        return f"Questions for you ({len(questions)})"

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
