from trinity.slash_commands import COMMAND_SPECS
from trinity.textual_app.slash_command_router import (
    TextualSlashCommandRoute,
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
    assert textual_slash_command_route("execute") == TextualSlashCommandRoute(
        "_handle_textual_execute_command",
        "name_args",
    )
