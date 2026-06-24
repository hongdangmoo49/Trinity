"""Provider output inspector modal."""

from __future__ import annotations

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, RichLog, Static, TabbedContent, TabPane

from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.snapshot import ProviderSnapshot

MAX_PRETTY_PRINT_CHARS = 200_000
MAX_DISPLAY_CHARS = 50_000


class ProviderInspector(ModalScreen[None]):
    """Tabbed modal for provider raw output inspection."""

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    LOCALIZED_BINDINGS = {
        ("escape", "close"): ("binding_close", None),
    }

    def __init__(self, providers: list[ProviderSnapshot], *, lang: str = "en") -> None:
        super().__init__()
        self.providers = providers
        self.lang = lang
        self._output_cache: dict[str, str] = {}
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        with Vertical(id="provider-inspector"):
            yield Static("Provider Inspector", id="provider-inspector-title")
            with TabbedContent(id="provider-inspector-tabs"):
                for provider in self.providers:
                    with TabPane(provider.name.title(), id=f"inspect-{provider.name}"):
                        yield from self._provider_output_widgets(provider)
                with TabPane("All", id="inspect-all"):
                    yield self._output_area(self._all_output())
            yield Button("Close", id="close-provider-inspector", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-provider-inspector":
            event.stop()
            self.dismiss()

    def action_close(self) -> None:
        self.dismiss()

    def _provider_output_widgets(self, provider: ProviderSnapshot) -> ComposeResult:
        yield Static(self._provider_meta(provider), classes="provider-inspector-meta")
        yield self._output_area(self._provider_output(provider))

    def _output_area(self, text: str) -> RichLog:
        output = RichLog(
            wrap=True,
            min_width=1,
            markup=False,
            highlight=False,
            auto_scroll=False,
            classes="provider-inspector-output",
        )
        output.write(text)
        return output

    def _provider_output(self, provider: ProviderSnapshot) -> str:
        output = (
            provider.raw_output
            or self._read_provider_output_path(provider.raw_output_path)
            or provider.summary
            or "No raw output captured yet."
        )
        return self._format_output(output)

    def _provider_meta(self, provider: ProviderSnapshot) -> str:
        lines = [
            provider.name.title(),
            f"Provider: {provider.provider}",
            f"Status: {provider.status}",
            f"Readiness: {provider.readiness}",
        ]
        if provider.profile_mission:
            lines.append(f"Mission: {provider.profile_mission}")
        if provider.profile_modes:
            lines.append(f"Modes: {', '.join(provider.profile_modes)}")
        if provider.profile_strengths:
            lines.append(f"Strengths: {', '.join(provider.profile_strengths)}")
        if provider.context_profile:
            lines.append(f"Context profile: {provider.context_profile}")
        if provider.output_contract:
            lines.append(f"Output contract: {provider.output_contract}")
        if provider.quality_signal_count:
            lines.append(
                "Quality signals: "
                f"score {_format_score(provider.quality_score)}, "
                f"success {provider.quality_success_count}/"
                f"{provider.quality_signal_count}, "
                f"blockers {provider.quality_blocker_count}, "
                f"required changes {provider.quality_required_change_count}"
            )
        return "\n".join(lines)

    def _all_output(self) -> str:
        sections: list[str] = []
        for provider in self.providers:
            sections.extend(
                [
                    f"## {provider.name.title()}",
                    f"Provider: {provider.provider}",
                    f"Status: {provider.status}",
                    f"Readiness: {provider.readiness}",
                    f"Mission: {provider.profile_mission or '-'}",
                    f"Context profile: {provider.context_profile or '-'}",
                    f"Output contract: {provider.output_contract or '-'}",
                    (
                        "Quality signals: "
                        f"score {_format_score(provider.quality_score)}, "
                        f"success {provider.quality_success_count}/"
                        f"{provider.quality_signal_count}, "
                        f"blockers {provider.quality_blocker_count}, "
                        "required changes "
                        f"{provider.quality_required_change_count}"
                    )
                    if provider.quality_signal_count
                    else "Quality signals: -",
                    "",
                    self._provider_output(provider),
                ]
            )
        return "\n\n---\n\n".join(sections)

    @classmethod
    def _format_output(cls, output: str) -> str:
        text = output.strip()
        if not text:
            return output
        if len(text) > MAX_DISPLAY_CHARS:
            return cls._truncate_output(output)

        fenced = cls._strip_json_fence(text)
        candidate = fenced if fenced is not None else text
        if not candidate.startswith(("{", "[")):
            return output
        if len(candidate) > MAX_PRETTY_PRINT_CHARS:
            return cls._truncate_output(output)

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return output
        return json.dumps(parsed, indent=2, ensure_ascii=False)

    @staticmethod
    def _truncate_output(output: str) -> str:
        if len(output) <= MAX_DISPLAY_CHARS:
            return output
        omitted = len(output) - MAX_DISPLAY_CHARS
        return (
            f"[truncated {omitted} characters; inspect the raw artifact for full output]"
            + "\n\n"
            + output[-MAX_DISPLAY_CHARS:]
        )

    def _read_provider_output_path(self, raw_output_path: str) -> str:
        path_text = raw_output_path.strip()
        if not path_text:
            return ""
        cached = self._output_cache.get(path_text)
        if cached is not None:
            return cached
        path = Path(path_text)
        output = self._read_bounded_output(path)
        self._output_cache[path_text] = output
        return output

    @staticmethod
    def _read_bounded_output(path: Path) -> str:
        try:
            size = path.stat().st_size
        except OSError:
            return ""
        if size <= MAX_DISPLAY_CHARS:
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return ""

        marker = (
            f"[truncated {size} bytes to last {MAX_DISPLAY_CHARS} display "
            "characters; inspect the raw artifact for full output]"
        )
        tail_limit = max(0, MAX_DISPLAY_CHARS - len(marker) - 2)
        try:
            with path.open("rb") as fh:
                fh.seek(max(0, size - tail_limit))
                data = fh.read(tail_limit)
        except OSError:
            return ""
        return marker + "\n\n" + data.decode("utf-8", errors="replace")

    @staticmethod
    def _strip_json_fence(text: str) -> str | None:
        lines = text.splitlines()
        if len(lines) < 3:
            return None
        first = lines[0].strip().lower()
        if first not in {"```json", "```"} or lines[-1].strip() != "```":
            return None
        return "\n".join(lines[1:-1]).strip()


def _format_score(score: float) -> str:
    text = f"{score:.3f}".rstrip("0").rstrip(".")
    if text == "-0":
        return "0"
    return text or "0"
