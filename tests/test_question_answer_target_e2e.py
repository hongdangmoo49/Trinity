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
    """Write a fake Claude CLI that records argv/stdin and emits JSON."""
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
    "rationale": "Targeted Claude continuation used the saved answer.",
    "blueprint": {{
        "title": "Claude Continuation Blueprint",
        "summary": "Continue with the selected Claude model only.",
        "architecture": [],
        "data_flow": ["answer -> claude -> blueprint"],
        "external_dependencies": [],
        "risks": [],
        "acceptance_criteria": ["Claude receives the answered prompt."],
        "open_questions": [],
        "work_packages": [
            {{
                "id": "WP-001",
                "title": "Verify Claude continuation",
                "owner_agent": "claude",
                "objective": "Verify Claude target continuity.",
                "scope": ["Use the answered decision."],
                "out_of_scope": [],
                "dependencies": [],
                "expected_files": ["docs/"],
                "acceptance_criteria": ["Only Claude is invoked."],
                "estimated_weight": 1,
                "parallel_group": 1,
                "parallelizable": True,
                "risk": "low"
            }}
        ]
    }}
}}
payload = {{
    "result": json.dumps(agent_payload, ensure_ascii=False),
    "session_id": "claude-after-answer",
    "model": "opus[1m]",
    "usage": {{"input_tokens": 11, "output_tokens": 22}},
}}
print(json.dumps(payload, ensure_ascii=False))
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def _write_fake_antigravity(path: Path, log_path: Path) -> None:
    """Write a fake Antigravity CLI that records argv/stdin and emits text."""
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

args = sys.argv[1:]
provider_log = ""
for index, arg in enumerate(args):
    if arg == "--log-file" and index + 1 < len(args):
        provider_log = args[index + 1]
    elif arg.startswith("--log-file="):
        provider_log = arg.split("=", 1)[1]
if provider_log:
    log_file = pathlib.Path(provider_log)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(
        "conversation=agy-after-answer\\n"
        "selected model: Gemini 3.1 Pro (High)\\n",
        encoding="utf-8",
    )

agent_payload = {{
    "vote": "APPROVE",
    "rationale": "Targeted Antigravity continuation used the saved answer.",
    "blueprint": {{
        "title": "Antigravity Continuation Blueprint",
        "summary": "Continue with the selected Antigravity model only.",
        "architecture": [],
        "data_flow": ["answer -> antigravity -> blueprint"],
        "external_dependencies": [],
        "risks": [],
        "acceptance_criteria": ["Antigravity receives the answered prompt."],
        "open_questions": [],
        "work_packages": [
            {{
                "id": "WP-001",
                "title": "Verify Antigravity continuation",
                "owner_agent": "antigravity",
                "objective": "Verify Antigravity target continuity.",
                "scope": ["Use the answered decision."],
                "out_of_scope": [],
                "dependencies": [],
                "expected_files": ["docs/"],
                "acceptance_criteria": ["Only Antigravity is invoked."],
                "estimated_weight": 1,
                "parallel_group": 1,
                "parallelizable": True,
                "risk": "low"
            }}
        ]
    }}
}}
print(json.dumps(agent_payload, ensure_ascii=False))
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


def _provider_turn_calls(calls: list[dict[str, object]]) -> list[dict[str, object]]:
    preflight_argv = {
        ("--version",),
        ("debug", "models"),
        ("debug", "models", "--bundled"),
        ("models",),
    }
    return [
        call
        for call in calls
        if tuple(str(item) for item in call.get("argv", [])) not in preflight_argv
    ]


