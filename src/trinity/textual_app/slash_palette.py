"""Textual command palette provider for Trinity slash commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from textual.command import DiscoveryHit, Hit, Hits, Provider

from trinity.slash_commands import COMMAND_SPECS
from trinity.textual_app.i18n import command_description

if TYPE_CHECKING:
    from trinity.textual_app.app import TrinityTextualApp


class SlashCommandPaletteProvider(Provider):
    """Expose Trinity-owned slash commands in Textual's command palette."""

    async def discover(self) -> Hits:
        for spec in COMMAND_SPECS:
            for name in spec.names:
                yield self._discovery_hit(name)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for spec in COMMAND_SPECS:
            for name in spec.names:
                summary = command_description(name, self._app_lang())
                search_text = f"{name} {spec.usage} {summary}"
                if (score := matcher.match(search_text)) > 0:
                    yield Hit(
                        score,
                        matcher.highlight(name),
                        self._callback(name),
                        text=name,
                        help=summary,
                    )

    def _discovery_hit(self, name: str) -> DiscoveryHit:
        return DiscoveryHit(
            name,
            self._callback(name),
            text=name,
            help=command_description(name, self._app_lang()),
        )

    def _callback(self, command: str) -> Callable[[], None]:
        def run_command() -> None:
            app = cast("TrinityTextualApp", self.app)
            app._handle_textual_slash_command(command)

        return run_command

    def _app_lang(self) -> str | None:
        config = getattr(self.app, "config", None)
        return getattr(config, "lang", None)
