"""Reusable fake provider CLI binaries for deterministic Trinity tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class FakeProviderCLIs:
    """Installed fake provider binaries and their shared call log."""

    root: Path
    bin_dir: Path
    log_dir: Path
    calls_log: Path
    claude: Path
    codex: Path
    agy: Path

    @property
    def path_env(self) -> str:
        """Return PATH with the fake binaries first."""
        current = os.environ.get("PATH", "")
        return str(self.bin_dir) if not current else f"{self.bin_dir}{os.pathsep}{current}"

    def env(self, **overrides: str) -> dict[str, str]:
        """Return environment overrides for subprocess-backed Trinity tests."""
        env = {
            "PATH": self.path_env,
            "TRINITY_FAKE_PROVIDER_LOG": str(self.calls_log),
        }
        env.update({key: str(value) for key, value in overrides.items()})
        return env

    def read_calls(self) -> list[dict[str, object]]:
        """Read provider invocation records from the shared JSONL log."""
        return read_jsonl(self.calls_log)


def install_fake_provider_clis(root: Path) -> FakeProviderCLIs:
    """Create fake Claude, Codex, and Antigravity executables under ``root``."""
    root = Path(root)
    bin_dir = root / "bin"
    log_dir = root / "logs"
    bin_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    calls_log = log_dir / "provider-calls.jsonl"

    claude = _install_fake_provider(bin_dir, provider="claude")
    codex = _install_fake_provider(bin_dir, provider="codex")
    agy = _install_fake_provider(bin_dir, provider="agy")
    return FakeProviderCLIs(
        root=root,
        bin_dir=bin_dir,
        log_dir=log_dir,
        calls_log=calls_log,
        claude=claude,
        codex=codex,
        agy=agy,
    )


def _install_fake_provider(bin_dir: Path, *, provider: str) -> Path:
    if os.name == "nt":
        script = bin_dir / f"{provider}.py"
        wrapper = bin_dir / f"{provider}.cmd"
        _write_fake_provider(script, provider=provider)
        _write_windows_wrapper(wrapper, script.name)
        return wrapper

    executable = bin_dir / provider
    _write_fake_provider(executable, provider=provider)
    return executable


def read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read a JSONL file, ignoring blank lines."""
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def provider_calls(
    calls: Iterable[dict[str, object]],
    provider: str,
) -> list[dict[str, object]]:
    """Filter shared call-log records for one fake provider."""
    return [
        call
        for call in calls
        if str(call.get("provider") or "") == provider
    ]


def run_fake_cli(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    input_text: str = "",
    timeout_seconds: float = 5.0,
) -> subprocess.CompletedProcess[str]:
    """Run a fake CLI command with captured text output."""
    return subprocess.run(
        argv,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )


def _write_fake_provider(path: Path, *, provider: str) -> None:
    script = _SCRIPT_TEMPLATE.replace("__PROVIDER__", provider)
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def _write_windows_wrapper(path: Path, script_name: str) -> None:
    path.write_text(_windows_wrapper_script(script_name), encoding="utf-8")


def _windows_wrapper_script(script_name: str) -> str:
    return (
        "@echo off\r\n"
        f'"{sys.executable}" "%~dp0{script_name}" %*\r\n'
        "exit /b %ERRORLEVEL%\r\n"
    )


