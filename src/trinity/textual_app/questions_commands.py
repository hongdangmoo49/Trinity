"""Pure helpers for Textual questions command presentation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


@dataclass(frozen=True)
class QuestionsCommandPresentation:
    """Prepared local command result for `/questions`."""

    title: str
    body: str
    empty: bool
    action_hint: str
    table_columns: tuple[str, ...]
    table_rows: tuple[tuple[str, ...], ...]


def questions_command_presentation(
    snapshot: WorkflowNexusSnapshot,
    *,
    select_requested: bool = False,
    lang: str = "en",
) -> QuestionsCommandPresentation:
    """Return the presentation payload for a Textual `/questions` command."""
    has_questions = bool(snapshot.questions)
    return QuestionsCommandPresentation(
        title=textual_presenters.questions_title(lang=lang),
        body=(
            textual_presenters.questions_select_markdown(snapshot, lang=lang)
            if select_requested
            else textual_presenters.questions_markdown(snapshot, lang=lang)
        ),
        empty=not has_questions,
        action_hint=textual_presenters.questions_action_hint(
            has_questions=has_questions,
            lang=lang,
        ),
        table_columns=textual_presenters.questions_table_columns(lang=lang),
        table_rows=textual_presenters.questions_rows(snapshot, lang=lang),
    )


def questions_select_requested(args: Sequence[str]) -> bool:
    """Return whether `/questions` should show the selected-question body."""
    return any(arg.lower() in {"--select", "-s"} for arg in args)


def questions_command_presentation_from_args(
    args: Sequence[str],
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> QuestionsCommandPresentation:
    """Return the presentation payload for `/questions` arguments."""
    return questions_command_presentation(
        snapshot,
        select_requested=questions_select_requested(args),
        lang=lang,
    )
