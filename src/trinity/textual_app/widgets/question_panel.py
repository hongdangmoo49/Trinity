"""User-facing question and answer panel for Nexus."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Grid, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Static

from trinity.textual_app.snapshot import QuestionSnapshot


@dataclass(frozen=True)
class QuestionAnswer:
    """Question answer selected from the Nexus question panel."""

    question_id: str
    answer: str


class QuestionPanel(VerticalScroll):
    """Render central-agent questions separately from the conversation surface."""

    class QuestionAnswered(Message):
        """Posted when a user selects one of the synthesized options."""

        def __init__(self, answer: QuestionAnswer) -> None:
            super().__init__()
            self.answer = answer

    def __init__(self, *, id: str | None = None, lang: str = "en") -> None:
        super().__init__(id=id)
        self.lang = lang
        self._button_answers: dict[str, QuestionAnswer] = {}
        self._questions_key: tuple[object, ...] | None = None
        self._empty_state_key: bool | None = None
        self._title_key = ""
        self._title_widget: Static | None = None
        self._body_container: Vertical | None = None

    def compose(self) -> ComposeResult:
        self._reset_widget_cache()
        title = Static("", id="question-panel-title")
        self._title_widget = title
        yield title
        body = Vertical(id="question-panel-body")
        self._body_container = body
        with body:
            pass

    def apply_questions(self, questions: list[QuestionSnapshot]) -> None:
        questions_key = self._question_key(questions)
        if self.is_mounted and questions_key == self._questions_key:
            return
        self._sync_empty_state(not questions)
        if not self.is_mounted:
            return
        title = self._question_title(questions)
        if title != self._title_key:
            self._title_static().update(title)
            self._title_key = title
        self._render_questions(questions)
        self._questions_key = questions_key

    def _sync_empty_state(self, empty: bool) -> None:
        if self._empty_state_key == empty:
            return
        self.set_class(empty, "question-panel-empty")
        self._empty_state_key = empty

    def on_button_pressed(self, event: Button.Pressed) -> None:
        answer = self._button_answers.get(event.button.id or "")
        if answer is None:
            return
        event.stop()
        self.post_message(self.QuestionAnswered(answer))

    def _render_questions(self, questions: list[QuestionSnapshot]) -> None:
        container = self._body_widget()
        container.remove_children()
        self._button_answers = {}
        if not questions:
            container.mount(
                Static(self._label("no_questions"), classes="question-empty")
            )
            return

        for question_number, question in enumerate(questions, start=1):
            status = self._rendered_status(question)
            status_label = self._status_label(status)
            container.mount(
                Static(
                    f"{question_number}. [{status_label}] {question.question}",
                    classes=(
                        "question-text "
                        + ("question-open" if not question.answer else "question-answered")
                    ),
                )
            )
            if question.answer:
                container.mount(
                    Static(
                        f"{self._label('answer')}: {question.answer}",
                        classes="question-answer",
                    )
                )
                continue
            if question.options and status == "open":
                row = Grid(classes="question-options")
                container.mount(row)
                for option_index, option in enumerate(question.options, start=1):
                    button_id = self._answer_button_id(question_number, option_index)
                    label = (
                        f"{option} ({self._label('recommended')})"
                        if option == question.recommended_option
                        else option
                    )
                    self._button_answers[button_id] = QuestionAnswer(question.id, option)
                    row.mount(
                        Button(
                            label,
                            id=button_id,
                            variant="primary"
                            if option == question.recommended_option
                            else "default",
                            tooltip=label,
                        )
                    )

    def _reset_widget_cache(self) -> None:
        self._title_widget = None
        self._body_container = None

    def _title_static(self) -> Static:
        if self._title_widget is None:
            self._title_widget = self.query_one("#question-panel-title", Static)
        return self._title_widget

    def _body_widget(self) -> Vertical:
        if self._body_container is None:
            self._body_container = self.query_one("#question-panel-body", Vertical)
        return self._body_container

    @staticmethod
    def _answer_button_id(question_number: int, option_index: int) -> str:
        return f"answer-q-{question_number}-{option_index}"

    @staticmethod
    def _question_key(questions: list[QuestionSnapshot]) -> tuple[object, ...]:
        return tuple(
            (
                question.id,
                question.question,
                tuple(question.options),
                question.recommended_option,
                QuestionPanel._rendered_status(question),
                question.answer,
            )
            for question in questions
        )

    @staticmethod
    def _rendered_status(question: QuestionSnapshot) -> str:
        return question.status or ("answered" if question.answer else "open")

    def _question_title(self, questions: list[QuestionSnapshot]) -> str:
        if not questions:
            return self._label("title_empty")
        open_count = sum(1 for question in questions if not question.answer)
        if open_count == 1:
            return self._label("title_one")
        if open_count > 1:
            return f"{self._label('title_many')} ({open_count})"
        return self._label("title_answered")

    def _label(self, key: str) -> str:
        ko = {
            "answer": "답변",
            "no_questions": "현재 답변할 질문이 없습니다.",
            "recommended": "추천",
            "title_answered": "답변 기록",
            "title_empty": "질문",
            "title_many": "질문",
            "title_one": "질문",
        }
        en = {
            "answer": "Answer",
            "no_questions": "No questions waiting for an answer.",
            "recommended": "recommended",
            "title_answered": "Answered Questions",
            "title_empty": "Questions",
            "title_many": "Questions for You",
            "title_one": "Question for You",
        }
        labels = ko if self.lang == "ko" else en
        return labels.get(key, key)

    def _status_label(self, status: str) -> str:
        if self.lang != "ko":
            return status
        labels = {
            "answered": "답변됨",
            "open": "답변 대기",
        }
        return labels.get(status, status)
