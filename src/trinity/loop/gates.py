"""Loop gate evaluation."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from trinity.config import TrinityConfig
from trinity.loop.models import LoopGateResult, LoopGateSpec, LoopRun, LoopSpec
from trinity.workflow import WorkflowEngine


class GateEvaluator:
    """Evaluate loop gates against local state and command output."""

    def __init__(self, config: TrinityConfig) -> None:
        self.config = config

    def evaluate(
        self,
        gate: LoopGateSpec,
        *,
        spec: LoopSpec,
        run: LoopRun,
        artifact_dir: Path,
    ) -> LoopGateResult:
        """Evaluate one gate and return a serializable result."""
        if gate.gate_type == "command":
            return self._evaluate_command(gate, spec=spec, run=run, artifact_dir=artifact_dir)
        if gate.gate_type == "workflow-state":
            return self._evaluate_workflow_state(gate, run=run)
        return LoopGateResult(
            id=gate.id,
            gate_type=gate.gate_type,
            status="error",
            summary=f"Unsupported loop gate type: {gate.gate_type}",
            iteration=run.iteration,
            retryable=gate.retryable,
            blocking=gate.required,
        )

    def _evaluate_command(
        self,
        gate: LoopGateSpec,
        *,
        spec: LoopSpec,
        run: LoopRun,
        artifact_dir: Path,
    ) -> LoopGateResult:
        started_at = time.time()
        if not gate.command.strip():
            return LoopGateResult(
                id=gate.id,
                gate_type=gate.gate_type,
                status="error",
                summary="Command gate is missing command.",
                iteration=run.iteration,
                retryable=gate.retryable,
                blocking=gate.required,
                started_at=started_at,
                finished_at=time.time(),
            )

        cwd = self._gate_cwd(gate, spec)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"gate-{gate.id}.txt"
        try:
            completed = subprocess.run(
                gate.command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=gate.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            output = "\n".join(
                [
                    f"Command: {gate.command}",
                    f"CWD: {cwd}",
                    f"Timed out after {gate.timeout_seconds:.1f}s",
                    "",
                    str(exc.stdout or ""),
                    str(exc.stderr or ""),
                ]
            )
            artifact_path.write_text(output, encoding="utf-8")
            return LoopGateResult(
                id=gate.id,
                gate_type=gate.gate_type,
                status="failed",
                summary=f"Command timed out after {gate.timeout_seconds:.1f}s.",
                iteration=run.iteration,
                artifact_path=str(artifact_path),
                retryable=gate.retryable,
                blocking=gate.required,
                started_at=started_at,
                finished_at=time.time(),
                details={"cwd": str(cwd), "command": gate.command},
            )

        output = "\n".join(
            [
                f"Command: {gate.command}",
                f"CWD: {cwd}",
                f"Exit code: {completed.returncode}",
                "",
                "[stdout]",
                completed.stdout or "",
                "",
                "[stderr]",
                completed.stderr or "",
            ]
        )
        artifact_path.write_text(output, encoding="utf-8")
        passed = completed.returncode == 0
        summary = (
            "Command exited with 0."
            if passed
            else f"Command exited with {completed.returncode}."
        )
        return LoopGateResult(
            id=gate.id,
            gate_type=gate.gate_type,
            status="passed" if passed else "failed",
            summary=summary,
            iteration=run.iteration,
            artifact_path=str(artifact_path),
            retryable=gate.retryable,
            blocking=gate.required,
            exit_code=completed.returncode,
            started_at=started_at,
            finished_at=time.time(),
            details={"cwd": str(cwd), "command": gate.command},
        )

    def _evaluate_workflow_state(
        self,
        gate: LoopGateSpec,
        *,
        run: LoopRun,
    ) -> LoopGateResult:
        started_at = time.time()
        allowed = set(gate.allowed_states or ("done", "post_review_ready"))
        workflow = WorkflowEngine(self.config.effective_state_dir)
        state = workflow.session.state.value
        passed = state in allowed
        return LoopGateResult(
            id=gate.id,
            gate_type=gate.gate_type,
            status="passed" if passed else "failed",
            summary=(
                f"Workflow state {state!r} is allowed."
                if passed
                else f"Workflow state {state!r} is not in {sorted(allowed)}."
            ),
            iteration=run.iteration,
            retryable=gate.retryable,
            blocking=gate.required,
            started_at=started_at,
            finished_at=time.time(),
            details={"state": state, "allowed_states": sorted(allowed)},
        )

    def _gate_cwd(self, gate: LoopGateSpec, spec: LoopSpec) -> Path:
        raw = gate.cwd or spec.target_workspace
        if not raw:
            return self.config.project_dir
        path = Path(raw).expanduser()
        if path.is_absolute():
            return path
        return self.config.project_dir / path
