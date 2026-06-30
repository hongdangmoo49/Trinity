from trinity.slash_commands import COMMAND_SPECS
from trinity.textual_app.slash_command_router import (
    TextualSlashCommandDispatch,
    TextualSlashCommandRoute,
    textual_slash_command_dispatch,
    textual_slash_command_route,
)


def test_textual_slash_command_routes_cover_registered_commands() -> None:
    command_ids = {spec.command_id for spec in COMMAND_SPECS}
    alias_ids = {
        alias.removeprefix("/")
        for spec in COMMAND_SPECS
        for alias in spec.aliases
    }

    missing = sorted(
        command_id
        for command_id in command_ids | alias_ids
        if textual_slash_command_route(command_id) is None
    )

    assert missing == []


def test_textual_slash_command_route_argument_shapes() -> None:
    assert textual_slash_command_route("quit") == TextualSlashCommandRoute(
        "_handle_textual_quit_command"
    )
    assert textual_slash_command_route("help") == TextualSlashCommandRoute(
        "_handle_textual_help_command",
        "name",
    )
    assert textual_slash_command_route("memory") == TextualSlashCommandRoute(
        "_handle_textual_memory_command",
        "args",
    )
    assert textual_slash_command_route("project") == TextualSlashCommandRoute(
        "_handle_textual_project_command",
        "name_args",
    )
    assert textual_slash_command_route("providers") == TextualSlashCommandRoute(
        "_handle_textual_providers_command"
    )
    assert textual_slash_command_route("workspace") == TextualSlashCommandRoute(
        "_handle_textual_workspace_command"
    )
    assert textual_slash_command_route("execute") == TextualSlashCommandRoute(
        "_handle_textual_execute_command",
        "name_args",
    )


def test_textual_slash_command_dispatch_ignores_non_commands() -> None:
    assert textual_slash_command_dispatch("hello") is None
    assert textual_slash_command_dispatch("/") is None


def test_textual_slash_command_dispatch_routes_known_command() -> None:
    dispatch = textual_slash_command_dispatch("/help status")

    assert dispatch == TextualSlashCommandDispatch(
        route=TextualSlashCommandRoute("_handle_textual_help_command", "name"),
        command_name="/help",
        args=("status",),
    )


def test_textual_slash_command_dispatch_routes_project_action_args() -> None:
    dispatch = textual_slash_command_dispatch("/project analyze")

    assert dispatch == TextualSlashCommandDispatch(
        route=TextualSlashCommandRoute("_handle_textual_project_command", "name_args"),
        command_name="/project",
        args=("analyze",),
    )


def test_textual_slash_command_dispatch_records_syntax_error() -> None:
    dispatch = textual_slash_command_dispatch('/ask "unterminated')

    assert dispatch is not None
    assert dispatch.raw_command == '/ask "unterminated'
    assert dispatch.syntax_error.startswith("Invalid command syntax:")
    assert dispatch.route is None


def test_textual_slash_command_dispatch_records_unknown_command() -> None:
    dispatch = textual_slash_command_dispatch("/missing")

    assert dispatch == TextualSlashCommandDispatch(unknown_token="/missing")
