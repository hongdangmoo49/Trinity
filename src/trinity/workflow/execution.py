"""Execution protocol for approved workflow work packages."""

from __future__ import annotations

import asyncio
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
    WorkPackage,
    WorkStatus,
)

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
    ):
        self.agents = agents
        self.shared = shared
        self.artifact_dir = artifact_dir
        self.timeout = timeout
        self._event_callback = event_callback

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

            result = await self.dispatch_package(package, decisions)
            package.status = result.status
            results.append(result)
            self._record_result(result)

        self._emit(TUIEventType.EXECUTION_DONE, package_count=len(packages))
        return results

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
            "Perform this work package. When finished, report exactly in this "
            "format:\n"
            "## Completed\n"
            "## Files Changed\n"
            "## Decisions Made\n"
            "## Blockers\n"
            "## Follow-up\n"
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
        }

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
