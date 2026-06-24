"""Execution protocol for approved workflow work packages."""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Callable
from uuid import uuid4

from trinity.agents.base import AgentWrapper
from trinity.context.shared import SharedContextEngine
from trinity.models import DeliberationMessage, ResponseStatus
from trinity.prompts.context_projection import (
    agent_context_profile,
    agent_output_contract_id,
    render_agent_output_contract,
    render_context_projection_block,
    render_operating_profile_block,
)
from trinity.prompts.contracts import EXECUTION_CONTRACT_ID
from trinity.providers.policy import (
    ExecutionAuthority,
    ExecutionScope,
    InvocationAccess,
    ParallelExecutionPolicy,
)
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.workflow.models import (
    DecisionRecord,
    ExecutionResult,
    SubtaskResult,
    WorkPackage,
    WorkStatus,
)
from trinity.workflow.lifecycle import LifecycleDecision, LifecycleGuard

logger = logging.getLogger(__name__)

EXECUTION_FALLBACK_PRIORITY: tuple[str, ...] = (
    "codex",
    "claude",
    "antigravity",
)

LEGACY_OWNER_ALIASES: dict[str, str] = {
    "gemini": "antigravity",
}

ENVIRONMENT_BLOCKER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(cargo|rustc|npm|pnpm|yarn|node|python|pytest|go|java)\b"
        r".{0,80}\b(not found|not installed|missing|unavailable|없)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(not found|not installed|missing|unavailable|없).{0,80}"
        r"\b(cargo|rustc|npm|pnpm|yarn|node|python|pytest|go|java)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(command not found|not recognized as an internal|no such file)\b",
        re.IGNORECASE,
    ),
)


class ExecutionWorkspaceError(RuntimeError):
    """Raised when provider workspace-write would violate workspace boundaries."""


