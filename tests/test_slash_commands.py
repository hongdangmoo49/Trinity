from __future__ import annotations

from trinity.slash_commands import parse_execute_retry_args, parse_slash_command


def test_parse_execute_retry_args_defaults_to_all() -> None:
    assert parse_execute_retry_args([]) == ("all", [])


def test_parse_execute_retry_args_uses_known_selector() -> None:
    assert parse_execute_retry_args(["failed", "WP-001"]) == ("failed", ["WP-001"])


def test_parse_execute_retry_args_treats_package_ids_as_custom() -> None:
    assert parse_execute_retry_args(["WP-001", "WP-002"]) == (
        "custom",
        ["WP-001", "WP-002"],
    )


def test_parse_slash_command_keeps_execute_retry_args() -> None:
    parsed = parse_slash_command("/execute-retry blocked WP-003")

    assert parsed is not None
    assert parsed.command_id == "execute-retry"
    assert parsed.args == ("blocked", "WP-003")


def test_parse_slash_command_registers_project_command() -> None:
    parsed = parse_slash_command("/project")

    assert parsed is not None
    assert parsed.command_id == "project"
    assert parsed.spec is not None
    assert parsed.spec.usage == "/project"
    assert parsed.spec.summary_ko == "간결한 프로젝트 진단 보기"


def test_parse_slash_command_registers_providers_command() -> None:
    parsed = parse_slash_command("/providers")

    assert parsed is not None
    assert parsed.command_id == "providers"
    assert parsed.spec is not None
    assert parsed.spec.summary == "open provider inspector"


def test_parse_slash_command_registers_workspace_command() -> None:
    parsed = parse_slash_command("/workspace")

    assert parsed is not None
    assert parsed.command_id == "workspace"
    assert parsed.spec is not None
    assert parsed.spec.summary == "browse for a target workspace"


def test_parse_slash_command_registers_target_command() -> None:
    parsed = parse_slash_command("/target")

    assert parsed is not None
    assert parsed.command_id == "target"
    assert parsed.spec is not None
    assert parsed.spec.summary == "show, set, or clear target path"
    assert parsed.spec.summary_ko == "대상 경로 보기, 설정 또는 초기화"
