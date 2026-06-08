"""Workflow runtime bridge for the Textual workbench."""

from __future__ import annotations

import asyncio
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from trinity.config import TrinityConfig
from trinity.models import DeliberationResult
from trinity.orchestrator import TrinityOrchestrator
from trinity.textual_app.snapshot import NexusSnapshotAdapter, WorkflowNexusSnapshot
from trinity.tui.events import TUIEvent, TUIEventBus, TUIEventType
from trinity.workflow import (
    ExecutionRetryPlan,
    ExecutionResult,
    WorkflowEngine,
    WorkflowInputAction,
    WorkflowPersistence,
    WorkflowState,
)

RunKind = Literal["deliberation", "execution"]
OrchestratorFactory = Callable[..., TrinityOrchestrator]


@dataclass(frozen=True)
class TextualWorkflowOutcome:
    """A UI-facing result of a workflow controller action."""

    snapshot: WorkflowNexusSnapshot
    message: str = ""
    running: bool = False
    execution_requested: bool = False
    target_workspace_required: bool = False
    execution_recovery_required: bool = False


@dataclass(frozen=True)
class TextualWorkflowArchiveOption:
    """A saved workflow summary suitable for Textual resume selection."""

    selector: str
    session_id: str
    goal: str
    state: str
    updated_at: float


