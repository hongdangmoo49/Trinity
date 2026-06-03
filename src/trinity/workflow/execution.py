"""ExecutionProtocol — dispatch WorkPackages to agents in parallel."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

from trinity.models import ExecutionResult, WorkPackage, WorkStatus

if TYPE_CHECKING:
    from trinity.agents.base import AgentWrapper

logger = logging.getLogger(__name__)

EXECUTION_PROMPT_TEMPLATE = """\
[Work Package]
ID: {package_id}
Owner: {owner}
Objective: {objective}
Scope:
{scope}
Acceptance Criteria:
{acceptance}

{decisions_section}
작업을 수행하고 결과를 다음 형식으로 보고:
## Completed
## Files Changed
## Decisions Made
## Blockers
## Follow-up"""


class ExecutionProtocol:
    """Dispatch WorkPackages to agents in parallel and collect results."""

    def __init__(self, agents: dict[str, AgentWrapper]) -> None:
        self._agents = agents

    # -- public API ----------------------------------------------------------

    async def run(
        self,
        packages: list[WorkPackage],
        timeout: float = 300.0,
    ) -> list[ExecutionResult]:
        """Dispatch all packages in parallel and return their results.

        If no agent exists for a package's owner, a FAILED result is returned
        immediately.
        """
        coros = []
        for wp in packages:
            agent = self._agents.get(wp.owner_agent)
            if agent is None:
                logger.warning(
                    "No agent for owner=%s, package=%s — marking FAILED",
                    wp.owner_agent,
                    wp.id,
                )
                coros.append(self._make_missing_agent_coro(wp))
            else:
                coros.append(self._dispatch_and_collect(agent, wp, timeout))

        raw_results = await asyncio.gather(*coros, return_exceptions=True)

        results: list[ExecutionResult] = []
        for item in raw_results:
            if isinstance(item, ExecutionResult):
                results.append(item)
            elif isinstance(item, BaseException):
                logger.exception("Unexpected exception during execution: %s", item)
                results.append(
                    ExecutionResult(
                        package_id="unknown",
                        agent_name="unknown",
                        status=WorkStatus.FAILED,
                        summary=f"Unexpected error: {item}",
                    )
                )
        return results

    # -- internal dispatch ---------------------------------------------------

    async def _dispatch_and_collect(
        self,
        agent: AgentWrapper,
        wp: WorkPackage,
        timeout: float,
    ) -> ExecutionResult:
        """Send the execution prompt to *agent* and parse the response."""
        try:
            prompt = self.build_execution_prompt(wp)
            response = await agent.send_and_wait(prompt, timeout)
            return self._parse_response(wp, response.content)
        except Exception as exc:
            logger.exception(
                "Agent %s failed for package %s: %s", agent.spec.name, wp.id, exc
            )
            return ExecutionResult(
                package_id=wp.id,
                agent_name=wp.owner_agent,
                status=WorkStatus.FAILED,
                summary=str(exc),
            )

    # -- prompt building -----------------------------------------------------

    @staticmethod
    def build_execution_prompt(
        wp: WorkPackage,
        decisions: list[str] | None = None,
    ) -> str:
        """Build the execution prompt from a WorkPackage."""
        scope_lines = "\n".join(f"- {item}" for item in wp.scope) if wp.scope else "- (none)"
        acceptance_lines = (
            "\n".join(f"- {item}" for item in wp.acceptance_criteria)
            if wp.acceptance_criteria
            else "- (none)"
        )

        if decisions:
            decisions_section = "Relevant Decisions:\n" + "\n".join(
                f"- {d}" for d in decisions
            )
        else:
            decisions_section = ""

        return EXECUTION_PROMPT_TEMPLATE.format(
            package_id=wp.id,
            owner=wp.owner_agent,
            objective=wp.objective,
            scope=scope_lines,
            acceptance=acceptance_lines,
            decisions_section=decisions_section,
        )

    # -- response parsing ----------------------------------------------------

    @staticmethod
    def _extract_files_changed(content: str) -> list[str]:
        """Parse the ## Files Changed section from agent output."""
        return _extract_section(content, "Files Changed")

    @staticmethod
    def _extract_blockers(content: str) -> list[str]:
        """Parse the ## Blockers section from agent output."""
        return _extract_section(content, "Blockers")

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _make_missing_agent_coro(wp: WorkPackage) -> object:
        """Return a coroutine that immediately yields a FAILED ExecutionResult."""
        return _missing_agent_result(wp)

    @staticmethod
    def _parse_response(wp: WorkPackage, content: str) -> ExecutionResult:
        """Parse agent response content into an ExecutionResult."""
        files = _extract_section(content, "Files Changed")
        blockers = _extract_section(content, "Blockers")
        status = WorkStatus.BLOCKED if blockers else WorkStatus.DONE
        summary = _extract_section_text(content, "Completed")
        if not summary:
            summary = content[:200] if content else "(no output)"

        return ExecutionResult(
            package_id=wp.id,
            agent_name=wp.owner_agent,
            status=status,
            summary=summary,
            files_changed=files,
            blockers=blockers,
        )


# -- module-level helpers ----------------------------------------------------

async def _missing_agent_result(wp: WorkPackage) -> ExecutionResult:
    """Coroutine that yields a FAILED result for a missing agent."""
    return ExecutionResult(
        package_id=wp.id,
        agent_name=wp.owner_agent,
        status=WorkStatus.FAILED,
        summary=f"No agent available for owner '{wp.owner_agent}'",
    )


def _extract_section(content: str, heading: str) -> list[str]:
    """Extract bullet items from a markdown ## heading section."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return []
    section = match.group(1).strip()
    if not section:
        return []
    items: list[str] = []
    for line in section.splitlines():
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            items.append(line[2:].strip())
        elif line and not line.startswith("#"):
            items.append(line)
    return items


def _extract_section_text(content: str, heading: str) -> str:
    """Extract the raw text under a markdown ## heading."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()
