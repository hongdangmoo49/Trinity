"""E2E coverage for targeted question-answer continuation."""

from __future__ import annotations

import json
from pathlib import Path

from trinity.config import TrinityConfig
from trinity.models import AgentSpec, Provider
from trinity.textual_app.workflow_controller import TextualWorkflowController
from trinity.workflow import OpenQuestion, WorkflowEngine
from trinity.workflow.models import ProviderSessionRef


def _write_fake_codex(path: Path, log_path: Path) -> None:
    """Write a fake Codex CLI that records argv/stdin and emits JSONL."""
    script = f"""#!/usr/bin/env python3
import json
import pathlib
import sys

log_path = pathlib.Path({str(log_path)!r})
stdin_text = sys.stdin.read()
log_path.parent.mkdir(parents=True, exist_ok=True)
with log_path.open("a", encoding="utf-8") as handle:
    record = {{"argv": sys.argv[1:], "stdin": stdin_text}}
    handle.write(json.dumps(record, ensure_ascii=False) + "\\n")

agent_payload = {{
    "vote": "APPROVE",
    "rationale": "Targeted Codex continuation used the saved answer.",
    "blueprint": {{
        "title": "Targeted Continuation Blueprint",
        "summary": "Continue with the selected Codex model only.",
        "architecture": [],
        "data_flow": ["answer -> codex -> blueprint"],
        "external_dependencies": [],
        "risks": [],
        "acceptance_criteria": ["Codex receives the answered prompt."],
        "open_questions": [],
        "work_packages": [
            {{
                "id": "WP-001",
                "title": "Verify continuation",
                "owner_agent": "codex",
                "objective": "Verify target continuity.",
                "scope": ["Use the answered decision."],
                "out_of_scope": [],
                "dependencies": [],
                "expected_files": ["docs/"],
                "acceptance_criteria": ["Only Codex is invoked."],
                "estimated_weight": 1,
                "parallel_group": 1,
                "parallelizable": True,
                "risk": "low"
            }}
        ]
    }}
}}

thread_event = {{
    "type": "thread.started",
    "thread_id": "thread-after-answer",
    "model": "gpt-5",
}}
message_event = {{
    "type": "item.completed",
    "item": {{
        "type": "agent_message",
        "text": json.dumps(agent_payload, ensure_ascii=False),
    }},
}}
completed_event = {{
    "type": "turn.completed",
    "usage": {{
        "input_tokens": 10,
        "output_tokens": 20,
        "reasoning_output_tokens": 0,
    }},
}}
print(json.dumps(thread_event))
print(json.dumps(message_event, ensure_ascii=False))
print(json.dumps(completed_event))
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def _write_fake_claude(path: Path, log_path: Path) -> None:
    """Write a fake Claude CLI that records unexpected invocations."""
    script = f"""#!/usr/bin/env python3
import json
import pathlib
import sys

log_path = pathlib.Path({str(log_path)!r})
stdin_text = sys.stdin.read()
log_path.parent.mkdir(parents=True, exist_ok=True)
with log_path.open("a", encoding="utf-8") as handle:
    record = {{"argv": sys.argv[1:], "stdin": stdin_text}}
    handle.write(json.dumps(record, ensure_ascii=False) + "\\n")

payload = {{
    "result": (
        "VOTE: APPROVE\\n"
        "Title: Unexpected Claude Call\\n"
        "Summary: Claude should not be invoked."
    ),
    "session_id": "claude-unexpected",
}}
print(json.dumps(payload))
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_question_answer_continuation_invokes_only_saved_target_agent_model_and_session(
    tmp_path,
) -> None:
    """Answering a central question keeps the saved target agent/model in a real run."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    codex_log = tmp_path / "logs" / "codex.jsonl"
    claude_log = tmp_path / "logs" / "claude.jsonl"
    fake_codex = bin_dir / "codex"
    fake_claude = bin_dir / "claude"
    _write_fake_codex(fake_codex, codex_log)
    _write_fake_claude(fake_claude, claude_log)

    config = TrinityConfig(
        project_dir=tmp_path,
        state_dir=tmp_path / ".trinity",
        transport_mode="one-shot",
        synthesis_mode="heuristic",
        round_timeout_seconds=5.0,
        provider_readiness_timeout_seconds=0.1,
        agents={
            "claude": AgentSpec(
                name="claude",
                provider=Provider.CLAUDE_CODE,
                cli_command=str(fake_claude),
                enabled=True,
            ),
            "codex": AgentSpec(
                name="codex",
                provider=Provider.CODEX,
                cli_command=str(fake_codex),
                enabled=True,
            ),
        },
    )
    workflow = WorkflowEngine(config.effective_state_dir)
    workflow.start(
        "Build a targeted workflow.",
        ["claude", "codex"],
        target_agents=("codex",),
        agent_model_overrides={"codex": "gpt-5"},
    )
    workflow.session.provider_sessions["codex:key"] = ProviderSessionRef(
        provider="codex",
        agent_name="codex",
        session_key="codex:key",
        provider_session_id="thread-before-answer",
        session_kind="codex_thread",
        access="read-only",
    )
    workflow.add_open_question(
        OpenQuestion(
            id="q-1",
            question="Which theme?",
            options=["dark", "light"],
        )
    )
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        archive_active_session=False,
    )

    outcome = controller.answer_question("q-1", "dark")

    assert outcome.running is True
    assert controller.wait_until_idle(timeout=5.0)
    final = controller.drain_updates()
    assert final is not None
    assert final.snapshot.state == "blueprint_ready"

    codex_calls = _read_jsonl(codex_log)
    claude_calls = _read_jsonl(claude_log)
    assert len(codex_calls) == 1
    assert claude_calls == []

    argv = [str(item) for item in codex_calls[0]["argv"]]
    stdin_text = str(codex_calls[0]["stdin"])
    assert argv[:3] == ["exec", "resume", "thread-before-answer"]
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "gpt-5"
    assert "dark" in stdin_text
    assert controller.workflow.session.runtime_models["codex"].actual_model == "gpt-5"
