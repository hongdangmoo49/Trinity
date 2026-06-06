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
    ) -> TextualWorkflowOutcome:
        """Record a central-agent question answer and continue when possible."""
        if self.is_running:
            return self._outcome(message="Workflow is still running.", running=True)
        action = self.workflow.answer_question(question_id, answer)
        return self._apply_action(action)

    def request_execution(self, instruction: str = "") -> TextualWorkflowOutcome:
        """Enable and run execution for the current blueprint when possible."""
        if self.is_running:
            return self._outcome(message="Workflow is still running.", running=True)
        if self.workflow.state != WorkflowState.BLUEPRINT_READY:
            return self._outcome(
                message="No blueprint is ready. Finish planning before execution."
            )
        action = self.workflow.enable_execution_for_current_blueprint(instruction)
        return self._apply_action(action)

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
                self._error = RuntimeError(
                    "transport_mode is 'tmux', but tmux is not installed."
                )
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
        bus = TUIEventBus()
        use_tmux = self._uses_tmux_transport()
        self.workflow.begin_execution()
        self._prepare_background_run(bus, "execution")

        def _run() -> None:
            try:
                orchestrator = self.orchestrator_factory(
                    self.config,
                    interactive=use_tmux,
                    target_workspace=self.workflow.session.target_workspace,
                    allow_control_repo_writes=(
                        self.workflow.session.control_repo_target_confirmed
                    ),
                )
                orchestrator.set_event_bus(bus)
                results = asyncio.run(
                    orchestrator.execute_work_packages(
                        self.workflow.session.work_packages,
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
        if event.type == TUIEventType.WORK_PACKAGE_STARTED:
            self.workflow.record_work_package_started(
                str(event.data.get("package_id") or ""),
                str(event.data.get("agent") or ""),
                event.data.get("occurred_at"),
            )
        elif event.type == TUIEventType.WORK_PACKAGE_COMPLETED:
            self.workflow.record_work_package_completed(
                str(event.data.get("package_id") or ""),
                str(event.data.get("agent") or ""),
                str(event.data.get("status") or ""),
                str(event.data.get("summary") or ""),
                event.data.get("occurred_at"),
            )

    def _outcome(
        self,
        *,
        message: str = "",
        running: bool | None = None,
        execution_requested: bool = False,
        target_workspace_required: bool = False,
    ) -> TextualWorkflowOutcome:
        return TextualWorkflowOutcome(
            snapshot=self.snapshot(),
            message=message,
            running=self._has_active_or_pending_work() if running is None else running,
            execution_requested=execution_requested,
            target_workspace_required=target_workspace_required,
        )

    def _has_active_or_pending_work(self) -> bool:
        with self._lock:
            pending = self._completion_pending
        return self.is_running or pending

    def _active_agent_names(self) -> list[str]:
        return list(self.config.active_agents.keys())

    def _uses_tmux_transport(self) -> bool:
        return self.config.transport_mode.lower() == "tmux"
