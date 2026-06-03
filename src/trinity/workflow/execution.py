"""Execution protocol for approved workflow work packages."""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Callable
from uuid import uuid4

from trinity.agents.base import AgentWrapper
from trinity.context.shared import SharedContextEngine
from trinity.models import DeliberationMessage
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


class ExecutionProtocol:
    """Dispatch approved work packages to their owner agents."""

    def __init__(
        self,
        agents: dict[str, AgentWrapper],
        shared: SharedContextEngine,
        artifact_dir: Path,
        timeout: float = 120.0,
        event_callback: Callable[[TUIEvent], None] | None = None,
        lifecycle_guard: LifecycleGuard | None = None,
        rotation_callback: Callable[[str], object] | None = None,
    ):
        self.agents = agents
        self.shared = shared
        self.artifact_dir = artifact_dir
        self.timeout = timeout
        self._event_callback = event_callback
        self.lifecycle_guard = lifecycle_guard
        self._rotation_callback = rotation_callback

    async def run(
        self,
        work_packages: Iterable[WorkPackage],
        decisions: Iterable[DecisionRecord] = (),
    ) -> list[ExecutionResult]:
        """Execute all executable work packages and return their results."""
        packages = [package for package in work_packages if package.requires_execution]
        if not packages:
            return []

        self._emit(TUIEventType.EXECUTION_START, package_count=len(packages))
        results: list[ExecutionResult] = []
        packages_by_id = {package.id: package for package in packages}

        for package in packages:
            blocked_dependencies = [
                dep_id
                for dep_id in package.dependencies
                if packages_by_id.get(dep_id)
                and packages_by_id[dep_id].status != WorkStatus.DONE
            ]
            if blocked_dependencies:
                result = self._dependency_blocked_result(package, blocked_dependencies)
                package.status = result.status
                results.append(result)
                self._record_result(result)
                continue

            await self._before_work_package_lifecycle(package)
            result = await self.dispatch_package(package, decisions)
            await self._after_work_package_lifecycle(package)
            package.status = result.status
            results.append(result)
            self._record_result(result)

        self._emit(TUIEventType.EXECUTION_DONE, package_count=len(packages))
        return results

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
        agent = self.agents.get(package.owner_agent)
        if agent is None:
            return self._missing_agent_result(package)

        package.status = WorkStatus.RUNNING
        self._emit(
            TUIEventType.WORK_PACKAGE_STARTED,
            package_id=package.id,
            agent=package.owner_agent,
            status=package.status.value,
        )

        prompt = self._build_execution_prompt(package, decisions)
        request_id = self._new_request_id(package)
        wrapped_prompt = self._wrap_execution_prompt(prompt, request_id)

        try:
            message = await agent.send_and_wait(wrapped_prompt, timeout=self.timeout)
        except asyncio.TimeoutError as exc:
            return self._exception_result(package, request_id, exc, WorkStatus.FAILED)
        except Exception as exc:
            logger.error("[%s] execution failed: %s", package.owner_agent, exc)
            return self._exception_result(package, request_id, exc, WorkStatus.FAILED)

        return self.collect_result(package, request_id, message)

    def collect_result(
        self,
        package: WorkPackage,
        request_id: str,
        message: DeliberationMessage,
    ) -> ExecutionResult:
        """Parse a package execution response into an ExecutionResult."""
        raw_content = str(message.metadata.get("raw_output") or message.content or "")
        raw_path = self._write_raw_response(package, request_id, raw_content)

        if self._message_failed(message):
            return ExecutionResult(
                package_id=package.id,
                agent_name=package.owner_agent,
                status=WorkStatus.FAILED,
                summary=message.content or "Agent response failed.",
                raw_response_path=raw_path,
            )

        parsed = self._parse_execution_response(message.content)
        blockers = parsed["blockers"]
        status = WorkStatus.BLOCKED if blockers else WorkStatus.DONE
        decisions = [
            DecisionRecord(
                id=f"{package.id.lower()}-dec-{idx:03d}",
                decision=decision,
                decided_by=package.owner_agent,
                rationale=f"Execution decision from {package.id}.",
            )
            for idx, decision in enumerate(parsed["decisions_made"], start=1)
        ]
        return ExecutionResult(
            package_id=package.id,
            agent_name=package.owner_agent,
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
        if statuses and all(status == WorkStatus.DONE for status in statuses):
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
        )

    def _missing_agent_result(self, package: WorkPackage) -> ExecutionResult:
        return ExecutionResult(
            package_id=package.id,
            agent_name=package.owner_agent,
            status=WorkStatus.FAILED,
            summary=f"Owner agent '{package.owner_agent}' is not available.",
            blockers=[f"Owner agent '{package.owner_agent}' is not available."],
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
            blockers=[
                "Dependencies not completed: " + ", ".join(sorted(dependencies))
            ],
        )

    def _exception_result(
        self,
        package: WorkPackage,
        request_id: str,
        exc: BaseException,
        status: WorkStatus,
    ) -> ExecutionResult:
        raw_path = self._write_raw_response(package, request_id, f"[Error: {exc}]")
        return ExecutionResult(
            package_id=package.id,
            agent_name=package.owner_agent,
            status=status,
            summary=f"Execution failed: {exc}",
            blockers=[str(exc)],
            raw_response_path=raw_path,
        )

    def _build_execution_prompt(
        self,
        package: WorkPackage,
        decisions: Iterable[DecisionRecord],
    ) -> str:
        decisions_text = "\n".join(
            f"- {decision.id}: {decision.decision}" for decision in decisions
        ) or "- none"
        scope = self._format_list(package.scope)
        out_of_scope = self._format_list(package.out_of_scope)
        acceptance = self._format_list(package.acceptance_criteria)
        expected_files = self._format_list(package.expected_files)
        shared_decisions = self.shared.read_section("Agreed Conclusion") or ""

        return (
            "[Work Package]\n"
            f"ID: {package.id}\n"
            f"Owner: {package.owner_agent}\n"
            f"Objective: {package.objective}\n"
            f"Title: {package.title}\n\n"
            "Scope:\n"
            f"{scope}\n\n"
            "Out of Scope:\n"
            f"{out_of_scope}\n\n"
            "Expected Files:\n"
            f"{expected_files}\n\n"
            "Acceptance Criteria:\n"
            f"{acceptance}\n\n"
            "[Shared Decisions]\n"
            f"{decisions_text}\n\n"
            "[Agreed Conclusion]\n"
            f"{shared_decisions.strip() or '(none)'}\n\n"
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
            "## Completed\n"
            "## Files Changed\n"
            "## Decisions Made\n"
            "## Blockers\n"
            "## Follow-up\n"
            "## Subtasks\n"
            "### ST-001\n"
            "- delegated_to: <subagent/tool or none>\n"
            "- objective: <input objective>\n"
            "- result_summary: <output summary>\n"
            "- status: done | blocked | failed\n"
            "- decisions_made: <comma-separated decisions or none>\n"
            "- files_changed: <comma-separated files or none>\n"
            "- unresolved_issues: <comma-separated issues or none>\n"
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
            status = cls._parse_work_status(
                cls._field(fields, "status") or WorkStatus.DONE.value
            )
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
            if value and value.lower() not in {"none", "n/a", "na", "(none)"}:
                return value
        return ""

    @classmethod
    def _field_list(cls, fields: dict[str, str], *names: str) -> list[str]:
        value = cls._field(fields, *names)
        if not value:
            return []
        parts = re.split(r"[,;\n]+", value)
        return [
            re.sub(r"^\s*[-*]\s*", "", part).strip()
            for part in parts
            if _is_substantive_line(part)
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

    @staticmethod
    def _message_failed(message: DeliberationMessage) -> bool:
        metadata = message.metadata
        return (
            metadata.get("error") == "timeout"
            or metadata.get("completed") is False
            or metadata.get("response_status") in {"timeout", "process_dead", "invalid"}
        )

    def _write_raw_response(
        self,
        package: WorkPackage,
        request_id: str,
        raw_content: str,
    ) -> Path:
        safe_package = re.sub(r"[^A-Za-z0-9_.-]+", "-", package.id).strip("-")
        safe_agent = re.sub(r"[^A-Za-z0-9_.-]+", "-", package.owner_agent).strip("-")
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
        return (
            f"TRINITY_EXECUTION_START {request_id}\n"
            f"{prompt}\n"
            f"TRINITY_EXECUTION_END {request_id}"
        )

    def _emit(self, event_type: TUIEventType, **kwargs) -> None:
        if self._event_callback:
            self._event_callback(TUIEvent(type=event_type, data=kwargs))


def _is_substantive_line(line: str) -> bool:
    normalized = re.sub(r"^\s*[-*]\s*", "", line).strip().lower()
    return bool(normalized) and normalized not in {"none", "n/a", "na", "(none)"}


def _normalize_field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