_SCRIPT_TEMPLATE = textwrap.dedent(
    r'''
    #!/usr/bin/env python3
    from __future__ import annotations

    import json
    import os
    import pathlib
    import sys
    import time


    PROVIDER = "__PROVIDER__"
    AGENT_NAME = {
        "claude": "claude",
        "codex": "codex",
        "agy": "antigravity",
    }[PROVIDER]


    def main() -> int:
        args = sys.argv[1:]
        stdin_text = sys.stdin.read()
        mode = provider_mode()
        record_call(args, stdin_text, mode)

        if mode == "slow":
            time.sleep(float(os.environ.get("TRINITY_FAKE_PROVIDER_SLEEP_SECONDS", "5")))

        if args == ["--version"]:
            return emit_version(mode)

        if PROVIDER == "codex" and args[:2] == ["debug", "models"]:
            return emit_codex_models(mode)

        if PROVIDER == "agy" and args == ["models"]:
            return emit_agy_models(mode)

        return emit_provider_turn(args, mode)


    def provider_mode() -> str:
        key = {
            "claude": "TRINITY_FAKE_CLAUDE_MODE",
            "codex": "TRINITY_FAKE_CODEX_MODE",
            "agy": "TRINITY_FAKE_AGY_MODE",
        }[PROVIDER]
        return (
            os.environ.get(key)
            or os.environ.get("TRINITY_FAKE_PROVIDER_MODE")
            or "success"
        ).strip().lower()


    def record_call(args: list[str], stdin_text: str, mode: str) -> None:
        log_file = os.environ.get("TRINITY_FAKE_PROVIDER_LOG", "")
        if not log_file:
            return
        path = pathlib.Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "provider": PROVIDER,
            "argv": args,
            "stdin": stdin_text,
            "cwd": os.getcwd(),
            "mode": mode,
            "env": {
                key: value
                for key, value in sorted(os.environ.items())
                if key.startswith("TRINITY_FAKE_")
            },
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


    def emit_version(mode: str) -> int:
        if mode in {"probe_exit1", "auth_required"}:
            print("Please sign in to continue.", file=sys.stderr)
            return 1
        print(f"{PROVIDER} fake-cli 0.0.0")
        return 0


    def emit_codex_models(mode: str) -> int:
        if mode == "models_exit1":
            print("model discovery failed", file=sys.stderr)
            return 1
        if mode == "models_empty":
            print(json.dumps({"models": []}))
            return 0
        override = os.environ.get("TRINITY_FAKE_CODEX_MODELS_JSON", "")
        if override:
            print(override)
            return 0
        print(
            json.dumps(
                {
                    "models": [
                        {"slug": "gpt-5", "visibility": "list"},
                        {"slug": "gpt-5.5", "visibility": "list"},
                        {"slug": "codex-hidden", "visibility": "hide"},
                    ]
                }
            )
        )
        return 0


    def emit_agy_models(mode: str) -> int:
        if mode == "models_exit1":
            print("model discovery failed", file=sys.stderr)
            return 1
        if mode == "models_empty":
            return 0
        models = os.environ.get(
            "TRINITY_FAKE_AGY_MODELS",
            "Gemini 3.5 Flash (Medium)\nGPT-OSS 120B (Medium)",
        )
        print(models)
        return 0


    def emit_provider_turn(args: list[str], mode: str) -> int:
        if mode in {"exit1", "auth_required"}:
            print("Please sign in to continue." if mode == "auth_required" else "Synthetic provider failure.", file=sys.stderr)
            return 1
        if mode == "empty":
            return 0
        if PROVIDER == "claude":
            return emit_claude_turn()
        if PROVIDER == "codex":
            return emit_codex_turn()
        if PROVIDER == "agy":
            return emit_agy_turn(args)
        print(f"Unknown fake provider: {PROVIDER}", file=sys.stderr)
        return 2


    def agent_payload() -> dict[str, object]:
        return {
            "vote": "APPROVE",
            "rationale": f"Fake {PROVIDER} response for Trinity smoke tests.",
            "blueprint": {
                "title": f"Fake {PROVIDER} Blueprint",
                "summary": "Deterministic provider output for local Trinity tests.",
                "architecture": [],
                "data_flow": ["prompt -> fake provider -> normalized result"],
                "external_dependencies": [],
                "risks": [],
                "acceptance_criteria": ["Fake provider response is parsed."],
                "open_questions": [],
                "work_packages": [
                    {
                        "id": "WP-001",
                        "title": "Verify fake provider harness",
                        "owner_agent": AGENT_NAME,
                        "objective": "Exercise Trinity provider plumbing without real accounts.",
                        "scope": ["preflight", "model discovery", "one-shot invocation"],
                        "out_of_scope": [],
                        "dependencies": [],
                        "expected_files": ["tests/harness/"],
                        "acceptance_criteria": ["The harness emits deterministic output."],
                        "estimated_weight": 1,
                        "parallel_group": 1,
                        "parallelizable": True,
                        "risk": "low",
                    }
                ],
            },
        }


    def emit_claude_turn() -> int:
        model = os.environ.get("TRINITY_FAKE_CLAUDE_MODEL", "claude-fake-model")
        payload = {
            "result": json.dumps(agent_payload(), ensure_ascii=False),
            "session_id": os.environ.get("TRINITY_FAKE_CLAUDE_SESSION", "fake-claude-session"),
            "model": model,
            "usage": {"input_tokens": 13, "output_tokens": 21},
            "modelUsage": {
                model: {
                    "contextWindow": 200000,
                    "maxOutputTokens": 8192,
                }
            },
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0


    def emit_codex_turn() -> int:
        model = os.environ.get("TRINITY_FAKE_CODEX_MODEL", "gpt-5")
        events = [
            {
                "type": "thread.started",
                "thread_id": os.environ.get("TRINITY_FAKE_CODEX_THREAD", "fake-codex-thread"),
                "model": model,
            },
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": json.dumps(agent_payload(), ensure_ascii=False),
                },
            },
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 17,
                    "output_tokens": 29,
                    "reasoning_output_tokens": 3,
                },
            },
        ]
        for event in events:
            print(json.dumps(event, ensure_ascii=False))
        return 0


    def emit_agy_turn(args: list[str]) -> int:
        log_file = extract_flag_value(args, "--log-file")
        if log_file:
            path = pathlib.Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "conversation=fake-agy-conversation\n"
                "selected model: Gemini 3.5 Flash (Medium)\n"
                "backend: fake-agy-backend\n",
                encoding="utf-8",
            )
        print(json.dumps(agent_payload(), ensure_ascii=False))
        return 0


    def extract_flag_value(args: list[str], flag: str) -> str:
        for index, item in enumerate(args):
            if item == flag and index + 1 < len(args):
                return args[index + 1]
            prefix = f"{flag}="
            if item.startswith(prefix):
                return item[len(prefix):]
        return ""


    if __name__ == "__main__":
        raise SystemExit(main())
    '''
).lstrip()
