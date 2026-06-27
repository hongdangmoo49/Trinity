"""Tests for the required smoke runner script."""

from __future__ import annotations

import subprocess

import pytest

from scripts import run_required_smoke_tests as runner


def test_required_smoke_runner_lists_manifest_entries(tmp_path, monkeypatch, capsys):
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_example(): pass\n", encoding="utf-8")
    manifest = tmp_path / ".github" / "required-smoke-tests.txt"
    manifest.parent.mkdir()
    manifest.write_text(
        "\n".join(
            [
                "# comment",
                "tests/test_example.py",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "TEST_LIST", manifest)

    assert runner.main(["--list"]) == 0

    assert capsys.readouterr().out == "tests/test_example.py\n"


def test_required_smoke_runner_rejects_duplicate_manifest_entries(
    tmp_path,
    monkeypatch,
):
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_example(): pass\n", encoding="utf-8")
    manifest = tmp_path / ".github" / "required-smoke-tests.txt"
    manifest.parent.mkdir()
    manifest.write_text(
        "\n".join(
            [
                "tests/test_example.py",
                "tests/test_example.py",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "TEST_LIST", manifest)

    with pytest.raises(SystemExit, match="duplicate test path"):
        runner.load_tests()


def test_required_smoke_runner_passes_pytest_args_after_options(
    tmp_path,
    monkeypatch,
):
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_example(): pass\n", encoding="utf-8")
    manifest = tmp_path / ".github" / "required-smoke-tests.txt"
    manifest.parent.mkdir()
    manifest.write_text("tests/test_example.py\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, *, cwd):
        calls.append(command)
        assert cwd == tmp_path
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "TEST_LIST", manifest)
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner.main(["-q", "-x"]) == 0

    assert calls == [
        [
            runner.sys.executable,
            "-m",
            "pytest",
            "-q",
            "-x",
            "tests/test_example.py",
        ]
    ]
