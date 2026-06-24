"""Provider-backed review execution for completed workflow work packages."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Iterable
from pathlib import Path
from uuid import uuid4

from trinity.agents.base import AgentWrapper
from trinity.context.shared import SharedContextEngine
from trinity.models import DeliberationMessage, ResponseStatus
from trinity.prompts.context_projection import (
    agent_context_profile,
    render_context_projection_block,
    render_operating_profile_block,
)
from trinity.prompts.contracts import (
    FINAL_REVIEW_CONTRACT_ID,
    REVIEW_CONTRACT_ID,
    render_output_contract,
)
from trinity.providers.policy import InvocationAccess
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.workflow.models import ExecutionResult, WorkPackage
from trinity.workflow.review import (
    FINAL_REVIEW_FALLBACK_PRIORITY,
    FINAL_REVIEW_PACKAGE_ID,
    ReviewPackage,
    ReviewResult,
    ReviewStatus,
    final_review_package,
)

logger = logging.getLogger(__name__)


class ReviewExecutionProtocol:
    """Dispatch review packages to providers and parse structured results."""

    def __init__(
        self,
        agents: dict[str, AgentWrapper],
        shared: SharedContextEngine,
        artifact_dir: Path,
        timeout: float = 300.0,
        event_callback=None,
        final_reviewer_priority: tuple[str, ...] = FINAL_REVIEW_FALLBACK_PRIORITY,
        target_workspace: Path | None = None,
    ) -> None:
        self.agents = agents
        self.shared = shared
        self.artifact_dir = artifact_dir
        self.timeout = timeout
        self._event_callback = event_callback
        self.final_reviewer_priority = final_reviewer_priority
        self.target_workspace = target_workspace.resolve() if target_workspace else None

    async def review_work_packages(
        self,
        review_packages: Iterable[ReviewPackage],
        work_packages: Iterable[WorkPackage],
        execution_results: Iterable[ExecutionResult],
    ) -> list[ReviewResult]:
        """Run provider reviews for the selected work package review tasks."""
        packages_by_id = {package.id: package for package in work_packages}
        results_by_package = {result.package_id: result for result in execution_results}
        review_tasks = list(review_packages)
        if not review_tasks:
            return []

        self._emit(TUIEventType.REVIEW_START, review_count=len(review_tasks), scope="wp")
        for review_package in review_tasks:
            self._emit_review_package_event(
                TUIEventType.REVIEW_PACKAGE_QUEUED,
                review_package,
                status="queued",
            )
        results: list[ReviewResult] = []
        for review_package in review_tasks:
            package = packages_by_id.get(review_package.package_id)
            execution_result = results_by_package.get(review_package.package_id)
            if package is None:
                self._emit_review_package_event(
                    TUIEventType.REVIEW_PACKAGE_SKIPPED,
                    review_package,
                    status="skipped",
                    summary=(
                        f"Work package '{review_package.package_id}' is not available "
                        "for review."
                    ),
                )
                results.append(self._missing_package_result(review_package))
                continue
            results.append(
                await self.review_work_package(
                    review_package,
                    package,
                    execution_result,
                )
            )
        self._emit(TUIEventType.REVIEW_DONE, review_count=len(results), scope="wp")
        return results

    async def review_work_package(
        self,
        review_package: ReviewPackage,
        package: WorkPackage,
        execution_result: ExecutionResult | None,
    ) -> ReviewResult:
        """Run one WP review with deterministic reviewer fallback."""
        failed_attempts: list[ReviewResult] = []
        for reviewer_agent in self._reviewer_attempt_order(review_package):
            agent = self.agents.get(reviewer_agent)
            if agent is None:
                attempted = self._attempted_review_package(review_package, reviewer_agent)
                self._emit_review_package_event(
                    TUIEventType.REVIEW_PACKAGE_SKIPPED,
                    attempted,
                    status="skipped",
                    summary=f"Review agent '{reviewer_agent}' is not available.",
                )
                failed_attempts.append(
                    self._failed_result(
                        review_package,
                        reviewer_agent,
                        f"Review agent '{reviewer_agent}' is not available.",
                    )
                )
                continue

            attempted = self._attempted_review_package(review_package, reviewer_agent)
            result = await self._dispatch_work_package_review(
                attempted,
                package,
                execution_result,
                agent,
            )
            if result.status != ReviewStatus.FAILED:
                return result
            failed_attempts.append(result)
        result = self._aggregate_failed_result(review_package, failed_attempts)
        self._emit_review_package_completed(result)
        return result

    async def review_final_execution(
        self,
        work_packages: Iterable[WorkPackage],
        execution_results: Iterable[ExecutionResult],
        review_results: Iterable[ReviewResult],
    ) -> ReviewResult:
        """Run the final project review using codex -> claude -> antigravity fallback."""
        self._emit(TUIEventType.REVIEW_START, review_count=1, scope="final")
        failed_attempts: list[ReviewResult] = []
        for attempt, reviewer_agent in enumerate(self._final_reviewer_attempt_order(), start=1):
            agent = self.agents.get(reviewer_agent)
            review_package = final_review_package(reviewer_agent, attempt=attempt)
            if agent is None:
                failed_attempts.append(
                    self._failed_result(
                        review_package,
                        reviewer_agent,
                        f"Final review agent '{reviewer_agent}' is not available.",
                    )
                )
                continue
            result = await self._dispatch_final_review(
                review_package,
                list(work_packages),
                list(execution_results),
                list(review_results),
                agent,
            )
            if result.status != ReviewStatus.FAILED:
                self._emit(TUIEventType.REVIEW_DONE, review_count=1, scope="final")
                return result
            failed_attempts.append(result)
        self._emit(TUIEventType.REVIEW_DONE, review_count=1, scope="final")
        return self._aggregate_failed_result(
            final_review_package(self.final_reviewer_priority[0]),
            failed_attempts,
        )

    async def _dispatch_work_package_review(
        self,
        review_package: ReviewPackage,
        package: WorkPackage,
        execution_result: ExecutionResult | None,
        agent: AgentWrapper,
    ) -> ReviewResult:
        request_id = self._new_request_id(review_package)
        self._emit_review_package_event(
            TUIEventType.REVIEW_PACKAGE_STARTED,
            review_package,
            status="reviewing",
            output_contract=REVIEW_CONTRACT_ID,
            context_profile=self._agent_context_profile(
                review_package.reviewer_agent
            ),
        )
        self._emit(
            TUIEventType.WORK_PACKAGE_REVIEW_STARTED,
            package_id=review_package.package_id,
            reviewer=review_package.reviewer_agent,
            target=review_package.target_agent,
        )
        prompt = self._wrap_review_prompt(
            self._build_work_package_review_prompt(
                review_package,
                package,
                execution_result,
            ),
            request_id,
        )
        try:
            message = await agent.send_and_wait(
                prompt,
                timeout=self.timeout,
                access=InvocationAccess.READ_ONLY,
            )
        except asyncio.TimeoutError as exc:
            result = self._failed_result(
                review_package,
                review_package.reviewer_agent,
                f"Review timed out: {exc}",
            )
        except Exception as exc:
            logger.error("[%s] review failed: %s", review_package.reviewer_agent, exc)
            result = self._failed_result(
                review_package,
                review_package.reviewer_agent,
                f"Review failed: {exc}",
            )
        else:
            result = self.collect_result(
                review_package,
                request_id,
                message,
                review_package.reviewer_agent,
            )

        self._emit_review_package_completed(result)
        return result

    async def _dispatch_final_review(
        self,
        review_package: ReviewPackage,
        work_packages: list[WorkPackage],
        execution_results: list[ExecutionResult],
        review_results: list[ReviewResult],
        agent: AgentWrapper,
    ) -> ReviewResult:
        request_id = self._new_request_id(review_package)
        self._emit(
            TUIEventType.FINAL_REVIEW_STARTED,
            reviewer=review_package.reviewer_agent,
            output_contract=FINAL_REVIEW_CONTRACT_ID,
            context_profile=self._agent_context_profile(
                review_package.reviewer_agent
            ),
        )
        prompt = self._wrap_review_prompt(
            self._build_final_review_prompt(
                work_packages,
                execution_results,
                review_results,
                reviewer_agent=review_package.reviewer_agent,
            ),
            request_id,
        )
        try:
            message = await agent.send_and_wait(
                prompt,
                timeout=self.timeout,
                access=InvocationAccess.READ_ONLY,
            )
        except asyncio.TimeoutError as exc:
            result = self._failed_result(
                review_package,
                review_package.reviewer_agent,
                f"Final review timed out: {exc}",
            )
        except Exception as exc:
            logger.error("[%s] final review failed: %s", review_package.reviewer_agent, exc)
            result = self._failed_result(
                review_package,
                review_package.reviewer_agent,
                f"Final review failed: {exc}",
            )
        else:
            result = self.collect_result(
                review_package,
                request_id,
                message,
                review_package.reviewer_agent,
            )

        self._emit(
            TUIEventType.FINAL_REVIEW_COMPLETED,
            reviewer=result.reviewer_agent,
            status=result.status.value,
            severity=result.severity,
            summary=result.summary,
            output_contract=FINAL_REVIEW_CONTRACT_ID,
        )
        return result

    def collect_result(
        self,
        review_package: ReviewPackage,
        request_id: str,
        message: DeliberationMessage,
        reviewer_agent: str,
    ) -> ReviewResult:
        """Parse a provider message into a structured review result."""
        raw_content = str(message.metadata.get("raw_output") or message.content or "")
        raw_path = self._write_raw_response(review_package, request_id, raw_content, reviewer_agent)
        if self._message_failed(message):
            response_status = str(message.metadata.get("response_status") or "")
            status = (
                ReviewStatus.BLOCKED
                if response_status == ResponseStatus.PERMISSION_REQUIRED.value
                else ReviewStatus.FAILED
            )
            return ReviewResult(
                review_package_id=review_package.id,
                package_id=review_package.package_id,
                reviewer_agent=reviewer_agent,
                target_agent=review_package.target_agent,
                status=status,
                summary=message.content or "Review agent response failed.",
                raw_response_path=raw_path,
                scope=review_package.scope,
            )

        parsed = self._parse_review_response(message.content)
        return ReviewResult(
            review_package_id=review_package.id,
            package_id=review_package.package_id,
            reviewer_agent=reviewer_agent,
            target_agent=review_package.target_agent,
            status=parsed["status"],
            summary=parsed["summary"],
            findings=parsed["findings"],
            required_changes=parsed["required_changes"],
            follow_up=parsed["follow_up"],
            raw_response_path=raw_path,
            severity=parsed["severity"],
            scope=review_package.scope,
            reviewed_files=parsed["reviewed_files"],
            compatibility_notes=parsed["compatibility_notes"],
            performance_notes=parsed["performance_notes"],
            anti_patterns=parsed["anti_patterns"],
            execution_risks=parsed["execution_risks"],
        )

    def _build_work_package_review_prompt(
        self,
        review_package: ReviewPackage,
        package: WorkPackage,
        execution_result: ExecutionResult | None,
    ) -> str:
        files_changed = (
            self._format_list(execution_result.files_changed)
            if execution_result
            else "- none"
        )
        blockers = self._format_list(execution_result.blockers) if execution_result else "- none"
        follow_up = self._format_list(execution_result.follow_up) if execution_result else "- none"
        criteria = self._format_list(review_package.criteria)
        shared_decisions = self.shared.read_section("Agreed Conclusion") or ""
        operating_profile = render_operating_profile_block(
            self.agents,
            review_package.reviewer_agent,
            mode="review",
            heading="[Operating Profile]",
        )
        context_projection = self._context_projection_block(
            review_package.reviewer_agent
        )
        return (
            "[Work Package Review]\n"
            f"Review Package: {review_package.id}\n"
            f"Package: {package.id}\n"
            f"Title: {package.title}\n"
            f"Owner: {package.owner_agent}\n"
            f"Executor: {review_package.target_agent}\n"
            f"Objective: {package.objective}\n\n"
            f"{operating_profile}"
            f"{self._target_workspace_block()}"
            "Scope:\n"
            f"{self._format_list(package.scope)}\n\n"
            "Expected Files:\n"
            f"{self._format_list(package.expected_files)}\n\n"
            "Acceptance Criteria:\n"
            f"{self._format_list(package.acceptance_criteria)}\n\n"
            "Execution Summary:\n"
            f"{execution_result.summary if execution_result else '(none)'}\n\n"
            "Files Changed:\n"
            f"{files_changed}\n\n"
            "Execution Blockers:\n"
            f"{blockers}\n\n"
            "Execution Follow-up:\n"
            f"{follow_up}\n\n"
            "Shared Decisions:\n"
            f"{shared_decisions.strip() or '(none)'}\n\n"
            f"{context_projection}"
            "Review Criteria:\n"
            f"{criteria}\n\n"
            "Review the completed work package. Focus on severe runtime errors, "
            "anti-patterns, and performance concerns. Do not modify files. "
            "Report exactly in this format:\n"
            f"{render_output_contract(REVIEW_CONTRACT_ID)}\n"
        )

    def _build_final_review_prompt(
        self,
        work_packages: list[WorkPackage],
        execution_results: list[ExecutionResult],
        review_results: list[ReviewResult],
        reviewer_agent: str = "",
    ) -> str:
        package_lines = [
            f"- {package.id} [{package.status.value}] {package.owner_agent}: {package.title}"
            for package in work_packages
        ]
        execution_lines = [
            f"- {result.package_id} [{result.status.value}] {result.agent_name}: {result.summary}"
            for result in execution_results
        ]
        review_lines = [
            (
                f"- {result.package_id} [{result.status.value}] "
                f"{result.reviewer_agent}: {result.summary}"
            )
            for result in review_results
            if result.scope != "final"
        ]
        context_projection = self._context_projection_block(reviewer_agent)
        operating_profile = render_operating_profile_block(
            self.agents,
            reviewer_agent,
            mode="final_review",
            heading="[Operating Profile]",
        )
        return (
            "[Final Project Review]\n"
            "Review the whole completed project after execution.\n\n"
            f"{operating_profile}"
            f"{self._target_workspace_block()}"
            "Work Packages:\n"
            f"{self._format_list(package_lines)}\n\n"
            "Execution Results:\n"
            f"{self._format_list(execution_lines)}\n\n"
            "WP Review Results:\n"
            f"{self._format_list(review_lines)}\n\n"
            f"{context_projection}"
            "Focus on whole-project compatibility, project overview, run "
            "instructions, and additional features that appear necessary. "
            "Do not modify files. Report exactly in this format:\n"
            f"{render_output_contract(FINAL_REVIEW_CONTRACT_ID)}\n"
        )

    def _target_workspace_block(self) -> str:
        if self.target_workspace is None:
            return ""
        return (
            "Target Workspace Context:\n"
            f"- Target workspace: {self.target_workspace}\n"
            "- Review project files and implementation artifacts in this workspace.\n"
            "- Do not modify files during review.\n\n"
        )

    def _context_projection_block(self, agent_name: str) -> str:
        return render_context_projection_block(
            self.shared,
            self._agent_context_profile(agent_name),
            heading="Context Projection:",
        )

    def _agent_context_profile(self, agent_name: str) -> str:
        return agent_context_profile(self.agents, agent_name)

    @classmethod
    def _parse_review_response(cls, content: str) -> dict:
        sections = cls._parse_sections(content)
        required_changes = cls._section_items(sections, "required changes")
        status = cls._parse_status(content, required_changes)
        severity = cls._parse_severity(content)
        summary = (
            cls._section_text(sections, "summary")
            or cls._section_text(sections, "project overview")
            or content.strip()
        )
        return {
            "status": status,
            "severity": severity,
            "summary": summary,
            "findings": cls._section_items(sections, "findings"),
            "required_changes": required_changes,
            "follow_up": [
                *cls._section_items(sections, "follow up"),
                *cls._section_items(sections, "run instructions"),
                *cls._section_items(sections, "recommended features"),
            ],
            "reviewed_files": cls._section_items(sections, "reviewed files"),
            "compatibility_notes": cls._section_items(sections, "compatibility"),
            "performance_notes": cls._section_items(sections, "performance notes"),
            "anti_patterns": cls._section_items(sections, "anti patterns"),
            "execution_risks": [
                *cls._section_items(sections, "execution risks"),
                *cls._section_items(sections, "critical risks"),
            ],
        }

    @staticmethod
    def _parse_sections(content: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {}
        current = "summary"
        sections[current] = []
        for line in content.splitlines():
            markdown_heading = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
            label_heading = re.match(r"^\s*([A-Z][A-Z0-9 _/-]+):\s*$", line)
            if markdown_heading or label_heading:
                raw = (markdown_heading or label_heading).group(1)
                current = _normalize_review_field(raw)
                sections.setdefault(current, [])
                continue
            if re.match(r"^\s*(REVIEW STATUS|FINAL REVIEW STATUS|SEVERITY):", line, re.I):
                continue
            sections.setdefault(current, []).append(line)
        return sections

    @staticmethod
    def _section_text(sections: dict[str, list[str]], name: str) -> str:
        return "\n".join(
            line.strip()
            for line in sections.get(_normalize_review_field(name), [])
            if _is_substantive_review_line(line)
        ).strip()

    @classmethod
    def _section_items(cls, sections: dict[str, list[str]], name: str) -> list[str]:
        text = cls._section_text(sections, name)
        if not text:
            return []
        return [
            re.sub(r"^\s*[-*]\s*", "", line).strip()
            for line in text.splitlines()
            if _is_substantive_review_line(line)
        ]

    @staticmethod
    def _parse_status(content: str, required_changes: list[str]) -> ReviewStatus:
        match = re.search(r"(?:FINAL\s+)?REVIEW STATUS:\s*([A-Z_ -]+)", content, re.I)
        normalized = _normalize_review_field(match.group(1) if match else "")
        aliases = {
            "approved": ReviewStatus.APPROVED,
            "approve": ReviewStatus.APPROVED,
            "changes_requested": ReviewStatus.CHANGES_REQUESTED,
            "change_requested": ReviewStatus.CHANGES_REQUESTED,
            "blocked": ReviewStatus.BLOCKED,
            "failed": ReviewStatus.FAILED,
        }
        if normalized in aliases:
            return aliases[normalized]
        return ReviewStatus.CHANGES_REQUESTED if required_changes else ReviewStatus.APPROVED

    @staticmethod
    def _parse_severity(content: str) -> str:
        match = re.search(r"SEVERITY:\s*([A-Z_ -]+)", content, re.I)
        normalized = _normalize_review_field(match.group(1) if match else "medium")
        allowed = {"low", "medium", "high", "critical"}
        return normalized if normalized in allowed else "medium"

    def _reviewer_attempt_order(self, review_package: ReviewPackage) -> tuple[str, ...]:
        attempts = [review_package.reviewer_agent]
        attempts.extend(
            agent
            for agent in sorted(self.agents)
            if agent not in attempts and agent != review_package.target_agent
        )
        if review_package.target_agent in self.agents and review_package.target_agent not in attempts:
            attempts.append(review_package.target_agent)
        return tuple(agent for agent in attempts if agent)

    def _final_reviewer_attempt_order(self) -> tuple[str, ...]:
        attempts = list(self.final_reviewer_priority)
        attempts.extend(agent for agent in sorted(self.agents) if agent not in attempts)
        return tuple(attempts)

    @staticmethod
    def _attempted_review_package(
        review_package: ReviewPackage,
        reviewer_agent: str,
    ) -> ReviewPackage:
        return ReviewPackage(
            id=review_package.id,
            package_id=review_package.package_id,
            reviewer_agent=reviewer_agent,
            target_agent=review_package.target_agent,
            criteria=list(review_package.criteria),
            execution_status=review_package.execution_status,
            scope=review_package.scope,
            attempt=review_package.attempt,
            created_at=review_package.created_at,
        )

    def _missing_package_result(self, review_package: ReviewPackage) -> ReviewResult:
        return ReviewResult(
            review_package_id=review_package.id,
            package_id=review_package.package_id,
            reviewer_agent=review_package.reviewer_agent,
            target_agent=review_package.target_agent,
            status=ReviewStatus.FAILED,
            summary=f"Work package '{review_package.package_id}' is not available for review.",
            scope=review_package.scope,
        )

    @staticmethod
    def _failed_result(
        review_package: ReviewPackage,
        reviewer_agent: str,
        summary: str,
    ) -> ReviewResult:
        return ReviewResult(
            review_package_id=review_package.id,
            package_id=review_package.package_id,
            reviewer_agent=reviewer_agent,
            target_agent=review_package.target_agent,
            status=ReviewStatus.FAILED,
            summary=summary,
            scope=review_package.scope,
        )

    def _aggregate_failed_result(
        self,
        review_package: ReviewPackage,
        attempts: list[ReviewResult],
    ) -> ReviewResult:
        if not attempts:
            return self._failed_result(review_package, review_package.reviewer_agent, "Review failed.")
        summary = "All review attempts failed: " + "; ".join(
            f"{attempt.reviewer_agent}: {attempt.summary}" for attempt in attempts
        )
        last = attempts[-1]
        return ReviewResult(
            review_package_id=review_package.id,
            package_id=review_package.package_id,
            reviewer_agent=last.reviewer_agent,
            target_agent=review_package.target_agent,
            status=ReviewStatus.FAILED,
            summary=summary,
            scope=review_package.scope,
        )

    def _write_raw_response(
        self,
        review_package: ReviewPackage,
        request_id: str,
        raw_content: str,
        reviewer_agent: str,
    ) -> Path:
        safe_package = re.sub(r"[^A-Za-z0-9_.-]+", "-", review_package.package_id).strip("-")
        safe_agent = re.sub(r"[^A-Za-z0-9_.-]+", "-", reviewer_agent).strip("-")
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

    @staticmethod
    def _format_list(items: Iterable[str]) -> str:
        values = [str(item).strip() for item in items if str(item).strip()]
        return "\n".join(f"- {item}" for item in values) if values else "- none"

    @staticmethod
    def _new_request_id(review_package: ReviewPackage) -> str:
        safe_scope = review_package.scope.replace("_", "-")
        return f"review-{safe_scope}-{review_package.package_id.lower()}-{uuid4().hex[:12]}"

    @staticmethod
    def _wrap_review_prompt(prompt: str, request_id: str) -> str:
        return f"TRINITY_REVIEW_START {request_id}\n{prompt}\nTRINITY_REVIEW_END {request_id}"

    def _emit_review_package_event(
        self,
        event_type: TUIEventType,
        review_package: ReviewPackage,
        *,
        status: str = "",
        summary: str = "",
        severity: str = "",
        output_contract: str = "",
        context_profile: str = "",
    ) -> None:
        self._emit(
            event_type,
            review_package_id=review_package.id,
            package_id=review_package.package_id,
            reviewer_agent=review_package.reviewer_agent,
            target_agent=review_package.target_agent,
            status=status,
            summary=summary,
            severity=severity,
            scope=review_package.scope,
            output_contract=output_contract,
            context_profile=context_profile,
        )

    def _emit_review_package_completed(self, result: ReviewResult) -> None:
        self._emit(
            TUIEventType.REVIEW_PACKAGE_COMPLETED,
            review_package_id=result.review_package_id,
            package_id=result.package_id,
            reviewer_agent=result.reviewer_agent,
            target_agent=result.target_agent,
            status=result.status.value,
            severity=result.severity,
            summary=result.summary,
            scope=result.scope,
            output_contract=(
                FINAL_REVIEW_CONTRACT_ID
                if result.scope == "final"
                else REVIEW_CONTRACT_ID
            ),
            context_profile=self._agent_context_profile(result.reviewer_agent),
            required_changes=list(result.required_changes),
        )
        self._emit(
            TUIEventType.WORK_PACKAGE_REVIEW_COMPLETED,
            package_id=result.package_id,
            reviewer=result.reviewer_agent,
            target=result.target_agent,
            status=result.status.value,
            severity=result.severity,
            summary=result.summary,
        )

    def _emit(self, event_type: TUIEventType, **kwargs) -> None:
        if self._event_callback:
            kwargs.setdefault("occurred_at", time.time())
            self._event_callback(TUIEvent(type=event_type, data=kwargs))


def _normalize_review_field(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _is_substantive_review_line(line: str) -> bool:
    normalized = re.sub(r"^\s*[-*]\s*", "", line).strip().lower()
    normalized = normalized.strip(" \t\r\n.。．:：;；,，")
    return bool(normalized) and normalized not in {"none", "n/a", "na", "(none)", "없음"}
