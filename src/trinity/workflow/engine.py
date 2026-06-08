"""Stateful workflow engine for Trinity TUI sessions."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable
from uuid import uuid4

from trinity.models import DeliberationResult
from trinity.providers.policy import (
    ExecutionAuthority,
    ExecutionScope,
    InvocationAccess,
    ParallelExecutionPolicy,
)
from trinity.workflow.decomposer import (
    BlueprintDecomposer,
    classify_blueprint_followup_action,
    classify_execution_intent,
)
from trinity.workflow.models import (
    Blueprint,
    DecisionRecord,
    ExecutionResult,
    OpenQuestion,
    SubtaskResult,
    WorkPackage,
    WorkStatus,
    WorkflowSession,
    WorkflowState,
)
from trinity.workflow.persistence import WorkflowPersistence
from trinity.workflow.review import (
    FINAL_REVIEW_PACKAGE_ID,
    ReviewPackage,
    ReviewResult,
    ReviewStatus,
)

if TYPE_CHECKING:
    from trinity.context.shared import SharedContextEngine


@dataclass(frozen=True)
class WorkflowInputAction:
    """Result of routing a user input through workflow state."""

    should_deliberate: bool
    prompt: str = ""
    decision_record: DecisionRecord | None = None
    started_new_workflow: bool = False
    replaced_decision: bool = False
    execution_requested: bool = False
    target_workspace_required: bool = False
    message: str = ""


@dataclass(frozen=True)
class RetrySkip:
    """A work package omitted from an execution retry plan."""

    package_id: str
    status: str
    reason: str


@dataclass(frozen=True)
class ExecutionRetryPlan:
    """Preview of the work packages that an execution retry will restart."""

    selector: str
    requested: tuple[str, ...]
    selected: tuple[str, ...]
    skipped: tuple[RetrySkip, ...]
    target_workspace: Path | None


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
        self.persistence = WorkflowPersistence(
            state_dir,
            state_file=state_file or workflow_dir / "session.json",
            events_file=events_file or workflow_dir / "events.jsonl",
        )
        self.state_file = self.persistence.session_path
        self.events_file = self.persistence.events_path
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
    def target_workspace(self) -> Path | None:
        return self.session.target_workspace

    @property
    def subtask_results(self) -> list[SubtaskResult]:
        return list(self.session.subtask_results)

    @property
    def review_packages(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.session.review_packages]

    @property
    def review_results(self) -> list[ReviewResult]:
        return self._review_results()

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

    @property
    def has_interrupted_execution(self) -> bool:
        """Return whether the persisted execution run needs recovery."""
        return self.execution_recovery_summary() is not None

    def handle_user_input(
        self,
        text: str,
        active_agents: list[str],
    ) -> WorkflowInputAction:
        """Route plain session text through the current workflow state."""
        if self.session.state == WorkflowState.NEEDS_USER_DECISION:
            return self.answer_pending_question(text)
        if self._can_continue_existing_blueprint():
            return self.continue_from_blueprint(text, active_agents)
        return self.start(text, active_agents)

    def _can_continue_existing_blueprint(self) -> bool:
        """Return whether free text should stay attached to this workflow."""
        return self.session.blueprint is not None and self.session.state in {
            WorkflowState.BLUEPRINT_READY,
            WorkflowState.REVIEWING,
            WorkflowState.DONE,
            WorkflowState.FAILED,
        }

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
        return self.answer_question("next", answer)

    def answer_question(
        self,
        selector: str,
        answer: str,
        *,
        replace: bool = False,
    ) -> WorkflowInputAction:
        """Record or replace a user answer for a selected workflow question."""
        answer = answer.strip()
        if not answer:
            return WorkflowInputAction(
                should_deliberate=False,
                message="Answer cannot be empty.",
            )

        question = self.resolve_question(selector, include_answered=replace)
        if question is None:
            return WorkflowInputAction(
                should_deliberate=False,
                message=f"No matching workflow question: {selector}",
            )
        if question.status != "open" and not replace:
            return WorkflowInputAction(
                should_deliberate=False,
                message=(
                    f"Question {question.id} is already answered. "
                    "Use /answer --replace to update it."
                ),
            )

        existing = self._decision_for_question(question.id) if replace else None
        question.status = "answered"
        if existing is not None:
            decision = existing
            decision.decision = answer
            decision.decided_by = "user"
            decision.rationale = f"Updated answer to: {question.question}"
            decision.timestamp = time.time()
            event_type = "decision_replaced"
            replaced = True
        else:
            decision = DecisionRecord(
                id=f"dec-{len(self.session.decisions) + 1:03d}",
                question_id=question.id,
                decision=answer,
                decided_by="user",
                rationale=f"Answer to: {question.question}",
            )
            self.session.decisions.append(decision)
            event_type = "decision_recorded"
            replaced = False

        self.session.updated_at = time.time()
        self._persist(
            event_type,
            {
                "decision_id": decision.id,
                "question_id": question.id,
                "decision": answer,
                "replaced": replaced,
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
                replaced_decision=replaced,
            )

        self.set_state(WorkflowState.DELIBERATING, reason="user decision answered")
        return WorkflowInputAction(
            should_deliberate=True,
            prompt=self._build_decision_continuation_prompt(decision),
            decision_record=decision,
            replaced_decision=replaced,
        )

    def answer_question_option(
        self,
        option_selector: str,
        *,
        question_selector: str = "next",
        replace: bool = False,
    ) -> WorkflowInputAction:
        """Record a numbered option for a selected workflow question."""
        question = self.resolve_question(
            question_selector,
            include_answered=replace,
        )
        if question is None:
            return WorkflowInputAction(
                should_deliberate=False,
                message=f"No matching workflow question: {question_selector}",
            )
        if not option_selector.isdigit():
            return WorkflowInputAction(
                should_deliberate=False,
                message=f"Option must be a number: {option_selector}",
            )
        index = int(option_selector) - 1
        if index < 0 or index >= len(question.options):
            return WorkflowInputAction(
                should_deliberate=False,
                message=f"Question {question.id} has no option {option_selector}.",
            )
        return self.answer_question(
            question.id,
            question.options[index],
            replace=replace,
        )

    def continue_from_blueprint(
        self,
        instruction: str,
        active_agents: list[str],
    ) -> WorkflowInputAction:
        """Continue an existing blueprint workflow with additional user text."""
        instruction = instruction.strip()
        if not instruction:
            return WorkflowInputAction(
                should_deliberate=False,
                message="Instruction cannot be empty.",
            )
        if self.session.blueprint is None:
            return self.start(instruction, active_agents)

        followup_action = classify_blueprint_followup_action(instruction)
        if followup_action == "execute":
            return self.enable_execution_for_current_blueprint(instruction)
        if followup_action == "cancel":
            return WorkflowInputAction(
                should_deliberate=False,
                message="Workflow action cancelled.",
            )
        if followup_action == "new":
            return self.start(instruction, active_agents)

        if active_agents:
            self.session.active_agents = list(active_agents)
        source_state = self.session.state
        self.set_state(
            WorkflowState.DELIBERATING,
            reason="user continued from existing blueprint",
        )
        self._persist(
            "workflow_continued",
            {
                "instruction": instruction,
                "source_state": source_state.value,
            },
        )
        return WorkflowInputAction(
            should_deliberate=True,
            prompt=self._build_blueprint_continuation_prompt(instruction),
        )

    def enable_execution_for_current_blueprint(
        self,
        instruction: str = "",
    ) -> WorkflowInputAction:
        """Regenerate current blueprint packages as executable work packages."""
        if self.session.blueprint is None:
            return WorkflowInputAction(
                should_deliberate=False,
                message="No approved blueprint is available to execute.",
            )
        if not self.session.active_agents:
            return WorkflowInputAction(
                should_deliberate=False,
                message="No active agents are attached to this workflow.",
            )
        if self.session.target_workspace is None:
            return WorkflowInputAction(
                should_deliberate=False,
                target_workspace_required=True,
                message="Target workspace is required before implementation.",
            )

        instruction = instruction.strip()
        blueprint_path = self._freeze_current_blueprint()
        if instruction:
            self.session.decisions.append(
                DecisionRecord(
                    id=self._next_decision_id(),
                    decision=instruction,
                    decided_by="user",
                    rationale="Execution instruction from session input.",
                )
            )

        self.session.work_packages = self.decomposer.decompose(
            self.session.blueprint,
            self.session.active_agents,
            requires_execution=True,
        )
        self.session.execution_results = []
        self.session.subtask_results = []
        self.session.review_packages = []
        self.session.review_results = []
        self.session.updated_at = time.time()
        self._persist(
            "execution_enabled",
            {
                "instruction": instruction,
                "blueprint_path": str(blueprint_path) if blueprint_path else "",
                "work_packages": [package.id for package in self.session.work_packages],
            },
        )
        self.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="current blueprint marked executable",
        )
        return WorkflowInputAction(
            should_deliberate=False,
            execution_requested=True,
            message="Current blueprint work packages are ready for execution.",
        )

    def _freeze_current_blueprint(self) -> Path | None:
        """Persist the approved blueprint as an immutable execution artifact."""
        if self.session.blueprint is None:
            return None
        artifact_dir = self.state_dir / "workflow" / "blueprints"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{self.session.id}.json"
        if artifact_path.exists():
            return artifact_path
        payload = {
            "workflow_id": self.session.id,
            "goal": self.session.goal,
            "frozen_at": time.time(),
            "blueprint": self.session.blueprint.to_dict(),
        }
        artifact_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return artifact_path

    def resolve_question(
        self,
        selector: str,
        *,
        include_answered: bool = False,
    ) -> OpenQuestion | None:
        """Resolve a question id, 1-based index, or ``next`` selector."""
        selector = selector.strip()
        if not selector:
            return None

        normalized = selector.lower()
        open_questions = self.pending_questions
        questions = self.session.pending_questions if include_answered else open_questions

        if normalized in {"next", "first"}:
            return open_questions[0] if open_questions else None

        if normalized.isdigit():
            index = int(normalized) - 1
            if 0 <= index < len(questions):
                return questions[index]
            return None

        if include_answered and normalized.startswith("dec-"):
            decision = next(
                (item for item in self.session.decisions if item.id.lower() == normalized),
                None,
            )
            if decision and decision.question_id:
                normalized = decision.question_id.lower()

        return next(
            (question for question in questions if question.id.lower() == normalized),
            None,
        )

    def _decision_for_question(self, question_id: str) -> DecisionRecord | None:
        """Return the existing decision attached to a question."""
        return next(
            (
                decision
                for decision in self.session.decisions
                if decision.question_id == question_id
            ),
            None,
        )

    def _next_decision_id(self) -> str:
        return f"dec-{len(self.session.decisions) + 1:03d}"

    def set_target_workspace(
        self,
        path: Path,
        *,
        control_repo_confirmed: bool = False,
    ) -> None:
        """Persist the workspace where provider implementation may write files."""
        resolved = path.expanduser().resolve()
        self.session.target_workspace = resolved
        self.session.control_repo_target_confirmed = control_repo_confirmed
        self.session.updated_at = time.time()
        self._persist(
            "target_workspace_selected",
            {
                "target_workspace": str(resolved),
                "control_repo_target_confirmed": control_repo_confirmed,
            },
        )

    def clear_target_workspace(self) -> None:
        """Clear the selected implementation workspace."""
        self.session.target_workspace = None
        self.session.control_repo_target_confirmed = False
        self.session.updated_at = time.time()
        self._persist("target_workspace_cleared", {})

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
                self.session.blueprint = Blueprint.from_dict(blueprint)
                self.session.work_packages = self.decomposer.decompose(
                    self.session.blueprint,
                    self.session.active_agents,
                    requires_execution=self._requires_execution(result),
                )
                self.session.execution_results = []
                self.session.subtask_results = []
                self.session.review_packages = []
                self.session.review_results = []
                self.set_state(
                    WorkflowState.BLUEPRINT_READY,
                    reason="structured blueprint reached consensus",
                )
                return

        if result.has_consensus:
            summary = result.consensus.summary if result.consensus else ""
            self.session.blueprint = Blueprint(
                title="Consensus Blueprint",
                summary=summary,
                acceptance_criteria=[summary] if summary else [],
            )
            self.session.work_packages = []
            self.session.execution_results = []
            self.session.subtask_results = []
            self.session.review_packages = []
            self.session.review_results = []
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
            question.id = self._unique_question_id(question.id)
            self.session.pending_questions.append(question)
            existing.add(normalized)
            added = True
        return added or saw_valid_question

    @staticmethod
    def _normalize_question(question: str) -> str:
        return " ".join(question.strip().lower().split())

    def _unique_question_id(self, question_id: str) -> str:
        """Return a question id that does not collide with session history."""
        base = question_id.strip() or "oq"
        existing = {question.id for question in self.session.pending_questions}
        existing.update(
            decision.question_id for decision in self.session.decisions if decision.question_id
        )
        if base not in existing:
            return base

        index = 2
        while f"{base}-{index}" in existing:
            index += 1
        return f"{base}-{index}"

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

    def pending_execution_package_ids(self) -> list[str]:
        """Return the package ids that the next execution run should dispatch."""
        run = self.session.execution_run if isinstance(self.session.execution_run, dict) else {}
        retry_packages = (
            [
                str(package_id).strip()
                for package_id in run.get("retry_packages", [])
                if str(package_id).strip()
            ]
            if str(run.get("state", "")) == "retry_requested"
            else []
        )
        if retry_packages:
            retry_id_set = set(retry_packages)
            return [
                package.id
                for package in self.session.work_packages
                if package.id in retry_id_set
                and package.requires_execution
                and package.status not in {WorkStatus.DONE, WorkStatus.NEEDS_REVIEW}
            ]

        return [
            package.id
            for package in self.session.work_packages
            if package.requires_execution
            and package.status not in {WorkStatus.DONE, WorkStatus.NEEDS_REVIEW}
        ]

    def begin_execution(self, package_ids: Iterable[str] | None = None) -> None:
        """Move the workflow into execution before dispatching work packages."""
        if not self.session.work_packages:
            return
        if self.session.target_workspace is None:
            raise RuntimeError("Target workspace is required before implementation.")
        run_id = f"exec-run-{uuid4().hex[:12]}"
        now = time.time()
        previous_run = (
            dict(self.session.execution_run)
            if isinstance(self.session.execution_run, dict)
            else {}
        )
        if package_ids is None:
            selected_ids = self.pending_execution_package_ids()
        else:
            requested = {str(package_id).strip() for package_id in package_ids}
            selected_ids = [
                package.id
                for package in self.session.work_packages
                if package.id in requested
                and package.requires_execution
                and package.status not in {WorkStatus.DONE, WorkStatus.NEEDS_REVIEW}
            ]
        work_package_ids = list(selected_ids)
        if not work_package_ids:
            return
        execution_run = {
            "run_id": run_id,
            "started_at": now,
            "heartbeat_at": now,
            "state": "running",
            "target_workspace": str(self.session.target_workspace),
            "work_packages": list(work_package_ids),
        }
        if str(previous_run.get("state", "")) == "retry_requested":
            execution_run["retry_selector"] = str(previous_run.get("retry_selector", "") or "")
            execution_run["retry_requested_at"] = previous_run.get("retry_requested_at")
            execution_run["retry_packages"] = list(previous_run.get("retry_packages", []))
        self.session.execution_run = execution_run
        self._persist(
            "execution_run_started",
            {
                "run_id": run_id,
                "target_workspace": str(self.session.target_workspace),
                "work_packages": list(work_package_ids),
            },
            timestamp=now,
        )
        self._persist(
            "implementation_requested",
            {
                "target_workspace": str(self.session.target_workspace),
                "work_packages": list(work_package_ids),
            },
        )
        self.set_state(WorkflowState.EXECUTING, reason="work package execution started")

    def record_work_package_started(
        self,
        package_id: str,
        agent_name: str = "",
        occurred_at: float | None = None,
    ) -> None:
        """Persist that one work package has started execution."""
        package = self._work_package_by_id(package_id)
        if package is None:
            return

        executor = agent_name or package.owner_agent
        package.status = WorkStatus.RUNNING
        package.current_executor = executor
        package.last_executor = executor
        self._touch_execution_run(occurred_at)
        self.session.updated_at = time.time()
        self._persist(
            "work_package_started",
            {
                "package_id": package.id,
                "agent": executor,
                "status": package.status.value,
            },
            timestamp=occurred_at,
        )

    def record_work_package_completed(
        self,
        package_id: str,
        agent_name: str = "",
        status: str = "",
        summary: str = "",
        occurred_at: float | None = None,
    ) -> None:
        """Persist that one work package has finished execution."""
        package = self._work_package_by_id(package_id)
        if package is None:
            return

        executor = agent_name or package.owner_agent
        if status:
            try:
                package.status = WorkStatus(status)
            except ValueError:
                pass
        package.current_executor = ""
        package.last_executor = executor
        self._touch_execution_run(occurred_at)
        self.session.updated_at = time.time()
        self._persist(
            "work_package_completed",
            {
                "package_id": package.id,
                "agent": executor,
                "status": package.status.value,
                "summary": summary,
            },
            timestamp=occurred_at,
        )

    def plan_parallel_groups(self) -> list[list[WorkPackage]]:
        """Preview dependency/file-safe work package groups for the current session."""
        packages_by_id = {
            package.id: package
            for package in self.session.work_packages
            if package.requires_execution
        }
        remaining = dict(packages_by_id)
        completed = {
            package.id
            for package in self.session.work_packages
            if package.status == WorkStatus.DONE
        }
        groups: list[list[WorkPackage]] = []
        policy = ParallelExecutionPolicy()

        while remaining:
            ready = [
                package
                for package in remaining.values()
                if all(
                    dep_id in completed or dep_id not in packages_by_id
                    for dep_id in package.dependencies
                )
            ]
            if not ready:
                groups.extend([package] for package in remaining.values())
                break

            ordered_ready = sorted(
                ready,
                key=lambda item: (-item.estimated_weight, item.id),
            )
            scope_by_package_id = {
                id(package): self._preview_execution_scope(package) for package in ordered_ready
            }
            package_by_scope_id = {
                id(scope): package
                for package in ordered_ready
                for scope in (scope_by_package_id[id(package)],)
            }
            scope_batches = policy.plan_batches(scope_by_package_id.values())
            batch = [
                package_by_scope_id[id(scope)]
                for scope in (scope_batches[0] if scope_batches else ())
            ]
            if not batch:
                batch.append(ordered_ready[0])
            groups.append(batch)
            for package in batch:
                completed.add(package.id)
                remaining.pop(package.id, None)

        return groups

    @staticmethod
    def _preview_execution_scope(package: WorkPackage) -> ExecutionScope:
        """Build scheduling metadata for TUI parallel-group previews."""
        return ExecutionScope(
            agent_name=package.owner_agent,
            authority=ExecutionAuthority.PROVIDER_MANAGED,
            access=InvocationAccess.WORKSPACE_WRITE,
            workspace_id="workflow-preview",
            file_ownership=frozenset(
                item.strip() for item in package.expected_files if item.strip()
            ),
            parallelizable=package.parallelizable,
            risk=package.risk,
            parallel_group=package.parallel_group,
        )

    def record_execution_batch_planned(
        self,
        batches: list[list[str]],
        notices: list[dict[str, object]] | None = None,
        occurred_at: float | None = None,
    ) -> None:
        """Persist execution scheduling batches and policy notices."""
        self._touch_execution_run(occurred_at)
        self.session.updated_at = time.time()
        self._persist(
            "execution_batch_planned",
            {
                "batches": batches,
                "notices": notices or [],
            },
            timestamp=occurred_at,
        )

    def record_execution_results(
        self,
        results: list[ExecutionResult],
        *,
        finalize: bool = True,
        emit_events: bool = True,
    ) -> None:
        """Persist execution results and derive the next workflow state."""
        if not results:
            return

        for result in results:
            self._record_execution_result(result, emit_event=emit_events)

        if finalize:
            self._finalize_execution_state()

    def _record_execution_result(
        self,
        result: ExecutionResult,
        *,
        emit_event: bool,
    ) -> None:
        """Upsert one execution result without finalizing the workflow."""
        package = self._work_package_by_id(result.package_id)
        if package:
            package.status = result.status
            package.current_executor = ""
            package.last_executor = result.agent_name or package.last_executor

        existing_by_package = {item.package_id: item for item in self.session.execution_results}
        existing_by_package[result.package_id] = result

        for decision in result.decisions_made:
            if not any(existing.id == decision.id for existing in self.session.decisions):
                self.session.decisions.append(decision)
        for subtask in result.subtasks:
            self._upsert_subtask_result(subtask)

        ordered_package_ids = [package.id for package in self.session.work_packages]
        self.session.execution_results = [
            existing_by_package[package_id]
            for package_id in ordered_package_ids
            if package_id in existing_by_package
        ]
        ordered_package_id_set = set(ordered_package_ids)
        extras = [
            result
            for package_id, result in existing_by_package.items()
            if package_id not in ordered_package_id_set
        ]
        self.session.execution_results.extend(extras)
        self.session.updated_at = time.time()

        if emit_event:
            self._persist(
                "execution_result_recorded",
                {
                    "package_id": result.package_id,
                    "agent": result.agent_name,
                    "status": result.status.value,
                },
            )
        else:
            self.save()

    def _finalize_execution_state(self) -> None:
        """Derive the workflow state after current execution progress."""

        executable = [
            package for package in self.session.work_packages if package.requires_execution
        ]
        if any(package.status == WorkStatus.FAILED for package in executable):
            self._finish_execution_run("failed")
            self.set_state(WorkflowState.FAILED, reason="work package execution failed")
            return
        if any(
            package.status in {WorkStatus.BLOCKED, WorkStatus.WAITING_ON_DECISION}
            for package in executable
        ):
            self._finish_execution_run("blocked")
            self.set_state(
                WorkflowState.NEEDS_USER_DECISION,
                reason="work package execution is blocked",
            )
            return
        if executable and all(
            package.status in {WorkStatus.DONE, WorkStatus.NEEDS_REVIEW} for package in executable
        ):
            self._finish_execution_run("completed")
            self._plan_review_packages()
            self.set_state(
                WorkflowState.REVIEWING,
                reason="all work packages completed",
            )
            return
        self.set_state(
            WorkflowState.EXECUTING,
            reason="work package execution still in progress",
        )

    def ensure_review_packages(self) -> list[ReviewPackage]:
        """Ensure completed execution has review packages planned."""
        if not self.session.review_packages and self.session.work_packages:
            self._plan_review_packages()
            self.session.updated_at = time.time()
            self._persist(
                "review_packages_planned",
                {
                    "review_packages": [
                        item.get("id", "") for item in self.session.review_packages
                    ],
                },
            )
        return self.review_packages_for_request("wp")

    def review_packages_for_request(
        self,
        selector: str = "wp",
        package_ids: Iterable[str] = (),
    ) -> list[ReviewPackage]:
        """Return review packages selected by a /review request."""
        normalized = (selector or "wp").strip().lower()
        requested = {
            str(package_id).strip()
            for package_id in package_ids
            if str(package_id).strip()
        }
        explicit = bool(requested)
        if normalized in {"all", "wp", "work-package", "work_packages"}:
            scope = "work_package"
        else:
            scope = normalized

        reviews: list[ReviewPackage] = []
        for item in self.session.review_packages:
            if not isinstance(item, dict):
                continue
            try:
                review = ReviewPackage.from_dict(item)
            except (TypeError, ValueError):
                continue
            if review.scope == "final" or review.package_id == FINAL_REVIEW_PACKAGE_ID:
                continue
            if scope not in {"work_package", "custom"}:
                continue
            if requested and review.package_id not in requested:
                continue
            if not explicit and self._latest_review_is_approved(review.package_id):
                continue
            reviews.append(review)
        return reviews

    def record_review_results(
        self,
        results: Iterable[ReviewResult],
        *,
        finalize: bool = True,
    ) -> None:
        """Persist review results and update workflow/package state."""
        review_results = list(results)
        if not review_results:
            return
        for result in review_results:
            self._record_review_result(result)
        if finalize:
            self._finalize_review_state(review_results)

    def prepare_review_repairs(
        self,
        results: Iterable[ReviewResult],
    ) -> tuple[str, ...]:
        """Queue packages with requested review changes for another execution pass."""
        selected: list[str] = []
        for result in results:
            if result.scope == "final" or result.package_id == FINAL_REVIEW_PACKAGE_ID:
                continue
            if result.status != ReviewStatus.CHANGES_REQUESTED:
                continue
            package = self._work_package_by_id(result.package_id)
            if package is None or not package.requires_execution:
                continue
            previous_status = package.status.value
            package.status = WorkStatus.PENDING
            package.current_executor = ""
            if package.id not in selected:
                selected.append(package.id)
            self._persist(
                "work_package_repair_requested",
                {
                    "package_id": package.id,
                    "previous_status": previous_status,
                    "review_package_id": result.review_package_id,
                    "reviewer": result.reviewer_agent,
                    "target": result.target_agent,
                    "required_changes": list(result.required_changes),
                    "executor": package.last_executor or package.owner_agent,
                },
            )

        if not selected:
            return ()

        run = dict(self.session.execution_run) if isinstance(self.session.execution_run, dict) else {}
        run.setdefault("run_id", f"exec-run-{uuid4().hex[:12]}")
        run.setdefault("target_workspace", str(self.session.target_workspace or ""))
        run["state"] = "retry_requested"
        run["retry_requested_at"] = time.time()
        run["retry_selector"] = "review-repair"
        run["retry_packages"] = list(selected)
        self.session.execution_run = run
        self.session.updated_at = time.time()
        self._persist(
            "execution_recovery_action",
            {
                "action": "review_repair",
                "packages": list(selected),
                "target_workspace": str(self.session.target_workspace or ""),
            },
        )
        self.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="review changes queued for repair",
        )
        return tuple(selected)

    def _record_review_result(self, result: ReviewResult) -> None:
        existing_by_id = {
            str(item.get("review_package_id", "")): dict(item)
            for item in self.session.review_results
            if isinstance(item, dict)
        }
        existing_by_id[result.review_package_id] = result.to_dict()
        self.session.review_results = list(existing_by_id.values())
        self._apply_review_result_to_package(result)
        self.session.updated_at = time.time()
        self._persist(
            "review_result_recorded",
            {
                "review_package_id": result.review_package_id,
                "package_id": result.package_id,
                "reviewer": result.reviewer_agent,
                "target": result.target_agent,
                "status": result.status.value,
                "severity": result.severity,
                "scope": result.scope,
            },
        )

    def _apply_review_result_to_package(self, result: ReviewResult) -> None:
        if result.scope == "final" or result.package_id == FINAL_REVIEW_PACKAGE_ID:
            return
        package = self._work_package_by_id(result.package_id)
        if package is None:
            return
        if result.status == ReviewStatus.APPROVED:
            if package.status == WorkStatus.NEEDS_REVIEW:
                package.status = WorkStatus.DONE
            return
        if result.status == ReviewStatus.CHANGES_REQUESTED:
            package.status = WorkStatus.NEEDS_REVIEW
            for change in result.required_changes:
                note = f"review {result.review_package_id}: {change}"
                if note not in package.repair_notes:
                    package.repair_notes.append(note)
            return
        if result.status == ReviewStatus.BLOCKED:
            package.status = WorkStatus.BLOCKED
            return
        if result.status == ReviewStatus.FAILED:
            package.status = WorkStatus.FAILED

    def _finalize_review_state(self, latest_results: list[ReviewResult]) -> None:
        final_results = [
            result
            for result in latest_results
            if result.scope == "final" or result.package_id == FINAL_REVIEW_PACKAGE_ID
        ]
        if final_results:
            final = final_results[-1]
            if final.status == ReviewStatus.APPROVED:
                self.set_state(WorkflowState.DONE, reason="final review approved")
            elif final.status == ReviewStatus.CHANGES_REQUESTED:
                self.set_state(WorkflowState.REVIEWING, reason="final review requested changes")
            elif final.status == ReviewStatus.BLOCKED:
                self.set_state(WorkflowState.NEEDS_USER_DECISION, reason="final review blocked")
            else:
                self.set_state(WorkflowState.FAILED, reason="final review failed")
            return

        if any(result.status == ReviewStatus.FAILED for result in latest_results):
            self.set_state(WorkflowState.FAILED, reason="work package review failed")
            return
        if any(result.status == ReviewStatus.BLOCKED for result in latest_results):
            self.set_state(WorkflowState.NEEDS_USER_DECISION, reason="work package review blocked")
            return
        if any(result.status == ReviewStatus.CHANGES_REQUESTED for result in latest_results):
            self.set_state(WorkflowState.REVIEWING, reason="work package review requested changes")
            return
        self.set_state(WorkflowState.REVIEWING, reason="work package review completed")

    def _latest_review_is_approved(self, package_id: str) -> bool:
        for result in reversed(self._review_results()):
            if result.package_id == package_id and result.scope != "final":
                return result.status == ReviewStatus.APPROVED
        return False

    def detect_interrupted_execution(
        self,
        *,
        worker_running: bool = False,
        reason: str = "process_lost",
    ) -> dict[str, Any] | None:
        """Mark and return stale execution recovery metadata."""
        if worker_running:
            return None
        if self.session.state != WorkflowState.EXECUTING:
            return None
        run = self.session.execution_run
        run_state = str(run.get("state", "")) if isinstance(run, dict) else ""
        running_packages = self._packages_with_status(WorkStatus.RUNNING)
        if run_state == "completed":
            return None
        if run_state not in {"running", "interrupted"} and not running_packages:
            return None
        if run_state != "interrupted":
            now = time.time()
            run = dict(run) if isinstance(run, dict) else {}
            run.setdefault("run_id", f"exec-run-{uuid4().hex[:12]}")
            run.setdefault("target_workspace", str(self.session.target_workspace or ""))
            run["state"] = "interrupted"
            run["interrupted_reason"] = reason
            run["interrupted_at"] = now
            run["running_packages"] = [package.id for package in running_packages]
            self.session.execution_run = run
            self.session.updated_at = now
            summary = self.execution_recovery_summary()
            self._persist(
                "execution_interrupted_detected",
                {
                    "run_id": run.get("run_id", ""),
                    "running_packages": run.get("running_packages", []),
                    "last_event_at": summary.get("last_event_at") if summary else None,
                    "reason": reason,
                },
                timestamp=now,
            )
            return summary
        return self.execution_recovery_summary()

    def execution_recovery_summary(self) -> dict[str, Any] | None:
        """Return a serializable execution recovery summary when applicable."""
        run = self.session.execution_run
        if not isinstance(run, dict) or not run:
            return None
        run_state = str(run.get("state", "") or "")
        if run_state not in {"running", "interrupted", "aborted"}:
            return None
        running_packages = self._packages_with_status(WorkStatus.RUNNING)
        if run_state == "running" and self.session.state != WorkflowState.EXECUTING:
            return None
        retry_candidates = [
            package.id
            for package in self.session.work_packages
            if package.requires_execution
            and package.status in {WorkStatus.RUNNING, WorkStatus.BLOCKED, WorkStatus.FAILED}
        ]
        done_packages = [
            package.id
            for package in self.session.work_packages
            if package.requires_execution and package.status == WorkStatus.DONE
        ]
        last_event = self._last_workflow_event()
        return {
            "run_id": str(run.get("run_id", "")),
            "state": run_state,
            "target_workspace": str(
                run.get("target_workspace") or self.session.target_workspace or ""
            ),
            "started_at": run.get("started_at"),
            "heartbeat_at": run.get("heartbeat_at"),
            "interrupted_reason": str(run.get("interrupted_reason", "") or ""),
            "running_packages": [package.id for package in running_packages],
            "done_packages": done_packages,
            "retry_candidates": retry_candidates,
            "last_event_at": last_event.get("timestamp") if last_event else None,
            "last_event": str(last_event.get("event", "")) if last_event else "",
        }

    def build_execution_retry_plan(
        self,
        selector: str = "all",
        package_ids: Iterable[str] = (),
    ) -> ExecutionRetryPlan:
        """Build a non-destructive retry plan for failed/blocked/stale packages."""
        normalized_selector = self._normalize_execution_retry_selector(selector, package_ids)
        requested = tuple(
            str(package_id).strip() for package_id in package_ids if str(package_id).strip()
        )
        summary = self.detect_interrupted_execution(worker_running=False)
        if summary is None:
            summary = self.execution_recovery_summary()
        interrupted_ids = {
            str(package_id)
            for package_id in ((summary or {}).get("running_packages", []) if summary else [])
        }

        selected: list[str] = []
        skipped: list[RetrySkip] = []
        if normalized_selector == "custom":
            for package_id in requested:
                package = self._work_package_by_id(package_id)
                if package is None:
                    skipped.append(RetrySkip(package_id, "missing", "package not found"))
                    continue
                reason = self._execution_retry_disabled_reason(package, interrupted_ids)
                if reason:
                    skipped.append(RetrySkip(package.id, package.status.value, reason))
                    continue
                if package.id not in selected:
                    selected.append(package.id)
        else:
            for package in self.session.work_packages:
                if not self._matches_execution_retry_selector(
                    package,
                    normalized_selector,
                    interrupted_ids,
                ):
                    continue
                reason = self._execution_retry_disabled_reason(package, interrupted_ids)
                if reason:
                    skipped.append(RetrySkip(package.id, package.status.value, reason))
                    continue
                selected.append(package.id)

        return ExecutionRetryPlan(
            selector=normalized_selector,
            requested=requested,
            selected=tuple(selected),
            skipped=tuple(skipped),
            target_workspace=self.session.target_workspace,
        )

    def prepare_execution_retry(
        self,
        selector: str = "all",
        package_ids: Iterable[str] = (),
    ) -> ExecutionRetryPlan:
        """Mark selected retry packages pending without deleting prior results."""
        plan = self.build_execution_retry_plan(selector=selector, package_ids=package_ids)
        candidates = set(plan.selected)
        if not candidates:
            return plan

        summary = self.execution_recovery_summary()
        stale_running_ids = {
            str(package_id)
            for package_id in ((summary or {}).get("running_packages", []) if summary else [])
        }
        for package in self.session.work_packages:
            if package.id in candidates:
                previous_status = package.status.value
                package.status = WorkStatus.PENDING
                package.current_executor = ""
                self._persist(
                    "work_package_retry_requested",
                    {
                        "package_id": package.id,
                        "previous_status": previous_status,
                        "agent": package.owner_agent,
                        "selector": plan.selector,
                    },
                )
                continue
            if package.id in stale_running_ids and package.status == WorkStatus.RUNNING:
                previous_status = package.status.value
                package.status = WorkStatus.BLOCKED
                package.current_executor = ""
                self._persist(
                    "work_package_retry_skipped",
                    {
                        "package_id": package.id,
                        "previous_status": previous_status,
                        "status": package.status.value,
                        "reason": "stale running package was not selected",
                    },
                )

        run = dict(self.session.execution_run) if isinstance(self.session.execution_run, dict) else {}
        run.setdefault("run_id", f"exec-run-{uuid4().hex[:12]}")
        run.setdefault("target_workspace", str(self.session.target_workspace or ""))
        run["state"] = "retry_requested"
        run["retry_requested_at"] = time.time()
        run["retry_selector"] = plan.selector
        run["retry_packages"] = list(plan.selected)
        self.session.execution_run = run
        self.session.updated_at = time.time()
        self._persist(
            "execution_recovery_action",
            {
                "action": "retry",
                "selector": plan.selector,
                "packages": list(plan.selected),
                "target_workspace": str(self.session.target_workspace or ""),
            },
        )
        self.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="work packages queued for retry",
        )
        return plan

    def retry_interrupted_execution(self) -> dict[str, Any] | None:
        """Prepare interrupted/failed packages for explicit user retry."""
        summary = self.detect_interrupted_execution(worker_running=False)
        if summary is None:
            summary = self.execution_recovery_summary()
        if summary is None:
            return None
        if summary.get("retry_candidates"):
            self.prepare_execution_retry("all")
        return summary

    @staticmethod
    def _normalize_execution_retry_selector(
        selector: str,
        package_ids: Iterable[str],
    ) -> str:
        normalized = selector.strip().lower() or "all"
        if normalized in {"all", "failed", "blocked", "interrupted", "custom"}:
            return normalized
        if any(str(package_id).strip() for package_id in package_ids):
            return "custom"
        return "custom"

    @staticmethod
    def _execution_retry_disabled_reason(
        package: WorkPackage,
        interrupted_ids: set[str],
    ) -> str:
        if not package.requires_execution:
            return "does not require execution"
        if package.status == WorkStatus.DONE:
            return "already done"
        if package.status == WorkStatus.NEEDS_REVIEW:
            return "already needs review"
        if package.status not in {WorkStatus.RUNNING, WorkStatus.FAILED, WorkStatus.BLOCKED}:
            return f"status is {package.status.value}"
        if (
            package.status == WorkStatus.RUNNING
            and interrupted_ids
            and package.id not in interrupted_ids
        ):
            return "running package is not part of the interrupted run"
        return ""

    @staticmethod
    def _matches_execution_retry_selector(
        package: WorkPackage,
        selector: str,
        interrupted_ids: set[str],
    ) -> bool:
        if selector == "all":
            return package.status in {WorkStatus.RUNNING, WorkStatus.FAILED, WorkStatus.BLOCKED}
        if selector == "failed":
            return package.status == WorkStatus.FAILED
        if selector == "blocked":
            return package.status == WorkStatus.BLOCKED
        if selector == "interrupted":
            return package.id in interrupted_ids or (
                not interrupted_ids and package.status == WorkStatus.RUNNING
            )
        return False

    def mark_interrupted_execution(self) -> dict[str, Any] | None:
        """Turn stale running packages into blocked work that needs user review."""
        summary = self.detect_interrupted_execution(worker_running=False)
        if summary is None:
            summary = self.execution_recovery_summary()
        if summary is None:
            return None
        running_ids = set(summary.get("running_packages", []))
        for package in self.session.work_packages:
            if package.id in running_ids:
                package.status = WorkStatus.BLOCKED
                package.current_executor = ""
        self._persist_recovery_action("mark_interrupted", sorted(running_ids))
        self.set_state(WorkflowState.NEEDS_USER_DECISION, reason="execution marked interrupted")
        return self.execution_recovery_summary()

    def abort_interrupted_execution(self) -> dict[str, Any] | None:
        """Abort a stale execution and require an explicit user decision."""
        summary = self.detect_interrupted_execution(worker_running=False)
        if summary is None:
            summary = self.execution_recovery_summary()
        if summary is None:
            return None
        candidates = set(summary.get("retry_candidates", []))
        for package in self.session.work_packages:
            if package.id in candidates and package.status == WorkStatus.RUNNING:
                package.status = WorkStatus.BLOCKED
                package.current_executor = ""
        run = dict(self.session.execution_run)
        run["state"] = "aborted"
        run["aborted_at"] = time.time()
        self.session.execution_run = run
        self._persist_recovery_action("abort_execution", sorted(candidates))
        self.set_state(WorkflowState.NEEDS_USER_DECISION, reason="execution aborted")
        return self.execution_recovery_summary()

    def _touch_execution_run(self, occurred_at: float | None = None) -> None:
        run = self.session.execution_run
        if not isinstance(run, dict) or not run:
            return
        if str(run.get("state", "")) != "running":
            return
        run["heartbeat_at"] = occurred_at if occurred_at is not None else time.time()
        self.session.execution_run = run

    def _finish_execution_run(self, outcome: str) -> None:
        run = self.session.execution_run
        if not isinstance(run, dict) or not run:
            return
        if str(run.get("state", "")) == "interrupted":
            return
        run["state"] = "completed"
        run["outcome"] = outcome
        run["completed_at"] = time.time()
        self.session.execution_run = run

    def _persist_recovery_action(self, action: str, packages: list[str]) -> None:
        run = dict(self.session.execution_run)
        run["last_recovery_action"] = action
        run["last_recovery_action_at"] = time.time()
        self.session.execution_run = run
        self.session.updated_at = time.time()
        self._persist(
            "execution_recovery_action",
            {
                "action": action,
                "packages": list(packages),
                "target_workspace": str(self.session.target_workspace or ""),
            },
        )

    def _packages_with_status(self, status: WorkStatus) -> list[WorkPackage]:
        return [
            package
            for package in self.session.work_packages
            if package.requires_execution and package.status == status
        ]

    def _last_workflow_event(self) -> dict[str, Any] | None:
        events = [
            event
            for event in self.persistence.load_events()
            if str(event.get("workflow_id", "")) == self.session.id
        ]
        return events[-1] if events else None

    def _work_package_by_id(self, package_id: str) -> WorkPackage | None:
        return next(
            (package for package in self.session.work_packages if package.id == package_id),
            None,
        )

    def _review_results(self) -> list[ReviewResult]:
        reviews: list[ReviewResult] = []
        for item in self.session.review_results:
            if not isinstance(item, dict):
                continue
            try:
                reviews.append(ReviewResult.from_dict(item))
            except (TypeError, ValueError):
                continue
        return reviews

    def _plan_review_packages(self) -> None:
        """Create peer review packages for completed execution results."""
        from trinity.workflow.review import PeerReviewPlanner

        planner = PeerReviewPlanner()
        reviews = planner.plan_reviews(
            self.session.work_packages,
            self.session.active_agents,
            self.session.execution_results,
        )
        self.session.review_packages = [review.to_dict() for review in reviews]
        self.session.review_results = []

    def _upsert_subtask_result(self, result: SubtaskResult) -> None:
        """Insert or replace a subtask result by id."""
        for index, existing in enumerate(self.session.subtask_results):
            if existing.id == result.id:
                self.session.subtask_results[index] = result
                return
        self.session.subtask_results.append(result)

    def render_shared_ledger(
        self,
        provider_readiness: Any = None,
        *,
        round_opinions: str = "",
        response_diagnostics: str = "",
        session_history: str = "",
    ) -> str:
        """Render the human-readable shared.md ledger from structured state."""
        from trinity.workflow.ledger import render_shared_ledger

        return render_shared_ledger(
            self.session,
            provider_readiness=provider_readiness,
            round_opinions=round_opinions,
            response_diagnostics=response_diagnostics,
            session_history=session_history,
        )

    def sync_shared_ledger(
        self,
        shared: "SharedContextEngine",
        provider_readiness: Any = None,
    ) -> None:
        """Rewrite shared.md from session.json state while preserving log sections."""
        sections = self._extract_shared_preserved_sections(shared.read())
        shared.write(
            self.render_shared_ledger(
                provider_readiness=provider_readiness,
                round_opinions=sections["round_opinions"],
                response_diagnostics=sections["response_diagnostics"],
                session_history=sections["session_history"],
            )
        )

    @classmethod
    def _extract_shared_preserved_sections(cls, content: str) -> dict[str, str]:
        """Collect freeform shared.md sections that are not source-of-truth state."""
        sections = cls._parse_markdown_sections(content)
        round_sections = [
            body
            for heading, body in sections.items()
            if heading == "round opinions" or re.fullmatch(r"round\s+\d+\s+opinions", heading)
        ]
        return {
            "round_opinions": "\n\n".join(round_sections).strip(),
            "response_diagnostics": sections.get("response diagnostics", "").strip(),
            "session_history": sections.get("session history", "").strip(),
        }

    @staticmethod
    def _parse_markdown_sections(content: str) -> dict[str, str]:
        """Parse top-level markdown ## sections by normalized heading."""
        sections: dict[str, str] = {}
        current_heading: str | None = None
        current_lines: list[str] = []

        for line in content.splitlines():
            if line.startswith("## ") and not line.startswith("### "):
                if current_heading is not None:
                    sections[current_heading] = "\n".join(current_lines).strip()
                current_heading = line[3:].strip().lower()
                current_lines = [line]
                continue
            if current_heading is not None:
                current_lines.append(line)

        if current_heading is not None:
            sections[current_heading] = "\n".join(current_lines).strip()
        return sections

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
        self.persistence.save(self.session)

    def _persist(
        self,
        event_type: str,
        data: dict,
        *,
        timestamp: float | None = None,
    ) -> None:
        self.save()
        event_timestamp = self._event_timestamp(timestamp)
        event = {
            "timestamp": event_timestamp,
            "workflow_id": self.session.id,
            "event": event_type,
            "state": self.session.state.value,
            "data": data,
        }
        self.persistence.append_event(event)

    @staticmethod
    def _event_timestamp(timestamp: float | None) -> float:
        if timestamp is None:
            return time.time()
        try:
            return float(timestamp)
        except (TypeError, ValueError):
            return time.time()

    def _load_or_create(self) -> WorkflowSession:
        session = self.persistence.load()
        if session:
            return session
        return WorkflowSession(
            id=f"wf-{uuid4().hex[:12]}",
            goal="",
            state=WorkflowState.IDLE,
        )

    def _build_decision_continuation_prompt(self, decision: DecisionRecord) -> str:
        decisions = "\n".join(f"- {item.id}: {item.decision}" for item in self.session.decisions)
        return (
            "Continue the existing workflow using the user's decision below.\n\n"
            f"Original goal:\n{self.session.goal}\n\n"
            f"Latest decision ({decision.id}):\n{decision.decision}\n\n"
            f"All decisions:\n{decisions}\n\n"
            "Update the design based on these decisions and continue deliberation."
        )

    def _build_blueprint_continuation_prompt(self, instruction: str) -> str:
        blueprint = self.session.blueprint
        blueprint_title = blueprint.title if blueprint else "(none)"
        blueprint_summary = blueprint.summary if blueprint else "(none)"
        criteria = (
            "\n".join(f"- {item}" for item in blueprint.acceptance_criteria)
            if blueprint and blueprint.acceptance_criteria
            else "- none"
        )
        decisions = (
            "\n".join(f"- {item.id}: {item.decision}" for item in self.session.decisions)
            or "- none"
        )
        return (
            "Continue the existing workflow instead of starting a new one.\n\n"
            f"Original goal:\n{self.session.goal}\n\n"
            "Current approved blueprint:\n"
            f"- Title: {blueprint_title}\n"
            f"- Summary: {blueprint_summary}\n"
            f"- Acceptance Criteria:\n{criteria}\n\n"
            f"User follow-up instruction:\n{instruction}\n\n"
            f"Recorded decisions:\n{decisions}\n\n"
            "Revise or confirm the blueprint using the user's follow-up. "
            "If the user is asking for implementation, produce an executable "
            "final blueprint and approve it. If more user input is required, "
            "raise OPEN QUESTIONS."
        )