class TextualWorkflowController:
    """Bridge Textual screen events to Trinity's workflow/orchestrator runtime."""

    def __init__(
        self,
        config: TrinityConfig,
        *,
        workflow: WorkflowEngine | None = None,
        snapshot_adapter: NexusSnapshotAdapter | None = None,
        orchestrator_factory: OrchestratorFactory | None = None,
        archive_active_session: bool = True,
    ) -> None:
        self.config = config
        self.persistence = WorkflowPersistence(config.effective_state_dir)
        if workflow is None and archive_active_session:
            self.persistence.archive_active_session()
        self.workflow = workflow or WorkflowEngine(config.effective_state_dir)
        self.snapshot_adapter = snapshot_adapter or NexusSnapshotAdapter(config)
        self.orchestrator_factory = orchestrator_factory or TrinityOrchestrator
        self._lock = threading.Lock()
        self._bus: TUIEventBus | None = None
        self._thread: threading.Thread | None = None
        self._run_kind: RunKind | None = None
        self._result: DeliberationResult | None = None
        self._execution_results: list[ExecutionResult] | None = None
        self._error: Exception | None = None
        self._completion_pending = False
        self._recent_events: list[TUIEvent] = []

    def snapshot(self) -> WorkflowNexusSnapshot:
        """Return the current UI projection, including transient provider events."""
        return self.snapshot_adapter.load_snapshot(self._recent_events)

    @property
    def is_running(self) -> bool:
        """Return whether a deliberation or execution worker is active."""
        thread = self._thread
        return thread is not None and thread.is_alive()

    def new_session(self) -> TextualWorkflowOutcome:
        """Archive the active workflow and return an idle snapshot."""
        if self.is_running:
            return self._outcome(message="Workflow is still running.", running=True)
        self.persistence.archive_active_session(force=True)
        self.workflow = WorkflowEngine(self.config.effective_state_dir)
        self._recent_events = []
        return self._outcome()

    def start_prompt(self, prompt: str) -> TextualWorkflowOutcome:
        """Start a workflow from the first Textual prompt."""
        if self.is_running:
            return self._outcome(message="Workflow is already running.", running=True)
        active_agents = self._active_agent_names()
        if not active_agents:
            return self._outcome(message="No active agents are configured.")
        self._recent_events = []
        action = self.workflow.start(prompt, active_agents)
        return self._apply_action(action)

    def submit_follow_up(self, text: str) -> TextualWorkflowOutcome:
        """Route Nexus follow-up text through the workflow state machine."""
        if self.is_running:
            return self._outcome(message="Workflow is still running.", running=True)
        active_agents = self._active_agent_names()
        if not active_agents:
            return self._outcome(message="No active agents are configured.")
        action = self.workflow.handle_user_input(text, active_agents)
        return self._apply_action(action)

    def answer_question(
        self,
        question_id: str,
        answer: str,
        *,
        replace: bool = False,
    ) -> TextualWorkflowOutcome:
        """Record a central-agent question answer and continue when possible."""
        if self.is_running:
            return self._outcome(message="Workflow is still running.", running=True)
        action = self.workflow.answer_question(question_id, answer, replace=replace)
        return self._apply_action(action)

    def answer_question_option(
        self,
        option_index: str,
        *,
        question_selector: str = "next",
        replace: bool = False,
    ) -> TextualWorkflowOutcome:
        """Record a numbered option answer and continue when possible."""
        if self.is_running:
            return self._outcome(message="Workflow is still running.", running=True)
        action = self.workflow.answer_question_option(
            option_index,
            question_selector=question_selector,
            replace=replace,
        )
        return self._apply_action(action)

    def request_execution(self, instruction: str = "") -> TextualWorkflowOutcome:
        """Enable and run execution for the current blueprint when possible."""
        if self.is_running:
            return self._outcome(message="Workflow is still running.", running=True)
        normalized_instruction = instruction.strip().lower()
        if normalized_instruction in {"retry", "retry-interrupted", "recovery retry"}:
            return self.confirm_execution_retry("all")
        if normalized_instruction in {"mark-interrupted", "mark interrupted", "mark"}:
            summary = self.workflow.mark_interrupted_execution()
            if summary is None:
                return self._outcome(message="No interrupted execution to mark.")
            return self._outcome(message="Execution marked as interrupted.")
        if normalized_instruction in {"abort", "abort-execution", "abort execution"}:
            summary = self.workflow.abort_interrupted_execution()
            if summary is None:
                return self._outcome(message="No interrupted execution to abort.")
            return self._outcome(message="Interrupted execution aborted.")

        recovery = self.workflow.detect_interrupted_execution(worker_running=self.is_running)
        if recovery is not None and str(recovery.get("state", "")) == "interrupted":
            return self._outcome(
                message=(
                    "Previous execution was interrupted. Review running packages before retrying."
                ),
                execution_recovery_required=True,
            )
        if self.workflow.state != WorkflowState.BLUEPRINT_READY:
            return self._outcome(message="No blueprint is ready. Finish planning before execution.")
        action = self.workflow.enable_execution_for_current_blueprint(instruction)
        return self._apply_action(action)

    def preview_execution_retry(
        self,
        selector: str = "all",
        package_ids: tuple[str, ...] | list[str] = (),
    ) -> ExecutionRetryPlan:
        """Return the retry plan that the UI should show before confirmation."""
        return self.workflow.build_execution_retry_plan(
            selector=selector,
            package_ids=package_ids,
        )

    def confirm_execution_retry(
        self,
        selector: str = "all",
        package_ids: tuple[str, ...] | list[str] = (),
    ) -> TextualWorkflowOutcome:
        """Prepare selected work packages and start a new execution run."""
        if self.is_running:
            return self._outcome(message="Workflow is still running.", running=True)
        plan = self.workflow.build_execution_retry_plan(
            selector=selector,
            package_ids=package_ids,
        )
        if not plan.selected:
            return self._outcome(message="No retryable work packages match the request.")
        if self.workflow.session.target_workspace is None:
            return self._outcome(
                message="Choose a target workspace before retrying execution.",
                target_workspace_required=True,
            )

        prepared = self.workflow.prepare_execution_retry(
            selector=selector,
            package_ids=package_ids,
        )
        if not prepared.selected:
            return self._outcome(message="No retryable work packages match the request.")
        self._start_execution()
        return self._outcome(
            message=f"Retrying work packages: {', '.join(prepared.selected)}.",
            execution_requested=True,
        )

    def set_target_workspace(
        self,
        path: Path,
        *,
        control_repo_confirmed: bool = False,
    ) -> TextualWorkflowOutcome:
        """Persist the target workspace selected by Textual preflight."""
        self.workflow.set_target_workspace(
            path,
            control_repo_confirmed=control_repo_confirmed,
        )
        return self._outcome()

    def clear_target_workspace(self) -> TextualWorkflowOutcome:
        """Clear the selected implementation workspace."""
        if self.is_running:
            return self._outcome(message="Workflow is still running.", running=True)
        self.workflow.clear_target_workspace()
        return self._outcome()

    def list_resume_options(self) -> list[TextualWorkflowArchiveOption]:
        """Return archived workflows ordered the same way /resume selectors resolve."""
        return [
            TextualWorkflowArchiveOption(
                selector=str(index),
                session_id=archive.session.id,
                goal=archive.session.goal,
                state=archive.session.state.value,
                updated_at=archive.session.updated_at,
            )
            for index, archive in enumerate(self.persistence.list_archives(), start=1)
        ]

    def resume_workflow(self, selector: str = "latest") -> TextualWorkflowOutcome:
        """Restore an archived workflow into the active Textual session."""
        if self.is_running:
            return self._outcome(message="Workflow is still running.", running=True)
        archives = self.persistence.list_archives()
        if not archives:
            return self._outcome(message="No saved workflow sessions to resume.")

        archive = archives[0]
        normalized = selector.lower().strip() or "latest"
        if normalized not in {"latest", "last", "newest"}:
            if normalized.isdigit() and 1 <= int(normalized) <= len(archives):
                archive = archives[int(normalized) - 1]
            else:
                found = next(
                    (item for item in archives if item.session.id.lower() == normalized),
                    None,
                )
                if found is None:
                    return self._outcome(message=f"No matching workflow session: {selector}")
                archive = found

        self.persistence.archive_active_session()
        self.persistence.restore_archive(archive)
        self.workflow = WorkflowEngine(self.config.effective_state_dir)
        recovery = self.workflow.detect_interrupted_execution(worker_running=False)
        self._recent_events = []
        return self._outcome(
            message=f"Resumed workflow {archive.session.id}.",
            execution_recovery_required=recovery is not None,
        )

    def drain_updates(self) -> TextualWorkflowOutcome | None:
        """Consume runtime events and complete finished background work."""
        events = self._poll_events()
        message = ""
        completion_changed = False

        with self._lock:
            completion_pending = self._completion_pending
            run_kind = self._run_kind
            result = self._result
            execution_results = self._execution_results
            error = self._error
            if completion_pending:
                self._completion_pending = False
                self._run_kind = None
                self._result = None
                self._execution_results = None
                self._error = None

        if completion_pending:
            completion_changed = True
            if error is not None:
                if run_kind == "execution":
                    self.workflow.abort_interrupted_execution()
                self.workflow.set_state(WorkflowState.FAILED, reason=str(error))
                message = f"Workflow error: {error}"
            elif run_kind == "deliberation" and result is not None:
                self.workflow.mark_deliberation_result(result)
            elif run_kind == "execution" and execution_results is not None:
                self.workflow.record_execution_results(execution_results, emit_events=False)

        if events or completion_changed:
            return self._outcome(message=message, running=self.is_running)
        return None

    def wait_until_idle(self, timeout: float = 5.0) -> bool:
        """Wait for the active worker to finish. Intended for tests."""
        deadline = time.time() + timeout
        while self.is_running and time.time() < deadline:
            thread = self._thread
            if thread is not None:
                thread.join(timeout=0.05)
        return not self.is_running

    def _apply_action(self, action: WorkflowInputAction) -> TextualWorkflowOutcome:
        message = action.message
        if action.should_deliberate:
            self._start_deliberation(action.prompt)
        elif action.execution_requested:
            self._start_execution()

        return self._outcome(
            message=message,
            execution_requested=action.execution_requested,
            target_workspace_required=action.target_workspace_required,
        )

    def _start_deliberation(self, prompt: str) -> None:
        bus = TUIEventBus()
        use_tmux = self._uses_tmux_transport()
        if use_tmux and shutil.which("tmux") is None:
            with self._lock:
                self._error = RuntimeError("transport_mode is 'tmux', but tmux is not installed.")
                self._run_kind = "deliberation"
                self._completion_pending = True
            return

        self._prepare_background_run(bus, "deliberation")

        def _run() -> None:
            try:
                orchestrator = self.orchestrator_factory(
                    self.config,
                    interactive=use_tmux,
                )
                orchestrator.set_event_bus(bus)
                result = asyncio.run(orchestrator.ask(prompt))
                with self._lock:
                    self._result = result
                    self._completion_pending = True
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                with self._lock:
                    self._error = exc
                    self._completion_pending = True

        self._thread = threading.Thread(
            target=_run,
            name="trinity-textual-deliberation",
            daemon=True,
        )
        self._thread.start()

    def _start_execution(self) -> None:
        if not self.workflow.has_pending_execution:
            return
        if self.workflow.session.target_workspace is None:
            return
        package_ids = self.workflow.pending_execution_package_ids()
        if not package_ids:
            return
        package_id_set = set(package_ids)
        dispatch_packages = [
            package
            for package in self.workflow.session.work_packages
            if package.id in package_id_set
        ]
        bus = TUIEventBus()
        use_tmux = self._uses_tmux_transport()
        self.workflow.begin_execution(package_ids)
        self._prepare_background_run(bus, "execution")

        def _run() -> None:
            try:
                orchestrator = self.orchestrator_factory(
                    self.config,
                    interactive=use_tmux,
                    target_workspace=self.workflow.session.target_workspace,
                    allow_control_repo_writes=(self.workflow.session.control_repo_target_confirmed),
                )
                orchestrator.set_event_bus(bus)
                results = asyncio.run(
                    orchestrator.execute_work_packages(
                        dispatch_packages,
                        decisions=self.workflow.decisions,
                    )
                )
                with self._lock:
                    self._execution_results = results
                    self._completion_pending = True
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                with self._lock:
                    self._error = exc
                    self._completion_pending = True

        self._thread = threading.Thread(
            target=_run,
            name="trinity-textual-execution",
            daemon=True,
        )
        self._thread.start()

    def _prepare_background_run(self, bus: TUIEventBus, run_kind: RunKind) -> None:
        with self._lock:
            self._bus = bus
            self._run_kind = run_kind
            self._result = None
            self._execution_results = None
            self._error = None
            self._completion_pending = False
        self._recent_events = []

    def _poll_events(self) -> list[TUIEvent]:
        bus = self._bus
        if bus is None:
            return []
        events = bus.poll()
        if not events:
            return []
        self._recent_events.extend(events)
        self._recent_events = self._recent_events[-200:]
        for event in events:
            self._consume_runtime_event(event)
        return events

    def _consume_runtime_event(self, event: TUIEvent) -> None:
        if event.type == TUIEventType.EXECUTION_BATCH_PLANNED:
            self.workflow.record_execution_batch_planned(
                self._event_batches(event),
                self._event_notices(event),
                self._event_occurred_at(event),
            )
        if event.type == TUIEventType.WORK_PACKAGE_STARTED:
            self.workflow.record_work_package_started(
                str(event.data.get("package_id") or ""),
                str(event.data.get("agent") or ""),
                self._event_occurred_at(event),
            )
        if event.type == TUIEventType.WORK_PACKAGE_COMPLETED:
            self.workflow.record_work_package_completed(
                str(event.data.get("package_id") or ""),
                str(event.data.get("agent") or ""),
                str(event.data.get("status") or ""),
                str(event.data.get("summary") or ""),
                self._event_occurred_at(event),
            )

    @staticmethod
    def _event_occurred_at(event: TUIEvent) -> float | None:
        value = event.data.get("occurred_at")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _event_batches(event: TUIEvent) -> list[list[str]]:
        batches = event.data.get("batches", [])
        if not isinstance(batches, list):
            return []
        normalized: list[list[str]] = []
        for batch in batches:
            if isinstance(batch, list):
                normalized.append([str(item) for item in batch if str(item).strip()])
        return normalized

    @staticmethod
    def _event_notices(event: TUIEvent) -> list[dict[str, object]]:
        notices = event.data.get("notices", [])
        if not isinstance(notices, list):
            return []
        return [item for item in notices if isinstance(item, dict)]

    def _outcome(
        self,
        *,
        message: str = "",
        running: bool | None = None,
        execution_requested: bool = False,
        target_workspace_required: bool = False,
        execution_recovery_required: bool = False,
    ) -> TextualWorkflowOutcome:
        return TextualWorkflowOutcome(
            snapshot=self.snapshot(),
            message=message,
            running=self._has_active_or_pending_work() if running is None else running,
            execution_requested=execution_requested,
            target_workspace_required=target_workspace_required,
            execution_recovery_required=execution_recovery_required,
        )

    def _has_active_or_pending_work(self) -> bool:
        with self._lock:
            pending = self._completion_pending
        return self.is_running or pending

    def _active_agent_names(self) -> list[str]:
        return list(self.config.active_agents.keys())

    def _uses_tmux_transport(self) -> bool:
        return self.config.transport_mode.lower() == "tmux"
