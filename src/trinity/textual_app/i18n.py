"""Localized Textual workbench strings."""

from __future__ import annotations

from dataclasses import replace

from trinity.i18n import DEFAULT_LANG, validate_lang
from trinity.slash_commands import SLASH_COMMAND_DESCRIPTIONS


COMMAND_DESCRIPTIONS: dict[str, dict[str, str]] = SLASH_COMMAND_DESCRIPTIONS

UI_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "command_no_matches": "No matching commands",
        "command_more": "more commands",
        "binding_apply": "Apply",
        "binding_save_apply": "Save & Apply",
        "binding_back": "Back",
        "binding_cancel": "Cancel",
        "binding_close": "Close",
        "binding_create": "Create",
        "binding_execute": "Execute",
        "binding_export_markdown": "Export Markdown",
        "binding_expand_tasks": "Expand Tasks",
        "binding_full_log": "Full Log",
        "binding_inspector": "Inspector",
        "binding_new_line": "New line",
        "binding_new_session": "New Session",
        "binding_next_command": "Next command",
        "binding_nexus": "Nexus",
        "binding_palette": "palette",
        "binding_palette_tooltip": "Open the command palette",
        "binding_previous_command": "Previous command",
        "binding_quit": "Quit",
        "binding_report": "Report",
        "binding_retry": "Retry",
        "binding_send": "Send",
        "binding_settings": "Settings",
        "binding_start": "Start",
        "nexus_composer_placeholder": "Reply, refine direction, or type / for commands",
        "nexus_select_workspace": "Select Workspace",
        "nexus_select_agent_warning": "Select at least one agent.",
        "recipient_all": "All",
        "recipient_label": "Ask",
        "recipient_provider_default": "default",
        "start_placeholder": "What should Trinity work on?",
        "start_select_agent_warning": "Select at least one agent.",
        "start_select_workspace": "Select Workspace",
    },
    "ko": {
        "command_no_matches": "일치하는 명령이 없습니다",
        "command_more": "명령 더 있음",
        "binding_apply": "적용",
        "binding_save_apply": "저장 및 적용",
        "binding_back": "뒤로",
        "binding_cancel": "취소",
        "binding_close": "닫기",
        "binding_create": "생성",
        "binding_execute": "실행",
        "binding_export_markdown": "마크다운 내보내기",
        "binding_expand_tasks": "작업 펼치기",
        "binding_full_log": "전체 로그",
        "binding_inspector": "인스펙터",
        "binding_new_line": "새 줄",
        "binding_new_session": "새 세션",
        "binding_next_command": "다음 명령",
        "binding_nexus": "넥서스",
        "binding_palette": "팔레트",
        "binding_palette_tooltip": "명령 팔레트 열기",
        "binding_previous_command": "이전 명령",
        "binding_quit": "종료",
        "binding_report": "리포트",
        "binding_retry": "재시도",
        "binding_send": "보내기",
        "binding_settings": "설정",
        "binding_start": "시작",
        "nexus_composer_placeholder": "답변, 방향 조정 또는 /로 명령 입력",
        "nexus_select_workspace": "작업 폴더 선택",
        "nexus_select_agent_warning": "에이전트를 하나 이상 선택하세요.",
        "recipient_all": "전체",
        "recipient_label": "대상",
        "recipient_provider_default": "기본값",
        "start_placeholder": "Trinity가 무엇을 진행하면 될까요?",
        "start_select_agent_warning": "에이전트를 하나 이상 선택하세요.",
        "start_select_workspace": "작업 폴더 선택",
    },
}

BindingReplacements = dict[tuple[str, str], tuple[str, str | None]]


def textual_lang(lang: str | None) -> str:
    """Return a supported Textual UI language code."""
    return validate_lang(lang or DEFAULT_LANG, fallback=DEFAULT_LANG)


def command_description(command: str, lang: str | None = None) -> str:
    """Return a localized slash-command description.

    Command names such as ``/status`` intentionally remain untranslated.
    """
    safe_lang = textual_lang(lang)
    descriptions = COMMAND_DESCRIPTIONS.get(
        safe_lang, COMMAND_DESCRIPTIONS[DEFAULT_LANG]
    )
    fallback = COMMAND_DESCRIPTIONS[DEFAULT_LANG]
    return descriptions.get(command, fallback.get(command, ""))


def command_palette_text(key: str, lang: str | None = None) -> str:
    """Return localized command palette chrome text."""
    return ui_text(key, lang)


def ui_text(key: str, lang: str | None = None) -> str:
    """Return localized Textual UI text."""
    safe_lang = textual_lang(lang)
    strings = UI_TEXT.get(safe_lang, UI_TEXT[DEFAULT_LANG])
    fallback = UI_TEXT[DEFAULT_LANG]
    return strings.get(key, fallback.get(key, ""))


def localize_bindings(
    bindings_map: object,
    lang: str | None,
    replacements: BindingReplacements,
) -> None:
    """Update Textual binding descriptions in-place for the configured language."""
    if textual_lang(lang) == DEFAULT_LANG:
        return

    key_to_bindings = getattr(bindings_map, "key_to_bindings", {})
    for (key, action), (description_key, tooltip_key) in replacements.items():
        bindings = key_to_bindings.get(key, [])
        for index, binding in enumerate(bindings):
            if binding.action != action:
                continue
            description = command_palette_text(description_key, lang)
            tooltip = (
                command_palette_text(tooltip_key, lang)
                if tooltip_key is not None
                else binding.tooltip
            )
            bindings[index] = replace(
                binding,
                description=description,
                tooltip=tooltip,
            )
