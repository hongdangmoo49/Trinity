"""Loop orchestration layer built on top of Trinity workflows."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from trinity.config import TrinityConfig
from trinity.loop.gates import GateEvaluator
from trinity.loop.models import LoopGateResult, LoopRun, LoopSpec, LoopStatus
from trinity.loop.persistence import LoopPersistence
from trinity.orchestrator import TrinityOrchestrator
from trinity.workflow import WorkflowEngine


@dataclass(frozen=True)
class WorkflowIterationResult:
    """Small summary returned after one delegated workflow iteration."""

    workflow_id: str = ""
    token_used: int = 0
    summary: str = ""


class WorkflowRunner(Protocol):
    """Protocol for running one Trinity workflow iteration."""

    def run_iteration(
        self,
        spec: LoopSpec,
        prompt: str,
    ) -> WorkflowIterationResult:
        """Run one workflow iteration and return metadata."""


class NoopWorkflowRunner:
    """Workflow runner used for gate-only diagnostics and tests."""

    def run_iteration(
        self,
        spec: LoopSpec,
        prompt: str,
    ) -> WorkflowIterationResult:
        return WorkflowIterationResult(summary="workflow skipped")


class DefaultWorkflowRunner:
    """Run one real Trinity deliberation workflow for a loop iteration."""

    def __init__(self, config: TrinityConfig) -> None:
        self.config = config

    def run_iteration(
        self,
        spec: LoopSpec,
        prompt: str,
    ) -> WorkflowIterationResult:
        active_agents = self._active_agent_names(spec)
        if not active_agents:
            raise RuntimeError("No active agents are available for this loop.")
        self._apply_resource_packs(spec, active_agents)

        workflow = WorkflowEngine(self.config.effective_state_dir)
        action = workflow.start(prompt, active_agents, target_agents=active_agents)
        if spec.target_workspace:
            workflow.set_target_workspace(self._target_workspace(spec))

        orchestrator = TrinityOrchestrator(
            self.config,
            active_agent_names=tuple(action.target_agents or active_agents),
            target_workspace=self._target_workspace(spec) if spec.target_workspace else None,
        )
        result = asyncio.run(orchestrator.ask(action.prompt))
        workflow.mark_deliberation_result(result)
        return WorkflowIterationResult(
            workflow_id=workflow.session.id,
            token_used=int(getattr(result, "total_tokens_used", 0) or 0),
            summary=(
                getattr(result.consensus, "summary", "")
                if getattr(result, "consensus", None) is not None
                else ""
            ),
        )

    def _active_agent_names(self, spec: LoopSpec) -> list[str]:
        configured = set(self.config.active_agents)
        if spec.agents:
            return [name for name in spec.agents if name in configured]
        return list(self.config.active_agents)

    def _apply_resource_packs(self, spec: LoopSpec, active_agents: list[str]) -> None:
        if not spec.resource_packs:
            return
        packs = list(spec.resource_packs)
        for name in active_agents:
            agent = self.config.agents.get(name)
            if agent is None:
                continue
            agent.resource_packs = packs

    def _target_workspace(self, spec: LoopSpec) -> Path:
        path = Path(spec.target_workspace).expanduser()
        if path.is_absolute():
            return path
        return self.config.project_dir / path


class LoopEngine:
    """Coordinate loop runs, workflow iterations, gates, and persistence."""

    def __init__(
        self,
        config: TrinityConfig,
        *,
        persistence: LoopPersistence | None = None,
        gate_evaluator: GateEvaluator | None = None,
        workflow_runner: WorkflowRunner | None = None,
    ) -> None:
        self.config = config
        self.persistence = persistence or LoopPersistence(config.effective_state_dir)
        self.gate_evaluator = gate_evaluator or GateEvaluator(config)
        self.workflow_runner = workflow_runner or DefaultWorkflowRunner(config)

    def run(
        self,
        spec: LoopSpec,
        *,
        once: bool = True,
        run_workflow: bool = True,
        run: LoopRun | None = None,
    ) -> LoopRun:
        """Run one loop until it stops or one iteration completes."""
        current = run or self.persistence.create_run(spec)
        current.status = LoopStatus.RUNNING
        self.persistence.save_run(current)
        self.persistence.append_event(
            current,
            "loop_run_started",
            {"once": once, "run_workflow": run_workflow},
        )

        runner: WorkflowRunner = self.workflow_runner if run_workflow else NoopWorkflowRunner()
        started_at = current.started_at

        while current.status == LoopStatus.RUNNING:
            if self._runtime_exceeded(spec, started_at):
                self._stop(current, spec.stop_policy.on_budget_exceeded, "runtime budget exceeded")
                break
            if current.iteration >= spec.max_iterations:
                self._stop(current, spec.stop_policy.on_max_iterations, "max iterations reached")
                break

            current.iteration += 1
            self.persistence.save_run(current)
            self.persistence.append_event(
                current,
                "loop_iteration_started",
                {"iteration": current.iteration},
            )
            self.persistence.append_ledger(
                current,
                f"## Iteration {current.iteration}\n\n"
                f"- status: started\n"
                f"- workflow: {'enabled' if run_workflow else 'skipped'}",
            )

            try:
                workflow_result = runner.run_iteration(
                    spec,
                    self._iteration_prompt(spec, current),
                )
            except Exception as exc:
                self._fail_iteration(current, exc)
                break

            if workflow_result.workflow_id:
                current.workflow_ids.append(workflow_result.workflow_id)
            current.token_used += workflow_result.token_used
            if self._token_budget_exceeded(spec, current):
                self._stop(current, spec.stop_policy.on_budget_exceeded, "token budget exceeded")
                break

            gate_results = self._evaluate_gates(spec, current)
            current.gate_results.extend(gate_results)
            self.persistence.write_iteration_gate_results(current)
            self._record_iteration_summary(current, gate_results, workflow_result)

            failed_required = [
                result
                for result in gate_results
                if result.blocking and not result.passed
            ]
            if not failed_required:
                self._stop(current, spec.stop_policy.on_gate_pass, "required gates passed")
                break

            if once:
                self._stop(
                    current,
                    "pause",
                    "required gates failed: "
                    + ", ".join(result.id for result in failed_required),
                )
                break

            if current.iteration >= spec.max_iterations:
                self._stop(
                    current,
                    spec.stop_policy.on_max_iterations,
                    "max iterations reached with failing gates: "
                    + ", ".join(result.id for result in failed_required),
                )
                break

            action = spec.stop_policy.on_gate_fail
            if action != "iterate":
                self._stop(
                    current,
                    action,
                    "required gates failed: "
                    + ", ".join(result.id for result in failed_required),
                )
                break

            self.persistence.append_event(
                current,
                "loop_iteration_retrying",
                {"failed_gates": [result.id for result in failed_required]},
            )
            self.persistence.save_run(current)

        return current

    def stop(self, run: LoopRun, *, reason: str = "stopped by user") -> LoopRun:
        """Cancel a loop run without deleting its ledger."""
        run.status = LoopStatus.CANCELLED
        run.stop_reason = reason
        run.completed_at = time.time()
        self.persistence.save_run(run)
        self.persistence.append_event(run, "loop_run_cancelled", {"reason": reason})
        self.persistence.append_ledger(run, f"## Stopped\n\n- reason: {reason}")
        return run

    def _evaluate_gates(self, spec: LoopSpec, run: LoopRun) -> list[LoopGateResult]:
        artifact_dir = self.persistence.artifact_dir(run.id, run.iteration)
        results = [
            self.gate_evaluator.evaluate(
                gate,
                spec=spec,
                run=run,
                artifact_dir=artifact_dir,
            )
            for gate in spec.gates
        ]
        if not results:
            results.append(
                LoopGateResult(
                    id="no-gates",
                    gate_type="internal",
                    status="passed",
                    summary="No gates configured.",
                    iteration=run.iteration,
                    retryable=False,
                    blocking=False,
                )
            )
        return results

    def _record_iteration_summary(
        self,
        run: LoopRun,
        gate_results: list[LoopGateResult],
        workflow_result: WorkflowIterationResult,
    ) -> None:
        lines = [
            f"## Iteration {run.iteration} Result",
            "",
        ]
        if workflow_result.workflow_id:
            lines.append(f"- workflow_id: `{workflow_result.workflow_id}`")
        if workflow_result.summary:
            lines.append(f"- workflow_summary: {workflow_result.summary}")
        if workflow_result.token_used:
            lines.append(f"- token_used: {workflow_result.token_used}")
        lines.append("")
        lines.append("| Gate | Status | Summary |")
        lines.append("| :--- | :--- | :--- |")
        for result in gate_results:
            lines.append(
                f"| `{result.id}` | {result.status} | {result.summary.replace('|', '/')} |"
            )
        self.persistence.append_ledger(run, "\n".join(lines))
        self.persistence.append_event(
            run,
            "loop_iteration_completed",
            {
                "gate_results": [result.to_dict() for result in gate_results],
                "workflow_id": workflow_result.workflow_id,
                "token_used": workflow_result.token_used,
            },
        )

    def _stop(self, run: LoopRun, action: str, reason: str) -> None:
        normalized = action.strip().lower()
        if normalized == "complete":
            run.status = LoopStatus.COMPLETE
        elif normalized == "fail":
            run.status = LoopStatus.FAILED
        elif normalized == "cancel":
            run.status = LoopStatus.CANCELLED
        else:
            run.status = LoopStatus.PAUSED
        run.stop_reason = reason
        run.completed_at = time.time()
        self.persistence.save_run(run)
        self.persistence.append_event(
            run,
            "loop_run_stopped",
            {"status": run.status.value, "reason": reason},
        )
        self.persistence.append_ledger(
            run,
            f"## Loop Stopped\n\n- status: {run.status.value}\n- reason: {reason}",
        )

    def _fail_iteration(self, run: LoopRun, exc: Exception) -> None:
        run.status = LoopStatus.FAILED
        run.stop_reason = f"workflow iteration failed: {exc}"
        run.completed_at = time.time()
        self.persistence.save_run(run)
        self.persistence.append_event(
            run,
            "loop_iteration_failed",
            {"error": str(exc)},
        )
        self.persistence.append_ledger(
            run,
            f"## Iteration {run.iteration} Failed\n\n- error: {exc}",
        )

    def _iteration_prompt(self, spec: LoopSpec, run: LoopRun) -> str:
        if run.iteration <= 1:
            return spec.goal
        failed = [
            result
            for result in run.gate_results
            if result.iteration == run.iteration - 1 and result.blocking and not result.passed
        ]
        if not failed:
            return spec.goal
        summaries = "\n".join(
            f"- {result.id}: {result.summary}" for result in failed
        )
        return (
            f"{spec.goal}\n\n"
            "Previous loop iteration failed these required gates. "
            "Use the failure evidence to adjust the plan before continuing:\n"
            f"{summaries}"
        )

    @staticmethod
    def _runtime_exceeded(spec: LoopSpec, started_at: float) -> bool:
        return bool(
            spec.max_runtime_seconds
            and time.time() - started_at >= spec.max_runtime_seconds
        )

    @staticmethod
    def _token_budget_exceeded(spec: LoopSpec, run: LoopRun) -> bool:
        return bool(spec.max_token_budget and run.token_used >= spec.max_token_budget)
