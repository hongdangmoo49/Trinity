from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from trinity.config import TrinityConfig
from trinity.loop import (
    DefaultWorkflowRunner,
    GateEvaluator,
    LoopEngine,
    LoopPersistence,
    LoopStatus,
    WorkflowIterationResult,
)
from trinity.workflow import WorkflowPersistence, WorkflowSession, WorkflowState


class FakeWorkflowRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run_iteration(self, spec, prompt: str) -> WorkflowIterationResult:
        self.calls.append(prompt)
        return WorkflowIterationResult(
            workflow_id=f"wf-{len(self.calls)}",
            token_used=11,
            summary="fake workflow",
        )


def _config(tmp_path: Path) -> TrinityConfig:
    return TrinityConfig.default_config(project_dir=tmp_path)


def _write_spec(
    state_dir: Path,
    *,
    command: str,
    spec_id: str = "quality",
    max_iterations: int = 2,
) -> Path:
    specs_dir = state_dir / "loops" / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    path = specs_dir / f"{spec_id}.toml"
    path.write_text(
        f"""
id = "{spec_id}"
title = "Quality Loop"
goal = "Fix quality issues."
agents = ["claude"]
max_iterations = {max_iterations}

[trigger]
type = "manual"

[[gates]]
id = "unit"
type = "command"
command = '''{command}'''
required = true

[stop_policy]
on_gate_pass = "complete"
on_gate_fail = "iterate"
on_max_iterations = "pause"
""",
        encoding="utf-8",
    )
    return path


def test_loop_persistence_loads_spec_from_default_specs_dir(tmp_path):
    config = _config(tmp_path)
    command = f"{sys.executable} -c \"import sys; sys.exit(0)\""
    _write_spec(config.effective_state_dir, command=command)

    spec = LoopPersistence(config.effective_state_dir).load_spec("quality")

    assert spec.id == "quality"
    assert spec.title == "Quality Loop"
    assert spec.gates[0].id == "unit"
    assert spec.gates[0].command == command


def test_loop_engine_run_once_completes_when_required_gates_pass(tmp_path):
    config = _config(tmp_path)
    command = f"{sys.executable} -c \"import sys; sys.exit(0)\""
    spec = LoopPersistence(config.effective_state_dir).load_spec(
        _write_spec(config.effective_state_dir, command=command)
    )
    runner = FakeWorkflowRunner()

    run = LoopEngine(config, workflow_runner=runner).run(spec, once=True)

    assert run.status == LoopStatus.COMPLETE
    assert run.iteration == 1
    assert run.workflow_ids == ["wf-1"]
    assert run.token_used == 11
    assert run.gate_results[0].status == "passed"
    assert runner.calls == ["Fix quality issues."]


def test_loop_engine_run_once_pauses_when_required_gate_fails(tmp_path):
    config = _config(tmp_path)
    command = f"{sys.executable} -c \"import sys; sys.exit(2)\""
    spec = LoopPersistence(config.effective_state_dir).load_spec(
        _write_spec(config.effective_state_dir, command=command)
    )

    run = LoopEngine(config, workflow_runner=FakeWorkflowRunner()).run(spec, once=True)

    assert run.status == LoopStatus.PAUSED
    assert "required gates failed" in run.stop_reason
    assert run.gate_results[0].status == "failed"
    artifact = Path(run.gate_results[0].artifact_path)
    assert artifact.exists()
    assert "Exit code: 2" in artifact.read_text(encoding="utf-8")


def test_loop_engine_until_stop_retries_until_max_iterations(tmp_path):
    config = _config(tmp_path)
    command = f"{sys.executable} -c \"import sys; sys.exit(1)\""
    spec = LoopPersistence(config.effective_state_dir).load_spec(
        _write_spec(config.effective_state_dir, command=command, max_iterations=2)
    )
    runner = FakeWorkflowRunner()

    run = LoopEngine(config, workflow_runner=runner).run(spec, once=False)

    assert run.status == LoopStatus.PAUSED
    assert run.iteration == 2
    assert len(runner.calls) == 2
    assert "Previous loop iteration failed" in runner.calls[1]


def test_workflow_state_gate_reads_current_workflow_state(tmp_path):
    config = _config(tmp_path)
    WorkflowPersistence(config.effective_state_dir).save(
        WorkflowSession(
            id="wf-done",
            goal="done",
            state=WorkflowState.DONE,
        )
    )
    spec_path = config.effective_state_dir / "loops" / "specs" / "state.toml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        """
id = "state"
title = "State Loop"
goal = "Check state."

[[gates]]
id = "workflow"
type = "workflow-state"
states = ["done"]
required = true
""",
        encoding="utf-8",
    )
    persistence = LoopPersistence(config.effective_state_dir)
    spec = persistence.load_spec("state")
    run = persistence.create_run(spec)
    run.iteration = 1

    result = GateEvaluator(config).evaluate(
        spec.gates[0],
        spec=spec,
        run=run,
        artifact_dir=persistence.artifact_dir(run.id, 1),
    )

    assert result.status == "passed"
    assert result.details["state"] == "done"


def test_default_workflow_runner_applies_loop_resource_packs_to_selected_agents(tmp_path):
    config = _config(tmp_path)
    spec = LoopPersistence(config.effective_state_dir).load_spec(
        _write_spec(
            config.effective_state_dir,
            command=f"{sys.executable} -c \"import sys; sys.exit(0)\"",
        )
    )
    spec = replace(spec, resource_packs=("trinity-core", "review-hardening"))
    runner = DefaultWorkflowRunner(config)

    runner._apply_resource_packs(spec, ["claude"])

    assert config.agents["claude"].resource_packs == [
        "trinity-core",
        "review-hardening",
    ]
    assert config.agents["codex"].resource_packs == []


def test_loop_stop_marks_run_cancelled(tmp_path):
    config = _config(tmp_path)
    command = f"{sys.executable} -c \"import sys; sys.exit(0)\""
    persistence = LoopPersistence(config.effective_state_dir)
    spec = persistence.load_spec(_write_spec(config.effective_state_dir, command=command))
    run = persistence.create_run(spec)

    stopped = LoopEngine(config, persistence=persistence).stop(run, reason="manual")

    loaded = persistence.load_run(stopped.id)
    assert loaded.status == LoopStatus.CANCELLED
    assert loaded.stop_reason == "manual"
