"""Shared Trinity slash command registry and parser."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import Enum


class SlashCommandCategory(str, Enum):
    """High-level side-effect category for a Trinity slash command."""

    LOCAL_UI = "local_ui"
    LOCAL_FILE = "local_file"
    SESSION_SETTING = "session_setting"
    WORKFLOW_LOCAL = "workflow_local"
    CONDITIONAL_WORKFLOW = "conditional_workflow"
    EXECUTION = "execution"
    APP_EXIT = "app_exit"


class AgentCallPolicy(str, Enum):
    """Whether a Trinity slash command is allowed to call providers."""

    NONE = "none"
    CONDITIONAL = "conditional"
    EXECUTION = "execution"


SESSION_ONLY_SETTING_NOTICE = (
    "Session-only setting. Config file was not changed."
)


@dataclass(frozen=True)
class SlashCommandSpec:
    """A Trinity-owned slash command definition."""

    name: str
    usage: str
    summary: str
    summary_ko: str
    category: SlashCommandCategory
    agent_call: AgentCallPolicy = AgentCallPolicy.NONE
    aliases: tuple[str, ...] = ()
    mutates_workflow: bool = False
    writes_files: bool = False

    @property
    def names(self) -> tuple[str, ...]:
        """Return the canonical command and aliases, all with leading slash."""
        return (self.name, *self.aliases)

    @property
    def command_id(self) -> str:
        """Return the command id without the leading slash."""
        return self.name.removeprefix("/")


@dataclass(frozen=True)
class ParsedSlashCommand:
    """Result of parsing user slash command text."""

    raw: str
    token: str
    args: tuple[str, ...]
    spec: SlashCommandSpec | None = None
    error: str = ""

    @property
    def is_known(self) -> bool:
        """Return whether the parsed command matched a Trinity command."""
        return self.spec is not None and not self.error

    @property
    def command_id(self) -> str:
        """Return the canonical command id when known, else the raw token id."""
        if self.spec is not None:
            return self.spec.command_id
        return self.token.removeprefix("/")


COMMAND_SPECS: tuple[SlashCommandSpec, ...] = (
    SlashCommandSpec(
        name="/status",
        usage="/status",
        summary="show provider and workflow status",
        summary_ko="제공자와 워크플로우 상태 보기",
        category=SlashCommandCategory.LOCAL_UI,
    ),
    SlashCommandSpec(
        name="/context",
        usage="/context",
        summary="show shared context summary",
        summary_ko="공유 컨텍스트 요약 보기",
        category=SlashCommandCategory.LOCAL_UI,
    ),
    SlashCommandSpec(
        name="/rounds",
        usage="/rounds [N]",
        summary="show or set deliberation rounds",
        summary_ko="협의 라운드 보기 또는 변경",
        category=SlashCommandCategory.SESSION_SETTING,
    ),
    SlashCommandSpec(
        name="/agent",
        usage="/agent <name> on|off",
        summary="enable or disable an agent",
        summary_ko="에이전트 활성화 또는 비활성화",
        category=SlashCommandCategory.SESSION_SETTING,
    ),
    SlashCommandSpec(
        name="/history",
        usage="/history",
        summary="show recent session history",
        summary_ko="최근 세션 기록 보기",
        category=SlashCommandCategory.LOCAL_UI,
    ),
    SlashCommandSpec(
        name="/save",
        usage="/save",
        summary="save current plain TUI result history",
        summary_ko="현재 plain TUI 결과 기록 저장",
        category=SlashCommandCategory.LOCAL_FILE,
        writes_files=True,
    ),
    SlashCommandSpec(
        name="/caveman",
        usage="/caveman [on|off|lite|full|ultra]",
        summary="toggle concise reasoning mode",
        summary_ko="간결 추론 모드 전환",
        category=SlashCommandCategory.SESSION_SETTING,
    ),
    SlashCommandSpec(
        name="/workflow",
        usage="/workflow",
        summary="show workflow ledger",
        summary_ko="워크플로우 원장 보기",
        category=SlashCommandCategory.LOCAL_UI,
    ),
    SlashCommandSpec(
        name="/questions",
        usage="/questions [--select] [--all]",
        summary="show pending questions",
        summary_ko="대기 중인 질문 보기",
        category=SlashCommandCategory.LOCAL_UI,
    ),
    SlashCommandSpec(
        name="/answer",
        usage="/answer <id|index|next> <answer>",
        summary="answer a pending question",
        summary_ko="대기 중인 질문에 답변",
        category=SlashCommandCategory.CONDITIONAL_WORKFLOW,
        agent_call=AgentCallPolicy.CONDITIONAL,
        mutates_workflow=True,
    ),
    SlashCommandSpec(
        name="/decisions",
        usage="/decisions",
        summary="show agreed decisions",
        summary_ko="합의된 결정 보기",
        category=SlashCommandCategory.LOCAL_UI,
    ),
    SlashCommandSpec(
        name="/packages",
        usage="/packages",
        summary="show work packages",
        summary_ko="작업 패키지 보기",
        category=SlashCommandCategory.LOCAL_UI,
    ),
    SlashCommandSpec(
        name="/subtasks",
        usage="/subtasks",
        summary="show decomposed subtasks",
        summary_ko="분해된 하위 작업 보기",
        category=SlashCommandCategory.LOCAL_UI,
    ),
    SlashCommandSpec(
        name="/report",
        usage="/report [save|s]",
        summary="show or save the deliberation report",
        summary_ko="협의 보고서 보기 또는 저장",
        category=SlashCommandCategory.LOCAL_UI,
        writes_files=True,
    ),
    SlashCommandSpec(
        name="/resume",
        usage="/resume [index|latest|workflow-id]",
        summary="resume a saved workflow",
        summary_ko="저장된 워크플로우 재개",
        category=SlashCommandCategory.WORKFLOW_LOCAL,
        mutates_workflow=True,
    ),
    SlashCommandSpec(
        name="/execute",
        usage="/execute [instruction]",
        summary="open execution preflight",
        summary_ko="실행 사전 점검 열기",
        category=SlashCommandCategory.EXECUTION,
        agent_call=AgentCallPolicy.EXECUTION,
        mutates_workflow=True,
        writes_files=True,
    ),
    SlashCommandSpec(
        name="/target",
        usage="/target [path|clear]",
        summary="set target workspace candidate",
        summary_ko="대상 워크스페이스 후보 설정",
        category=SlashCommandCategory.WORKFLOW_LOCAL,
        mutates_workflow=True,
    ),
    SlashCommandSpec(
        name="/help",
        usage="/help",
        summary="show available commands",
        summary_ko="사용 가능한 명령 보기",
        category=SlashCommandCategory.LOCAL_UI,
    ),
    SlashCommandSpec(
        name="/quit",
        usage="/quit",
        summary="exit Trinity",
        summary_ko="Trinity 종료",
        category=SlashCommandCategory.APP_EXIT,
        aliases=("/exit", "/q"),
    ),
)


COMMAND_BY_NAME: dict[str, SlashCommandSpec] = {
    name: spec
    for spec in COMMAND_SPECS
    for name in spec.names
}

TRINITY_COMMANDS: list[str] = [
    name
    for spec in COMMAND_SPECS
    for name in spec.names
]

SLASH_COMMAND_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "en": {
        name: spec.summary
        for spec in COMMAND_SPECS
        for name in spec.names
    },
    "ko": {
        name: spec.summary_ko
        for spec in COMMAND_SPECS
        for name in spec.names
    },
}


def is_slash_command_text(text: str) -> bool:
    """Return whether text should be handled as a Trinity slash command."""
    return text.strip().startswith("/")


def parse_slash_command(text: str) -> ParsedSlashCommand | None:
    """Parse slash command text using the plain TUI-compatible syntax."""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    try:
        parts = shlex.split(stripped[1:])
    except ValueError as exc:
        return ParsedSlashCommand(
            raw=text,
            token="",
            args=(),
            error=f"Invalid command syntax: {exc}",
        )
    if not parts:
        return ParsedSlashCommand(raw=text, token="", args=())

    token = "/" + parts[0].lower()
    spec = COMMAND_BY_NAME.get(token)
    return ParsedSlashCommand(
        raw=text,
        token=token,
        args=tuple(parts[1:]),
        spec=spec,
    )