class ExecutionProtocol:
    """Dispatch approved work packages to their owner agents."""

    def __init__(
        self,
        agents: dict[str, AgentWrapper],
        shared: SharedContextEngine,
        artifact_dir: Path,
        timeout: float = 300.0,
        event_callback: Callable[[TUIEvent], None] | None = None,
        lifecycle_guard: LifecycleGuard | None = None,
        rotation_callback: Callable[[str], object] | None = None,
        parallel_policy: ParallelExecutionPolicy | None = None,
        result_callback: Callable[[ExecutionResult], None] | None = None,
        target_workspace: Path | None = None,
        control_repo: Path | None = None,
        allow_control_repo_writes: bool = False,
    ):
        self.agents = agents
        self.shared = shared
        self.artifact_dir = artifact_dir
        self.timeout = timeout
        self._event_callback = event_callback
        self.lifecycle_guard = lifecycle_guard
        self._rotation_callback = rotation_callback
        self.parallel_policy = parallel_policy or ParallelExecutionPolicy()
        self.result_callback = result_callback
        self.target_workspace = target_workspace.resolve() if target_workspace else None
        self.control_repo = control_repo.resolve() if control_repo else None
        self.allow_control_repo_writes = allow_control_repo_writes

    async def run(
        self,
        work_packages: Iterable[WorkPackage],
        decisions: Iterable[DecisionRecord] = (),
        result_callback: Callable[[ExecutionResult], None] | None = None,
    ) -> list[ExecutionResult]:
        """Execute all executable work packages and return their results."""
        packages = [
            package
            for package in work_packages
            if package.requires_execution
            and package.status not in {WorkStatus.DONE, WorkStatus.NEEDS_REVIEW}
        ]
        if not packages:
            return []
        self._validate_workspace_boundary()

        on_result = result_callback or self.result_callback
        self._emit(TUIEventType.EXECUTION_START, package_count=len(packages))
        results_by_id: dict[str, ExecutionResult] = {}
        packages_by_id = {package.id: package for package in packages}
        remaining = dict(packages_by_id)

        while remaining:
            ready_packages = [
                package
                for package in remaining.values()
                if not self._blocked_dependencies(package, packages_by_id)
            ]
            if not ready_packages:
                for package in list(remaining.values()):
                    blocked_dependencies = (
                        self._blocked_dependencies(
                            package,
                            packages_by_id,
                        )
                        or package.dependencies
                        or ["dependency cycle"]
                    )
                    result = self._dependency_blocked_result(
                        package,
                        blocked_dependencies,
                    )
                    package.status = result.status
                    results_by_id[package.id] = result
                    self._record_result(result)
                    self._notify_result(result, on_result)
                    remaining.pop(package.id, None)
                break

            for ready_batch in self._plan_ready_batches(ready_packages):
                batch_results = await asyncio.gather(
                    *[self._run_ready_package(package, decisions) for package in ready_batch],
                    return_exceptions=True,
                )
                for package, item in zip(ready_batch, batch_results):
                    if isinstance(item, ExecutionResult):
                        result = item
                    else:
                        result = self._exception_result(
                            package,
                            self._new_request_id(package),
                            item,
                            WorkStatus.FAILED,
                        )
                        package.status = result.status
                    results_by_id[package.id] = result
                    self._record_result(result)
                    self._notify_result(result, on_result)
                    remaining.pop(package.id, None)

        self._emit(TUIEventType.EXECUTION_DONE, package_count=len(packages))
        return [results_by_id[package.id] for package in packages if package.id in results_by_id]

    def _validate_workspace_boundary(self) -> None:
        """Refuse provider writes without an approved implementation workspace."""
        if self.control_repo is None:
            return
        if self.target_workspace is None:
            raise ExecutionWorkspaceError(
                "Target workspace is required before provider workspace-write."
            )
        if (
            self._is_inside_control_repo(self.target_workspace)
            and not self.allow_control_repo_writes
        ):
            raise ExecutionWorkspaceError(
                "Refusing provider workspace-write in the Trinity control repo "
                "without explicit confirmation."
            )
        for agent_name, agent in self.agents.items():
            cwd = getattr(agent, "launch_cwd", None)
            if not isinstance(cwd, Path):
                continue
            if self._is_inside_control_repo(cwd.resolve()) and not self.allow_control_repo_writes:
                raise ExecutionWorkspaceError(
                    f"Refusing provider workspace-write for {agent_name} in "
                    "the Trinity control repo."
                )

    def _is_inside_control_repo(self, path: Path) -> bool:
        if self.control_repo is None:
            return False
        resolved = path.resolve()
        return resolved == self.control_repo or self.control_repo in resolved.parents

    def _plan_ready_batches(
        self,
        ready_packages: Iterable[WorkPackage],
    ) -> tuple[tuple[WorkPackage, ...], ...]:
        """Group dependency-ready packages into safe parallel batches."""
        packages = tuple(ready_packages)
        scope_by_id: dict[int, ExecutionScope] = {
            id(package): self._execution_scope_for_package(package) for package in packages
        }
        package_by_scope_id = {
            id(scope): package for package in packages for scope in (scope_by_id[id(package)],)
        }
        batch_plan = self.parallel_policy.plan(scope_by_id.values())
        scope_batches = batch_plan.batches
        self._emit_batch_plan(scope_batches, package_by_scope_id, batch_plan.notices)
        return tuple(
            tuple(package_by_scope_id[id(scope)] for scope in scope_batch)
            for scope_batch in scope_batches
        )

    def _execution_scope_for_package(self, package: WorkPackage) -> ExecutionScope:
        """Build scheduling metadata for a work package invocation."""
        agent = self.agents.get(package.owner_agent)
        cwd = getattr(agent, "launch_cwd", None) if agent is not None else None
        return ExecutionScope(
            agent_name=package.owner_agent,
            authority=ExecutionAuthority.PROVIDER_MANAGED,
            access=InvocationAccess.WORKSPACE_WRITE,
            cwd=cwd if isinstance(cwd, Path) else None,
            file_ownership=frozenset(
                item.strip() for item in package.expected_files if item.strip()
            ),
            parallelizable=package.parallelizable,
            risk=package.risk,
            parallel_group=package.parallel_group,
        )

    def _emit_batch_plan(
        self,
        scope_batches: tuple[tuple[ExecutionScope, ...], ...],
        package_by_scope_id: dict[int, WorkPackage],
        notices: tuple[object, ...],
    ) -> None:
        """Emit safe scheduling groups and conservative policy reasons."""
        batches = [
            [package_by_scope_id[id(scope)].id for scope in scope_batch]
            for scope_batch in scope_batches
        ]
        self._emit(
            TUIEventType.EXECUTION_BATCH_PLANNED,
            batches=batches,
            notices=[
                {
                    "reason": str(getattr(notice, "reason", "")),
                    "serialized_agents": list(getattr(notice, "serialized_agents", ()) or ()),
                }
                for notice in notices
                if str(getattr(notice, "reason", "")).strip()
            ],
        )

    async def _run_ready_package(
        self,
        package: WorkPackage,
        decisions: Iterable[DecisionRecord],
    ) -> ExecutionResult:
        """Run lifecycle hooks and dispatch for one dependency-ready package."""
        try:
            await self._before_work_package_lifecycle(package)
            result = await self.dispatch_package(package, decisions)
            await self._after_work_package_lifecycle(package)
        except Exception as exc:
            logger.error("[%s] execution lifecycle failed: %s", package.owner_agent, exc)
            result = self._exception_result(
                package,
                self._new_request_id(package),
                exc,
                WorkStatus.FAILED,
            )
        package.status = result.status
        return result

    @staticmethod
    def _blocked_dependencies(
        package: WorkPackage,
        packages_by_id: dict[str, WorkPackage],
    ) -> list[str]:
        """Return internal dependencies that have not reached DONE."""
        return [
            dep_id
            for dep_id in package.dependencies
            if packages_by_id.get(dep_id) and packages_by_id[dep_id].status != WorkStatus.DONE
        ]

    async def _before_work_package_lifecycle(self, package: WorkPackage) -> None:
        """Run lifecycle checks before dispatching a work package."""
        if not self.lifecycle_guard:
            return
        decision = self.lifecycle_guard.before_work_package(package, self.agents)
        await self._apply_lifecycle_decision(decision)

    async def _after_work_package_lifecycle(self, package: WorkPackage) -> None:
        """Run lifecycle checks after a work package finishes."""
        if not self.lifecycle_guard:
            return
        decision = self.lifecycle_guard.after_work_package(package, self.agents)
        await self._apply_lifecycle_decision(decision)

    async def _apply_lifecycle_decision(
        self,
        decision: LifecycleDecision,
    ) -> None:
        """Execute lifecycle recommendations that this protocol can handle."""
        if not self._rotation_callback:
            return

        for agent_name in decision.rotation_agents:
            result = self._rotation_callback(agent_name)
            if inspect.isawaitable(result):
                await result

    async def dispatch_package(
        self,
        package: WorkPackage,
        decisions: Iterable[DecisionRecord] = (),
    ) -> ExecutionResult:
        """Send one work package to its owner agent and collect the result."""
        failed_attempts: list[ExecutionResult] = []
        preferred_agent = package.last_executor or package.owner_agent
        for agent_name in self._agent_attempt_order(preferred_agent):
            agent = self.agents.get(agent_name)
            if agent is None:
                failed_attempts.append(self._missing_agent_result(package, agent_name))
                continue

            result = await self._dispatch_package_to_agent(
                package,
                agent_name,
                agent,
                decisions,
            )
            if result.status not in {WorkStatus.FAILED, WorkStatus.BLOCKED}:
                if failed_attempts:
                    result.attempt_chain = self._attempt_chain([*failed_attempts, result])
                return result
            failed_attempts.append(result)

        return self._failed_fallback_result(package, failed_attempts)

    async def _dispatch_package_to_agent(
        self,
        package: WorkPackage,
        agent_name: str,
        agent: AgentWrapper,
        decisions: Iterable[DecisionRecord],
    ) -> ExecutionResult:
        """Dispatch one package attempt to a concrete agent."""
        package.status = WorkStatus.RUNNING
        package.current_executor = agent_name
        package.last_executor = agent_name
        self._emit(
            TUIEventType.WORK_PACKAGE_STARTED,
            package_id=package.id,
            agent=agent_name,
            status=package.status.value,
            output_contract=self._agent_output_contract_id(
                agent_name,
                mode="execute",
                default=EXECUTION_CONTRACT_ID,
            ),
            context_profile=self._agent_context_profile(agent_name),
        )

        prompt = self._build_execution_prompt(
            package,
            decisions,
            execution_agent=agent_name,
        )
        request_id = self._new_request_id(package)
        wrapped_prompt = self._wrap_execution_prompt(prompt, request_id)

        try:
            message = await agent.send_and_wait(
                wrapped_prompt,
                timeout=self.timeout,
                access=InvocationAccess.WORKSPACE_WRITE,
            )
        except asyncio.TimeoutError as exc:
            return self._exception_result(
                package,
                request_id,
                exc,
                WorkStatus.FAILED,
                agent_name=agent_name,
            )
        except Exception as exc:
            logger.error("[%s] execution failed: %s", agent_name, exc)
            return self._exception_result(
                package,
                request_id,
                exc,
                WorkStatus.FAILED,
                agent_name=agent_name,
            )

        return self.collect_result(
            package,
            request_id,
            message,
            agent_name=agent_name,
        )

    def collect_result(
        self,
        package: WorkPackage,
        request_id: str,
        message: DeliberationMessage,
        agent_name: str | None = None,
    ) -> ExecutionResult:
        """Parse a package execution response into an ExecutionResult."""
        actual_agent = agent_name or package.owner_agent
        raw_content = str(message.metadata.get("raw_output") or message.content or "")
        raw_path = self._write_raw_response(
            package,
            request_id,
            raw_content,
            agent_name=actual_agent,
        )

        if self._message_failed(message):
            response_status = str(message.metadata.get("response_status") or "")
            status = (
                WorkStatus.BLOCKED
                if response_status == ResponseStatus.PERMISSION_REQUIRED.value
                else WorkStatus.FAILED
            )
            return ExecutionResult(
                package_id=package.id,
                agent_name=actual_agent,
                status=status,
                summary=message.content or "Agent response failed.",
                blockers=(
                    [message.content or "Provider permission approval is required."]
                    if status == WorkStatus.BLOCKED
                    else []
                ),
                raw_response_path=raw_path,
            )

        parsed = self._parse_execution_response(message.content)
        blockers = parsed["blockers"]
        status = self._status_from_blockers(blockers)
        decisions = [
            DecisionRecord(
                id=f"{package.id.lower()}-dec-{idx:03d}",
                decision=decision,
                decided_by=actual_agent,
                rationale=f"Execution decision from {package.id}.",
            )
            for idx, decision in enumerate(parsed["decisions_made"], start=1)
        ]
        return ExecutionResult(
            package_id=package.id,
            agent_name=actual_agent,
            status=status,
            summary=parsed["summary"],
            files_changed=parsed["files_changed"],
            decisions_made=decisions,
            blockers=blockers,
            follow_up=parsed["follow_up"],
            subtasks=self._parse_subtasks(parsed["subtask_lines"], package),
            raw_response_path=raw_path,
        )

    def review_results(self, results: Iterable[ExecutionResult]) -> WorkStatus:
        """Return aggregate execution status for completed results."""
        statuses = [result.status for result in results]
        if any(status == WorkStatus.FAILED for status in statuses):
            return WorkStatus.FAILED
        if any(status == WorkStatus.BLOCKED for status in statuses):
            return WorkStatus.BLOCKED
        if statuses and all(
            status in {WorkStatus.DONE, WorkStatus.NEEDS_REVIEW} for status in statuses
        ):
            return WorkStatus.DONE
        return WorkStatus.PENDING

    def _record_result(self, result: ExecutionResult) -> None:
        self.shared.append_task_result(
            package_id=result.package_id,
            agent=result.agent_name,
            status=result.status.value,
            summary=result.summary,
            files_changed=result.files_changed,
            decisions_made=[decision.decision for decision in result.decisions_made],
            blockers=result.blockers,
            follow_up=result.follow_up,
            raw_response_path=result.raw_response_path,
        )
        for subtask in result.subtasks:
            self.shared.append_subtask_result(
                subtask_id=subtask.id,
                parent_package_id=subtask.parent_package_id,
                parent_agent=subtask.parent_agent,
                delegated_to=subtask.delegated_to,
                objective=subtask.objective,
                result_summary=subtask.result_summary,
                status=subtask.status.value,
                decisions_made=subtask.decisions_made,
                files_changed=subtask.files_changed,
                unresolved_issues=subtask.unresolved_issues,
            )
        self._emit(
            TUIEventType.WORK_PACKAGE_COMPLETED,
            package_id=result.package_id,
            agent=result.agent_name,
            status=result.status.value,
            summary=result.summary,
            output_contract=self._agent_output_contract_id(
                result.agent_name,
                mode="execute",
                default=EXECUTION_CONTRACT_ID,
            ),
            context_profile=self._agent_context_profile(result.agent_name),
            attempt_chain=list(result.attempt_chain),
            raw_response_path=(
                str(result.raw_response_path) if result.raw_response_path else ""
            ),
        )

    @staticmethod
    def _notify_result(
        result: ExecutionResult,
        callback: Callable[[ExecutionResult], None] | None,
    ) -> None:
        if callback:
            callback(result)

    def _missing_agent_result(
        self,
        package: WorkPackage,
        agent_name: str | None = None,
    ) -> ExecutionResult:
        attempted_agent = agent_name or package.owner_agent
        return ExecutionResult(
            package_id=package.id,
            agent_name=attempted_agent,
            status=WorkStatus.FAILED,
            summary=f"Execution agent '{attempted_agent}' is not available.",
            blockers=[f"Execution agent '{attempted_agent}' is not available."],
        )

    def _dependency_blocked_result(
        self,
        package: WorkPackage,
        dependencies: list[str],
    ) -> ExecutionResult:
        return ExecutionResult(
            package_id=package.id,
            agent_name=package.owner_agent,
            status=WorkStatus.BLOCKED,
            summary="Package dependencies have not completed.",
            blockers=["Dependencies not completed: " + ", ".join(sorted(dependencies))],
        )

    def _exception_result(
        self,
        package: WorkPackage,
        request_id: str,
        exc: BaseException,
        status: WorkStatus,
        agent_name: str | None = None,
    ) -> ExecutionResult:
        actual_agent = agent_name or package.owner_agent
        raw_path = self._write_raw_response(
            package,
            request_id,
            f"[Error: {exc}]",
            agent_name=actual_agent,
        )
        return ExecutionResult(
            package_id=package.id,
            agent_name=actual_agent,
            status=status,
            summary=f"Execution failed: {exc}",
            blockers=[str(exc)],
            raw_response_path=raw_path,
        )

    def _failed_fallback_result(
        self,
        package: WorkPackage,
        attempts: list[ExecutionResult],
    ) -> ExecutionResult:
        """Return a single failed result after all available attempts failed."""
        if not attempts:
            return self._missing_agent_result(package)
        if len(attempts) == 1:
            return attempts[0]

        aggregate_status = (
            WorkStatus.FAILED
            if any(attempt.status == WorkStatus.FAILED for attempt in attempts)
            else WorkStatus.BLOCKED
        )
        summary = "All execution attempts failed or blocked: " + "; ".join(
            f"{attempt.agent_name}: {attempt.summary or attempt.status.value}"
            for attempt in attempts
        )
        blockers: list[str] = []
        for attempt in attempts:
            blockers.extend(attempt.blockers or [attempt.summary])
        last = attempts[-1]
        return ExecutionResult(
            package_id=package.id,
            agent_name=last.agent_name,
            status=aggregate_status,
            summary=summary,
            blockers=[item for item in blockers if item],
            raw_response_path=last.raw_response_path,
            attempt_chain=self._attempt_chain(attempts),
        )

    @classmethod
    def _attempt_chain(cls, attempts: Iterable[ExecutionResult]) -> list[dict[str, object]]:
        """Return a structured, serializable execution-attempt chain."""
        return [cls._attempt_chain_payload(attempt) for attempt in attempts]

    @staticmethod
    def _attempt_chain_payload(result: ExecutionResult) -> dict[str, object]:
        """Return one execution attempt for events, sessions, and reports."""
        return {
            "agent": result.agent_name,
            "status": result.status.value,
            "summary": result.summary,
            "blockers": list(result.blockers),
            "raw_response_path": (
                str(result.raw_response_path) if result.raw_response_path else ""
            ),
        }

    def _build_execution_prompt(
        self,
        package: WorkPackage,
        decisions: Iterable[DecisionRecord],
        *,
        execution_agent: str | None = None,
    ) -> str:
        execution_agent = execution_agent or package.owner_agent
        decisions_text = (
            "\n".join(f"- {decision.id}: {decision.decision}" for decision in decisions) or "- none"
        )
        scope = self._format_list(package.scope)
        out_of_scope = self._format_list(package.out_of_scope)
        acceptance = self._format_list(package.acceptance_criteria)
        expected_files = self._format_list(package.expected_files)
        repair_notes = self._format_list(package.repair_notes)
        shared_decisions = self.shared.read_section("Agreed Conclusion") or ""
        operating_profile = render_operating_profile_block(
            self.agents,
            execution_agent,
            mode="execute",
            heading="[Operating Profile]",
            default_output_contract=EXECUTION_CONTRACT_ID,
        )
        context_projection = self._context_projection_block(execution_agent)
        output_contract = render_agent_output_contract(
            self.agents,
            execution_agent,
            mode="execute",
            default=EXECUTION_CONTRACT_ID,
        )
        fallback_note = ""
        if execution_agent != package.owner_agent:
            fallback_note = (
                "[Fallback Assignment]\n"
                f"Original owner: {package.owner_agent}\n"
                f"Current executor: {execution_agent}\n"
                "The original owner failed or is unavailable. Complete the same "
                "work package without expanding scope.\n\n"
            )

        return (
            "[Work Package]\n"
            f"ID: {package.id}\n"
            f"Owner: {package.owner_agent}\n"
            f"Executor: {execution_agent}\n"
            f"Objective: {package.objective}\n"
            f"Title: {package.title}\n"
            f"Estimated Weight: {package.estimated_weight}\n\n"
            f"{operating_profile}"
            f"{fallback_note}"
            "Scope:\n"
            f"{scope}\n\n"
            "Out of Scope:\n"
            f"{out_of_scope}\n\n"
            "Expected Files:\n"
            f"{expected_files}\n\n"
            "[Workspace Boundary]\n"
            f"Target Workspace: {self.target_workspace or '(not configured)'}\n"
            "Only modify files required by this package. Treat Expected Files "
            "as your ownership boundary unless a blocker requires escalation. "
            "Do not switch branches, merge, commit, or push; Trinity's "
            "orchestrator owns integration.\n\n"
            "Acceptance Criteria:\n"
            f"{acceptance}\n\n"
            "Repair Notes:\n"
            f"{repair_notes}\n\n"
            "[Shared Decisions]\n"
            f"{decisions_text}\n\n"
            "[Agreed Conclusion]\n"
            f"{shared_decisions.strip() or '(none)'}\n\n"
            f"{context_projection}"
            "[Subagent Delegation Policy]\n"
            "Trinity does not directly control provider-internal subagents or "
            "tools. If you delegate to subagents/tools, you must report each "
            "delegated subtask in the ## Subtasks section with:\n"
            "- subtask id\n"
            "- subagent/tool used\n"
            "- input objective\n"
            "- output summary\n"
            "- decisions made\n"
            "- files changed\n"
            "- unresolved issues\n\n"
            "Perform this work package. When finished, report exactly in this "
            "format:\n"
            f"{output_contract}\n"
        )

    def _context_projection_block(self, agent_name: str) -> str:
        return render_context_projection_block(
            self.shared,
            self._agent_context_profile(agent_name),
            heading="[Context Projection]",
        )

    def _agent_context_profile(self, agent_name: str) -> str:
        return agent_context_profile(self.agents, agent_name)

    def _agent_output_contract_id(
        self,
        agent_name: str,
        *,
        mode: str,
        default: str,
    ) -> str:
        return agent_output_contract_id(
            self.agents,
            agent_name,
            mode=mode,
            default=default,
        )

    @staticmethod
    def _format_list(items: Iterable[str]) -> str:
        values = [str(item).strip() for item in items if str(item).strip()]
        return "\n".join(f"- {item}" for item in values) if values else "- none"

    @staticmethod
    def _parse_execution_response(content: str) -> dict[str, list[str] | str]:
        sections: dict[str, list[str]] = {}
        current = "completed"
        sections[current] = []

        for line in content.splitlines():
            heading = re.match(r"^##\s+(.+?)\s*$", line)
            if heading:
                current = heading.group(1).strip().lower()
                sections.setdefault(current, [])
                continue
            sections.setdefault(current, []).append(line)

        def _items(*names: str) -> list[str]:
            lines: list[str] = []
            for name in names:
                lines.extend(sections.get(name, []))
            return [
                re.sub(r"^\s*[-*]\s*", "", line).strip()
                for line in lines
                if _is_substantive_line(line)
            ]

        completed = _items("completed")
        summary = "\n".join(completed).strip() or content.strip()
        return {
            "summary": summary,
            "files_changed": _items("files changed", "files"),
            "decisions_made": _items("decisions made", "decisions"),
            "blockers": _items("blockers", "blocked"),
            "follow_up": _items("follow-up", "follow up", "followup"),
            "subtask_lines": list(sections.get("subtasks", [])),
        }

    @classmethod
    def _parse_subtasks(
        cls,
        lines: object,
        package: WorkPackage,
    ) -> list[SubtaskResult]:
        """Parse optional provider-internal delegation reports."""
        if not isinstance(lines, list):
            return []

        blocks = cls._split_subtask_blocks([str(line) for line in lines])
        subtasks: list[SubtaskResult] = []
        for index, (heading, block_lines) in enumerate(blocks, start=1):
            fields = cls._parse_subtask_fields(block_lines)
            delegated_to = cls._field(
                fields,
                "delegated_to",
                "delegated to",
                "subagent/tool used",
                "subagent",
                "tool",
            )
            if not delegated_to:
                continue

            subtask_id = (
                heading
                or cls._field(fields, "id", "subtask id", "subtask_id")
                or f"{package.id}-ST-{index:03d}"
            )
            status = cls._parse_work_status(cls._field(fields, "status") or WorkStatus.DONE.value)
            subtasks.append(
                SubtaskResult(
                    id=subtask_id,
                    parent_package_id=package.id,
                    parent_agent=package.owner_agent,
                    delegated_to=delegated_to,
                    objective=cls._field(
                        fields,
                        "objective",
                        "input objective",
                    ),
                    result_summary=cls._field(
                        fields,
                        "result_summary",
                        "result summary",
                        "output summary",
                        "summary",
                    ),
                    status=status,
                    decisions_made=cls._field_list(
                        fields,
                        "decisions_made",
                        "decisions made",
                        "decisions",
                    ),
                    files_changed=cls._field_list(
                        fields,
                        "files_changed",
                        "files changed",
                        "files",
                    ),
                    unresolved_issues=cls._field_list(
                        fields,
                        "unresolved_issues",
                        "unresolved issues",
                        "issues",
                    ),
                )
            )
        return subtasks

    @staticmethod
    def _split_subtask_blocks(lines: list[str]) -> list[tuple[str, list[str]]]:
        blocks: list[tuple[str, list[str]]] = []
        current_heading = ""
        current_lines: list[str] = []

        for line in lines:
            heading = re.match(r"^###\s+(.+?)\s*$", line)
            if heading:
                if current_heading or any(_is_substantive_line(item) for item in current_lines):
                    blocks.append((current_heading, current_lines))
                current_heading = heading.group(1).strip()
                current_lines = []
                continue
            current_lines.append(line)

        if current_heading or any(_is_substantive_line(item) for item in current_lines):
            blocks.append((current_heading, current_lines))
        return blocks

    @staticmethod
    def _parse_subtask_fields(lines: list[str]) -> dict[str, str]:
        fields: dict[str, str] = {}
        last_key = ""
        for line in lines:
            if not _is_substantive_line(line):
                continue
            match = re.match(r"^\s*[-*]?\s*([^:]+):\s*(.*?)\s*$", line)
            if match:
                key = _normalize_field_name(match.group(1))
                value = match.group(2).strip()
                if value:
                    fields[key] = value
                    last_key = key
                continue
            if last_key:
                fields[last_key] = "\n".join(
                    part for part in (fields[last_key], line.strip()) if part
                )
        return fields

    @staticmethod
    def _field(fields: dict[str, str], *names: str) -> str:
        for name in names:
            value = fields.get(_normalize_field_name(name), "").strip()
            if _is_substantive_line(value):
                return value
        return ""

    @classmethod
    def _field_list(cls, fields: dict[str, str], *names: str) -> list[str]:
        value = cls._field(fields, *names)
        if not value:
            return []
        parts = re.split(r"[,;\n]+", value)
        return [
            re.sub(r"^\s*[-*]\s*", "", part).strip() for part in parts if _is_substantive_line(part)
        ]

    @staticmethod
    def _parse_work_status(value: str) -> WorkStatus:
        normalized = _normalize_field_name(value)
        aliases = {
            "complete": WorkStatus.DONE,
            "completed": WorkStatus.DONE,
            "done": WorkStatus.DONE,
            "blocked": WorkStatus.BLOCKED,
            "waiting": WorkStatus.WAITING_ON_DECISION,
            "waiting_on_decision": WorkStatus.WAITING_ON_DECISION,
            "failed": WorkStatus.FAILED,
            "failure": WorkStatus.FAILED,
            "needs_review": WorkStatus.NEEDS_REVIEW,
            "review": WorkStatus.NEEDS_REVIEW,
        }
        return aliases.get(normalized, WorkStatus.DONE)

    @classmethod
    def _status_from_blockers(cls, blockers: list[str]) -> WorkStatus:
        if not blockers:
            return WorkStatus.DONE
        if cls._only_environment_verification_blockers(blockers):
            return WorkStatus.NEEDS_REVIEW
        return WorkStatus.BLOCKED

    @staticmethod
    def _only_environment_verification_blockers(blockers: list[str]) -> bool:
        substantive = [blocker.strip() for blocker in blockers if blocker.strip()]
        if not substantive:
            return False
        return all(
            any(pattern.search(blocker) for pattern in ENVIRONMENT_BLOCKER_PATTERNS)
            for blocker in substantive
        )

    @staticmethod
    def _message_failed(message: DeliberationMessage) -> bool:
        metadata = message.metadata
        response_status = metadata.get("response_status")
        if response_status and str(response_status) != "ok":
            return True
        return (
            metadata.get("error") == "timeout"
            or metadata.get("invalid_response") is True
            or metadata.get("completed") is False
        )

    def _write_raw_response(
        self,
        package: WorkPackage,
        request_id: str,
        raw_content: str,
        *,
        agent_name: str | None = None,
    ) -> Path:
        safe_package = re.sub(r"[^A-Za-z0-9_.-]+", "-", package.id).strip("-")
        safe_agent = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "-",
            agent_name or package.owner_agent,
        ).strip("-")
        safe_request = re.sub(r"[^A-Za-z0-9_.-]+", "-", request_id).strip("-")
        package_dir = self.artifact_dir / safe_package
        package_dir.mkdir(parents=True, exist_ok=True)
        path = package_dir / f"{safe_agent}-{safe_request}.raw.txt"
        path.write_text(
            str(raw_content).encode("utf-8", errors="replace").decode("utf-8"),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _new_request_id(package: WorkPackage) -> str:
        return f"exec-{package.id.lower()}-{uuid4().hex[:12]}"

    @staticmethod
    def _wrap_execution_prompt(prompt: str, request_id: str) -> str:
        return f"TRINITY_EXECUTION_START {request_id}\n{prompt}\nTRINITY_EXECUTION_END {request_id}"

    def _emit(self, event_type: TUIEventType, **kwargs) -> None:
        if self._event_callback:
            kwargs.setdefault("occurred_at", time.time())
            self._event_callback(TUIEvent(type=event_type, data=kwargs))

    def _agent_attempt_order(self, owner_agent: str) -> tuple[str, ...]:
        """Return owner-first execution attempts with deterministic fallback order."""
        attempts: list[str] = []
        normalized_owner = self._normalize_owner_agent(owner_agent)
        if normalized_owner:
            attempts.append(normalized_owner)
        fallbacks = sorted(
            (name for name in self.agents if name != normalized_owner),
            key=lambda name: (self._fallback_priority_index(name), name),
        )
        attempts.extend(fallbacks)
        return tuple(dict.fromkeys(attempts))

    @staticmethod
    def _fallback_priority_index(agent_name: str) -> int:
        try:
            return EXECUTION_FALLBACK_PRIORITY.index(agent_name)
        except ValueError:
            return len(EXECUTION_FALLBACK_PRIORITY)

    def _normalize_owner_agent(self, owner_agent: str) -> str:
        alias = LEGACY_OWNER_ALIASES.get(owner_agent)
        if alias and alias in self.agents:
            return alias
        return owner_agent


def _is_substantive_line(line: str) -> bool:
    normalized = re.sub(r"^\s*[-*]\s*", "", line).strip().lower()
    normalized = normalized.strip(" \t\r\n.。．:：;；,，")
    return bool(normalized) and normalized not in {
        "none",
        "n/a",
        "na",
        "(none)",
        "nothing",
        "nothing.",
        "no blocker",
        "no blockers",
        "no blocking issue",
        "no blocking issues",
        "no issue",
        "no issues",
        "no unresolved issue",
        "no unresolved issues",
        "없음",
        "없습니다",
        "없다",
        "없습니다.",
        "해당 없음",
        "해당없음",
        "문제 없음",
        "문제없음",
        "블로커 없음",
        "블로커없음",
        "차단 없음",
        "차단없음",
    }


def _normalize_field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
