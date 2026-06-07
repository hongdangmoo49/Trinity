from __future__ import annotations

from pathlib import Path

from trinity.slash_commands import (
    COMMAND_SPECS,
    AgentCallPolicy,
    SlashCommandCategory,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DOC = ROOT / "docs" / "slash-command-reference.md"
DESIGN_DOC = (
    ROOT / "docs" / "plans" / "2026-06-06-trinity-slash-command-routing-design.md"
)


def _split_markdown_row(row: str) -> list[str]:
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in row.strip().strip("|"):
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    cells.append("".join(current).strip())
    return cells


def _table_after_heading(path: Path, heading: str) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = lines.index(heading)
    header_index = next(
        index
        for index in range(start + 1, len(lines))
        if lines[index].startswith("| ")
    )
    headers = _split_markdown_row(lines[header_index])
    rows: list[dict[str, str]] = []
    for line in lines[header_index + 2 :]:
        if not line.startswith("| "):
            break
        cells = _split_markdown_row(line)
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def _code_span(value: str) -> str:
    return value.strip().strip("`")


def test_reference_command_summary_matches_registry() -> None:
    rows = _table_after_heading(REFERENCE_DOC, "## 명령어 요약")
    documented = {_code_span(row["명령"]) for row in rows}
    canonical = {spec.name for spec in COMMAND_SPECS}

    assert documented == canonical


def test_reference_command_summary_mentions_registered_aliases() -> None:
    rows = _table_after_heading(REFERENCE_DOC, "## 명령어 요약")
    by_command = {_code_span(row["명령"]): row for row in rows}

    for spec in COMMAND_SPECS:
        usage = by_command[spec.name]["사용법"]
        for alias in spec.aliases:
            assert alias in usage


def test_design_command_table_matches_registry_names() -> None:
    rows = _table_after_heading(DESIGN_DOC, "## 명령별 동작 정의")
    documented = {_code_span(row["명령"]) for row in rows}
    registered = {
        name
        for spec in COMMAND_SPECS
        for name in spec.names
    }

    assert documented == registered


def test_design_command_table_matches_registry_policy() -> None:
    rows = _table_after_heading(DESIGN_DOC, "## 명령별 동작 정의")
    by_command = {_code_span(row["명령"]): row for row in rows}
    category_labels = {
        SlashCommandCategory.LOCAL_UI: "로컬/UI 조회",
        SlashCommandCategory.LOCAL_FILE: "로컬 파일 기록",
        SlashCommandCategory.SESSION_SETTING: "세션 설정 변경",
        SlashCommandCategory.WORKFLOW_LOCAL: "workflow 로컬 변경",
        SlashCommandCategory.CONDITIONAL_WORKFLOW: "조건부 workflow 변경",
        SlashCommandCategory.EXECUTION: "명시 실행",
        SlashCommandCategory.APP_EXIT: "앱 종료",
    }
    agent_call_labels = {
        AgentCallPolicy.NONE: "없음",
        AgentCallPolicy.CONDITIONAL: "조건부",
        AgentCallPolicy.EXECUTION: "execution",
    }

    for spec in COMMAND_SPECS:
        for name in spec.names:
            row = by_command[name]
            assert row["분류"].startswith(category_labels[spec.category])
            assert row["에이전트 호출"] == agent_call_labels[spec.agent_call]
