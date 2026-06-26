"""Routing table for Textual-owned slash commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SlashCommandArgumentShape = Literal["none", "name", "args", "name_args"]


@dataclass(frozen=True)
class TextualSlashCommandRoute:
    """Describe how a parsed slash command maps to a TextualApp handler."""

    handler_name: str
    argument_shape: SlashCommandArgumentShape = "none"


TEXTUAL_SLASH_COMMAND_ROUTES: dict[str, TextualSlashCommandRoute] = {
    "quit": TextualSlashCommandRoute("_handle_textual_quit_command"),
    "exit": TextualSlashCommandRoute("_handle_textual_quit_command"),
    "q": TextualSlashCommandRoute("_handle_textual_quit_command"),
    "help": TextualSlashCommandRoute("_handle_textual_help_command", "name"),
    "status": TextualSlashCommandRoute("_handle_textual_status_command", "name"),
    "workflow": TextualSlashCommandRoute("_handle_textual_workflow_command", "name"),
    "questions": TextualSlashCommandRoute(
        "_handle_textual_questions_command",
        "name_args",
    ),
    "decisions": TextualSlashCommandRoute("_handle_textual_decisions_command", "name"),
    "packages": TextualSlashCommandRoute("_handle_textual_packages_command", "name"),
    "subtasks": TextualSlashCommandRoute("_handle_textual_subtasks_command", "name"),
    "context": TextualSlashCommandRoute("_handle_textual_context_command", "name"),
    "model": TextualSlashCommandRoute("_handle_textual_model_command"),
    "memory": TextualSlashCommandRoute("_handle_textual_memory_command", "args"),
    "artifact": TextualSlashCommandRoute("_handle_textual_artifact_command", "args"),
    "history": TextualSlashCommandRoute("_handle_textual_history_command", "name"),
    "report": TextualSlashCommandRoute("_handle_textual_report_command", "args"),
    "rounds": TextualSlashCommandRoute("_handle_textual_rounds_command", "name_args"),
    "agent": TextualSlashCommandRoute("_handle_textual_agent_command", "name_args"),
    "caveman": TextualSlashCommandRoute(
        "_handle_textual_caveman_command",
        "name_args",
    ),
    "save": TextualSlashCommandRoute("_handle_textual_save_command", "name"),
    "target": TextualSlashCommandRoute("_handle_textual_target_command", "args"),
    "resume": TextualSlashCommandRoute("_handle_textual_resume_command", "args"),
    "answer": TextualSlashCommandRoute("_handle_textual_answer_command", "args"),
    "ask": TextualSlashCommandRoute("_handle_textual_ask_command", "name_args"),
    "execute-retry": TextualSlashCommandRoute(
        "_handle_textual_execute_retry_command",
        "args",
    ),
    "review": TextualSlashCommandRoute("_handle_textual_review_command", "name_args"),
    "improve": TextualSlashCommandRoute("_handle_textual_improve_command", "name_args"),
    "execute": TextualSlashCommandRoute("_handle_textual_execute_command", "name_args"),
}


def textual_slash_command_route(command_id: str) -> TextualSlashCommandRoute | None:
    """Return the TextualApp handler route for a command id."""
    return TEXTUAL_SLASH_COMMAND_ROUTES.get(command_id)
