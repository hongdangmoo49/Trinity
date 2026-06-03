"""Stateful workflow engine for Trinity TUI sessions."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from trinity.models import DeliberationResult
from trinity.workflow.decomposer import BlueprintDecomposer, classify_execution_intent
from trinity.workflow.models import (
    DecisionRecord,
    ExecutionResult,
    OpenQuestion,
    WorkPackage,
    WorkStatus,
    WorkflowSession,
    WorkflowState,
)


@dataclass(frozen=True)
class WorkflowInputAction:
    """Result of routing a user input through workflow state."""

    should_deliberate: bool
    prompt: str = ""
    decision_record: DecisionRecord | None = None
    started_new_workflow: bool = False


class WorkflowEngine:
    """Persisted state machine for user-guided multi-agent workflows."""

    def __init__(
        self,
        state_dir: Path,
        state_file: Path | None = None,
        events_file: Path | None = None,
        decomposer: BlueprintDecomposer | None = None,
    ):
        self.state_dir = state_dir
        workflow_dir = state_dir / "workflow"
        self.state_file = state_file or workflow_dir / "session.json"
        self.events_file = events_file or workflow_dir / "events.jsonl"
        self.decomposer = decomposer or BlueprintDecomposer()
        self.session = self._load_or_create()

    @property
    def state(self) -> WorkflowState:
        return self.session.state

    @property
    def pending_questions(self) -> list[OpenQuestion]:
        return self.session.open_questions

    @property
    def decisions(self) -> list[DecisionRecord]:
        return list(self.session.decisions)

    @property
    def work_packages(self) -> list[WorkPackage]:
        return list(self.session.work_packages)

    @property
    def execution_results(self) -> list[ExecutionResult]:
        return list(self.session.execution_results)

    @property
    def has_pending_execution(self) -> bool:
        """Return whether any generated package still needs execution."""
        return any(
            package.requires_execution
            and package.status
            in {
                WorkStatus.PENDING,
                WorkStatus.RUNNING,
                WorkStatus.WAITING_ON_DECISION,
                WorkStatus.BLOCKED,
                WorkStatus.FAILED,
            }
            for package in self.session.work_packages
        )

    def handle_user_input(
        self,
        text: str,
        active_agents: list[str],
    ) -> WorkflowInputAction:
        """Route a user input as a new goal or a pending-question answer."""
        if self.session.state == WorkflowState.NEEDS_USER_DECISION:
            return self.answer_pending_question(text)
        return self.start(text, active_agents)

    def start(
        self,
        goal: str,
        active_agents: list[str],
    ) -> WorkflowInputAction:
        """Start a new workflow for a user goal."""
        now = time.time()
        self.session = WorkflowSession(
            id=f"wf-{uuid4().hex[:12]}",
            goal=goal,
            state=WorkflowState.PREFLIGHT,
            active_agents=list(active_agents),
            created_at=now,
            updated_at=now,
        )
        self._persist("workflow_started", {"goal": goal, "active_agents": active_agents})
        self.set_state(WorkflowState.DELIBERATING, reason="user goal accepted")
        return WorkflowInputAction(
            should_deliberate=True,
            prompt=goal,
            started_new_workflow=True,
        )

    def answer_pending_question(self, answer: str) -> WorkflowInputAction:
        """Record an answer to the oldest open question and continue deliberation."""
        questions = self.pending_questions
        if not questions:
            return WorkflowInputAction(should_deliberate=False)

        question = questions[0]
        question.status = "answered"
        decision = DecisionRecord(
            id=f"dec-{len(self.session.decisions) + 1:03d}",
            question_id=question.id,
            decision=answer,
            decided_by="user",
            rationale=f"Answer to: {question.question}",
        )
        self.session.decisions.append(decision)
        self.session.updated_at = time.time()
        self._persist(
            "decision_recorded",
            {
                "decision_id": decision.id,
                "question_id": question.id,
                "decision": answer,
            },
        )

        if self.pending_questions:
            self.set_state(
                WorkflowState.NEEDS_USER_DECISION,
                reason="more blocking questions remain",
            )
            return WorkflowInputAction(
                should_deliberate=False,
                decision_record=decision,
            )

        self.set_state(WorkflowState.DELIBERATING, reason="user decision answered")
        return WorkflowInputAction(
            should_deliberate=True,
            prompt=self._build_decision_continuation_prompt(decision),
            decision_record=decision,
        )

    def add_open_question(self, question: OpenQuestion) -> None:
        """Add a pending question and move workflow to waiting state."""
        self.session.pending_questions.append(question)
        self.set_state(
            WorkflowState.NEEDS_USER_DECISION,
            reason=f"question added: {question.id}",
        )

    def mark_deliberation_result(self, result: DeliberationResult) -> None:
        """Update workflow state after a deliberation completes."""
        self.session.current_round = result.rounds_completed
        structured = result.metadata.get("structured_consensus")
        if isinstance(structured, dict):
            if self._apply_structured_questions(structured):
                self.set_state(
                    WorkflowState.NEEDS_USER_DECISION,
                    reason="structured deliberation requires user decision",
                )
                return

            blueprint = structured.get("final_blueprint")
            if structured.get("reached") and isinstance(blueprint, dict):
                self.session.blueprint = blueprint
                self.session.work_packages = self.decomposer.decompose(
                    blueprint,
                    self.session.active_agents,
                    requires_execution=self._requires_execution(result),
                )
                self.session.execution_results = []
                self.set_state(
                    WorkflowState.BLUEPRINT_READY,
                    reason="structured blueprint reached consensus",
                )
                return

        if result.has_consensus:
            self.session.blueprint = {
                "summary": result.consensus.summary if result.consensus else "",
            }
            self.session.work_packages = []
            self.session.execution_results = []
            self.set_state(
                WorkflowState.BLUEPRINT_READY,
                reason="deliberation reached consensus",
            )
        else:
            self.set_state(WorkflowState.FAILED, reason="deliberation ended without consensus")

    def _apply_structured_questions(self, structured: dict) -> bool:
        raw_questions = structured.get("open_questions", [])
        if not isinstance(raw_questions, list) or not raw_questions:
            return False

        existing = {
            self._normalize_question(question.question)
            for question in self.session.pending_questions
        }
        added = False
        saw_valid_question = False
        for item in raw_questions:
            if not isinstance(item, dict):
                continue
            question = OpenQuestion.from_dict(item)
            normalized = self._normalize_question(question.question)
            if not normalized:
                continue
            saw_valid_question = True
            if normalized in existing:
                continue
            self.session.pending_questions.append(question)
            existing.add(normalized)
            added = True
        return added or saw_valid_question

    @staticmethod
    def _normalize_question(question: str) -> str:
        return " ".join(question.strip().lower().split())

    def _requires_execution(self, result: DeliberationResult) -> bool:
        if any(task.requires_execution for task in result.tasks):
            return True

        text = "\n".join(
            part
            for part in (
                self.session.goal,
                result.user_prompt,
                result.consensus.summary if result.consensus else "",
            )
            if part
        )
        return classify_execution_intent(text)

    def begin_execution(self) -> None:
        """Move the workflow into execution before dispatching work packages."""
        if not self.session.work_packages:
            return
        self.set_state(WorkflowState.EXECUTING, reason="work package execution started")

    def record_execution_results(self, results: list[ExecutionResult]) -> None:
        """Persist execution results and derive the next workflow state."""
        if not results:
            return

        packages_by_id = {package.id: package for package in self.session.work_packages}
        existing_by_package = {
            result.package_id: result for result in self.session.execution_results
        }

        for result in results:
            package = packages_by_id.get(result.package_id)
            if package:
                package.status = result.status
            existing_by_package[result.package_id] = result

            for decision in result.decisions_made:
                if not any(existing.id == decision.id for existing in self.session.decisions):
                    self.session.decisions.append(decision)

            self._persist(
                "execution_result_recorded",
                {
                    "package_id": result.package_id,
                    "agent": result.agent_name,
                    "status": result.status.value,
                },
            )

        ordered_package_ids = [package.id for package in self.session.work_packages]
        self.session.execution_results = [
            existing_by_package[package_id]
            for package_id in ordered_package_ids
            if package_id in existing_by_package
        ]
        self.session.updated_at = time.time()

        executable = [
            package
            for package in self.session.work_packages
            if package.requires_execution
        ]
        if any(package.status == WorkStatus.FAILED for package in executable):
            self.set_state(WorkflowState.FAILED, reason="work package execution failed")
            return
        if any(
            package.status
            in {WorkStatus.BLOCKED, WorkStatus.WAITING_ON_DECISION}
            for package in executable
        ):
            self.set_state(
                WorkflowState.NEEDS_USER_DECISION,
                reason="work package execution is blocked",
            )
            return
        if executable and all(
            package.status == WorkStatus.DONE for package in executable
        ):
            self.set_state(
                WorkflowState.REVIEWING,
                reason="all work packages completed",
            )
            return
        self.set_state(
            WorkflowState.EXECUTING,
            reason="work package execution still in progress",
        )

    def set_state(self, state: WorkflowState, reason: str = "") -> None:
        """Set and persist workflow state."""
        old_state = self.session.state
        self.session.state = state
        self.session.updated_at = time.time()
        self._persist(
            "state_changed",
            {
                "from": old_state.value,
                "to": state.value,
                "reason": reason,
            },
        )

    def save(self) -> None:
        """Persist session.json."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(self.session.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _persist(self, event_type: str, data: dict) -> None:
        self.save()
        self.events_file.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": time.time(),
            "workflow_id": self.session.id,
            "event": event_type,
            "state": self.session.state.value,
            "data": data,
        }
        with self.events_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _load_or_create(self) -> WorkflowSession:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                return WorkflowSession.from_dict(data)
            except (json.JSONDecodeError, OSError, ValueError):
                pass
        return WorkflowSession(
            id=f"wf-{uuid4().hex[:12]}",
            goal="",
            state=WorkflowState.IDLE,
        )

    def _build_decision_continuation_prompt(self, decision: DecisionRecord) -> str:
        decisions = "\n".join(
            f"- {item.id}: {item.decision}" for item in self.session.decisions
        )
        return (
            "Continue the existing workflow using the user's decision below.\n\n"
            f"Original goal:\n{self.session.goal}\n\n"
            f"Latest decision ({decision.id}):\n{decision.decision}\n\n"
            f"All decisions:\n{decisions}\n\n"
            "Update the design based on these decisions and continue deliberation."
        )
