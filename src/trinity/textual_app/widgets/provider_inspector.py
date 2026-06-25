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
from trinity.textual_app.widgets.status_label import (
    display_readiness_value,
    display_status_value,
)

MAX_PRETTY_PRINT_CHARS = 200_000
MAX_DISPLAY_CHARS = 50_000

PROVIDER_INSPECTOR_LABELS = {
    "en": {
        "all": "All",
        "blockers": "blockers",
        "close": "Close",
        "context_profile": "Context profile",
        "mission": "Mission",
        "modes": "Modes",
        "no_raw_output": "No raw output captured yet.",
        "output_contract": "Output contract",
        "provider": "Provider",
        "quality_signals": "Quality signals",
        "readiness": "Readiness",
        "required_changes": "required changes",
        "score": "score",
        "status": "Status",
        "strengths": "Strengths",
        "success": "success",
        "title": "Provider Inspector",
    },
    "ko": {
        "all": "전체",
        "blockers": "차단",
        "close": "닫기",
        "context_profile": "컨텍스트 프로필",
        "mission": "미션",
        "modes": "모드",
        "no_raw_output": "아직 캡처된 원본 출력이 없습니다.",
        "output_contract": "출력 형식",
        "provider": "프로바이더",
        "quality_signals": "품질 신호",
        "readiness": "준비 상태",
        "required_changes": "변경 요청",
        "score": "점수",
        "status": "상태",
        "strengths": "강점",
        "success": "성공",
        "title": "프로바이더 인스펙터",
    },
}


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
            yield Static(self._label("title"), id="provider-inspector-title")
            with TabbedContent(id="provider-inspector-tabs"):
                for provider in self.providers:
                    with TabPane(provider.name.title(), id=f"inspect-{provider.name}"):
                        yield from self._provider_output_widgets(provider)
                with TabPane(self._label("all"), id="inspect-all"):
                    yield self._output_area(self._all_output())
            yield Button(
                self._label("close"),
                id="close-provider-inspector",
                variant="primary",
            )
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
            or self._label("no_raw_output")
        )
        return self._format_output(output)

    def _provider_meta(self, provider: ProviderSnapshot) -> str:
        lines = [
            provider.name.title(),
            f"{self._label('provider')}: {provider.provider}",
            f"{self._label('status')}: {self._status_value(provider.status)}",
            f"{self._label('readiness')}: {self._readiness_value(provider.readiness)}",
        ]
        if provider.profile_mission:
            lines.append(f"{self._label('mission')}: {provider.profile_mission}")
        if provider.profile_modes:
            lines.append(f"{self._label('modes')}: {', '.join(provider.profile_modes)}")
        if provider.profile_strengths:
            lines.append(
                f"{self._label('strengths')}: {', '.join(provider.profile_strengths)}"
            )
        if provider.context_profile:
            lines.append(
                f"{self._label('context_profile')}: {provider.context_profile}"
            )
        if provider.output_contract:
            lines.append(f"{self._label('output_contract')}: {provider.output_contract}")
        if provider.quality_signal_count:
            lines.append(self._quality_signals_line(provider))
        return "\n".join(lines)

    def _all_output(self) -> str:
        sections: list[str] = []
        for provider in self.providers:
            sections.extend(
                [
                    f"## {provider.name.title()}",
                    f"{self._label('provider')}: {provider.provider}",
                    f"{self._label('status')}: {self._status_value(provider.status)}",
                    f"{self._label('readiness')}: "
                    f"{self._readiness_value(provider.readiness)}",
                    f"{self._label('mission')}: {provider.profile_mission or '-'}",
                    (
                        f"{self._label('context_profile')}: "
                        f"{provider.context_profile or '-'}"
                    ),
                    (
                        f"{self._label('output_contract')}: "
                        f"{provider.output_contract or '-'}"
                    ),
                    self._quality_signals_line(provider)
                    if provider.quality_signal_count
                    else f"{self._label('quality_signals')}: -",
                    "",
                    self._provider_output(provider),
                ]
            )
        return "\n\n---\n\n".join(sections)

    def _quality_signals_line(self, provider: ProviderSnapshot) -> str:
        return (
            f"{self._label('quality_signals')}: "
            f"{self._label('score')} {_format_score(provider.quality_score)}, "
            f"{self._label('success')} {provider.quality_success_count}/"
            f"{provider.quality_signal_count}, "
            f"{self._label('blockers')} {provider.quality_blocker_count}, "
            f"{self._label('required_changes')} "
            f"{provider.quality_required_change_count}"
        )

    def _status_value(self, status: str) -> str:
        return display_status_value(status, lang=self.lang)

    def _readiness_value(self, readiness: str) -> str:
        return display_readiness_value(readiness, lang=self.lang)

    def _label(self, key: str) -> str:
        labels = PROVIDER_INSPECTOR_LABELS.get(
            self.lang, PROVIDER_INSPECTOR_LABELS["en"]
        )
        return labels.get(key, PROVIDER_INSPECTOR_LABELS["en"][key])

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
