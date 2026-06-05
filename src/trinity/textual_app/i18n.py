"""Localized Textual workbench strings."""

from __future__ import annotations

from trinity.i18n import DEFAULT_LANG, validate_lang


COMMAND_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "en": {
        "/status": "show provider and workflow status",
        "/context": "show shared context summary",
        "/rounds": "show deliberation rounds",
        "/agent": "inspect or focus an agent",
        "/history": "show recent session history",
        "/save": "save current workflow state",
        "/caveman": "toggle concise reasoning mode",
        "/workflow": "show workflow ledger",
        "/questions": "show pending questions",
        "/answer": "answer a pending question",
        "/decisions": "show agreed decisions",
        "/packages": "show work packages",
        "/subtasks": "show decomposed subtasks",
        "/resume": "resume a saved workflow",
        "/execute": "open execution preflight",
        "/target": "set target workspace candidate",
        "/help": "show available commands",
        "/quit": "exit Trinity",
    },
    "ko": {
        "/status": "제공자와 워크플로우 상태 보기",
        "/context": "공유 컨텍스트 요약 보기",
        "/rounds": "협의 라운드 보기",
        "/agent": "에이전트 검사 또는 포커스",
        "/history": "최근 세션 기록 보기",
        "/save": "현재 워크플로우 상태 저장",
        "/caveman": "간결 추론 모드 전환",
        "/workflow": "워크플로우 원장 보기",
        "/questions": "대기 중인 질문 보기",
        "/answer": "대기 중인 질문에 답변",
        "/decisions": "합의된 결정 보기",
        "/packages": "작업 패키지 보기",
        "/subtasks": "분해된 하위 작업 보기",
        "/resume": "저장된 워크플로우 재개",
        "/execute": "실행 사전 점검 열기",
        "/target": "대상 워크스페이스 후보 설정",
        "/help": "사용 가능한 명령 보기",
        "/quit": "Trinity 종료",
    },
}

UI_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "command_no_matches": "No matching commands",
        "command_more": "more commands",
    },
    "ko": {
        "command_no_matches": "일치하는 명령이 없습니다",
        "command_more": "명령 더 있음",
    },
}


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
    safe_lang = textual_lang(lang)
    strings = UI_TEXT.get(safe_lang, UI_TEXT[DEFAULT_LANG])
    fallback = UI_TEXT[DEFAULT_LANG]
    return strings.get(key, fallback.get(key, ""))