def test_question_answer_continuation_invokes_only_saved_target_agent_model_and_session(
    tmp_path,
) -> None:
    """Answering keeps saved target/model while preserving Codex sandbox policy."""
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

    codex_calls = _provider_turn_calls(_read_jsonl(codex_log))
    claude_calls = _provider_turn_calls(_read_jsonl(claude_log))
    assert len(codex_calls) == 1
    assert claude_calls == []

    argv = [str(item) for item in codex_calls[0]["argv"]]
    stdin_text = str(codex_calls[0]["stdin"])
    assert argv[:2] == ["exec", "--json"]
    assert "resume" not in argv
    assert "--sandbox" in argv
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert "--cd" in argv
    assert argv[argv.index("--cd") + 1] == str(tmp_path)
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "gpt-5"
    assert "dark" in stdin_text
    assert controller.workflow.session.runtime_models["codex"].actual_model == "gpt-5"


def test_question_answer_continuation_invokes_claude_resume_for_targeted_agent(
    tmp_path,
) -> None:
    """Claude question answers continue the saved provider session with --resume."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    claude_log = tmp_path / "logs" / "claude.jsonl"
    codex_log = tmp_path / "logs" / "codex.jsonl"
    fake_claude = bin_dir / "claude"
    fake_codex = bin_dir / "codex"
    _write_fake_claude(fake_claude, claude_log)
    _write_fake_codex(fake_codex, codex_log)

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
        target_agents=("claude",),
        agent_model_overrides={"claude": "opus[1m]"},
    )
    workflow.session.provider_sessions["claude:key"] = ProviderSessionRef(
        provider="claude-code",
        agent_name="claude",
        session_key="claude:key",
        provider_session_id="claude-before-answer",
        session_kind="claude_session",
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

    claude_calls = _provider_turn_calls(_read_jsonl(claude_log))
    codex_calls = _provider_turn_calls(_read_jsonl(codex_log))
    assert len(claude_calls) == 1
    assert codex_calls == []

    argv = [str(item) for item in claude_calls[0]["argv"]]
    assert "--resume" in argv
    assert argv[argv.index("--resume") + 1] == "claude-before-answer"
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "opus[1m]"
    assert "-p" in argv
    assert "--output-format" in argv
    assert "dark" in " ".join(argv)
    assert (
        controller.workflow.session.runtime_models["claude"].actual_model
        == "opus[1m]"
    )


def test_question_answer_continuation_invokes_agy_conversation_for_targeted_agent(
    tmp_path,
) -> None:
    """Antigravity question answers continue the saved provider conversation."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    agy_log = tmp_path / "logs" / "agy.jsonl"
    claude_log = tmp_path / "logs" / "claude.jsonl"
    fake_agy = bin_dir / "agy"
    fake_claude = bin_dir / "claude"
    _write_fake_antigravity(fake_agy, agy_log)
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
            "antigravity": AgentSpec(
                name="antigravity",
                provider=Provider.ANTIGRAVITY_CLI,
                cli_command=str(fake_agy),
                enabled=True,
            ),
        },
    )
    workflow = WorkflowEngine(config.effective_state_dir)
    workflow.start(
        "Build a targeted workflow.",
        ["claude", "antigravity"],
        target_agents=("antigravity",),
        agent_model_overrides={"antigravity": "Gemini 3.1 Pro (High)"},
    )
    workflow.session.provider_sessions["agy:key"] = ProviderSessionRef(
        provider="antigravity-cli",
        agent_name="antigravity",
        session_key="agy:key",
        provider_session_id="agy-before-answer",
        session_kind="antigravity_conversation",
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

    agy_calls = _provider_turn_calls(_read_jsonl(agy_log))
    claude_calls = _provider_turn_calls(_read_jsonl(claude_log))
    assert len(agy_calls) == 1
    assert claude_calls == []

    argv = [str(item) for item in agy_calls[0]["argv"]]
    assert "--conversation" in argv
    assert argv[argv.index("--conversation") + 1] == "agy-before-answer"
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "Gemini 3.1 Pro (High)"
    assert "--sandbox" in argv
    assert "--print" in argv
    assert "dark" in " ".join(argv)
    assert (
        controller.workflow.session.runtime_models["antigravity"].model_label
        == "Gemini 3.1 Pro (High)"
    )
