"""Tests for cross-platform log following."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from trinity.cli import main
from trinity.config import TrinityConfig
from trinity.platform.log_tail import LogTailEvent, follow_log


def test_follow_log_emits_initial_tail_with_utf8_replacement(tmp_path):
    log_path = tmp_path / "trinity.log"
    log_path.write_bytes(b"one\nbad \xff\nthree\n")
    events = follow_log(log_path, lines=2, poll_interval=0)

    try:
        assert next(events) == LogTailEvent("line", "bad \ufffd")
        assert next(events) == LogTailEvent("line", "three")
    finally:
        events.close()


def test_follow_log_polls_appended_lines(tmp_path):
    log_path = tmp_path / "trinity.log"
    log_path.write_text("old\n", encoding="utf-8")
    events = follow_log(log_path, lines=1, poll_interval=0)

    try:
        assert next(events) == LogTailEvent("line", "old")
        with log_path.open("ab") as stream:
            stream.write("new cafe\n".encode("utf-8"))
            stream.write(b"bad \xff\n")

        assert next(events) == LogTailEvent("line", "new cafe")
        assert next(events) == LogTailEvent("line", "bad \ufffd")
    finally:
        events.close()


def test_follow_log_reports_rotation_and_reads_new_file(tmp_path):
    log_path = tmp_path / "trinity.log"
    rotated_path = tmp_path / "trinity.log.1"
    log_path.write_text("old\n", encoding="utf-8")
    events = follow_log(log_path, lines=1, poll_interval=0)

    try:
        assert next(events) == LogTailEvent("line", "old")
        log_path.rename(rotated_path)
        log_path.write_text("new\n", encoding="utf-8")

        event = next(events)
        assert event.kind == "rotated"
        assert "rotated" in event.message
        assert next(events) == LogTailEvent("line", "new")
    finally:
        events.close()


def test_follow_log_reports_delete_and_recreate(tmp_path):
    log_path = tmp_path / "trinity.log"
    log_path.write_text("old\n", encoding="utf-8")
    events = follow_log(log_path, lines=1, poll_interval=0)

    try:
        assert next(events) == LogTailEvent("line", "old")
        log_path.unlink()

        deleted = next(events)
        assert deleted.kind == "deleted"
        assert "deleted" in deleted.message

        log_path.write_text("new\n", encoding="utf-8")
        created = next(events)
        assert created.kind == "created"
        assert "recreated" in created.message
        assert next(events) == LogTailEvent("line", "new")
    finally:
        events.close()


def test_follow_log_reports_truncate_and_reads_from_start(tmp_path):
    log_path = tmp_path / "trinity.log"
    log_path.write_text("old line\n", encoding="utf-8")
    events = follow_log(log_path, lines=1, poll_interval=0)

    try:
        assert next(events) == LogTailEvent("line", "old line")
        log_path.write_text("new\n", encoding="utf-8")

        event = next(events)
        assert event.kind == "rotated"
        assert "truncated" in event.message
        assert next(events) == LogTailEvent("line", "new")
    finally:
        events.close()


def test_cli_logs_follow_exits_cleanly_on_keyboard_interrupt(tmp_path):
    state_dir = tmp_path / ".trinity"
    logs_dir = state_dir / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "trinity.log").write_text("old\n", encoding="utf-8")
    config = TrinityConfig(project_dir=tmp_path, state_dir=state_dir)

    with (
        patch("trinity.cli.load_config", return_value=config),
        patch("trinity.platform.log_tail.follow_log", side_effect=KeyboardInterrupt),
    ):
        result = CliRunner().invoke(main, ["logs", "--follow"])

    assert result.exit_code == 0
    assert "Stopped" in result.output


def test_cli_logs_follow_waits_when_log_missing(tmp_path):
    state_dir = tmp_path / ".trinity"
    config = TrinityConfig(project_dir=tmp_path, state_dir=state_dir)

    with (
        patch("trinity.cli.load_config", return_value=config),
        patch("trinity.platform.log_tail.follow_log", side_effect=KeyboardInterrupt) as follow,
    ):
        result = CliRunner().invoke(main, ["logs", "--follow"])

    assert result.exit_code == 0
    assert "No log file found" not in result.output
    assert follow.call_args.kwargs["lines"] == 50
