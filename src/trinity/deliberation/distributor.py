"""Task distributor — map consensus decisions to agent-specific tasks."""

from __future__ import annotations

import logging

from trinity.models import AgentSpec, TaskAssignment

logger = logging.getLogger(__name__)


class TaskDistributor:
    """Assign tasks to agents based on consensus and agent strengths.

    Phase 1: simple keyword-based matching.
    Phase 4+: LLM-based task decomposition.
    """

    # Default agent strength mapping
    DEFAULT_STRENGTHS: dict[str, list[str]] = {
        "claude": [
            "architecture",
            "design",
            "code review",
            "complex logic",
            "planning",
            "specification",
            "documentation",
        ],
        "codex": [
            "implementation",
            "coding",
            "prototyping",
            "refactoring",
            "bulk code",
            "fixing",
            "testing",
        ],
        "gemini": [
            "testing",
            "research",
            "alternative exploration",
            "documentation",
            "review",
            "quality assurance",
            "edge cases",
        ],
    }

    def __init__(self, agent_strengths: dict[str, list[str]] | None = None):
        self.strengths = agent_strengths or self.DEFAULT_STRENGTHS

    def distribute(
        self,
        consensus_text: str,
        agents: dict[str, AgentSpec],
    ) -> list[TaskAssignment]:
        """Distribute tasks based on consensus content and agent capabilities.

        Args:
            consensus_text: The agreed-upon conclusion from deliberation.
            agents: Available agent specs.

        Returns:
            List of TaskAssignment, one per agent.
        """
        if not agents:
            return []

        assignments: list[TaskAssignment] = []
        consensus_lower = consensus_text.lower()

        for name, spec in agents.items():
            strengths = self.strengths.get(name, ["general"])
            matched_strengths = [s for s in strengths if s in consensus_lower]

            task = self._generate_task(name, spec, consensus_text, matched_strengths)
            assignments.append(task)

            logger.info(f"Task assigned to {name}: {task.task_description[:80]}...")

        return assignments

    def _generate_task(
        self,
        agent_name: str,
        spec: AgentSpec,
        consensus: str,
        matched_strengths: list[str],
    ) -> TaskAssignment:
        """Generate a task description for a specific agent."""
        role = spec.role_prompt or agent_name

        if matched_strengths:
            strengths_text = ", ".join(matched_strengths)
            task_desc = (
                f"[{agent_name}] Handle: {strengths_text}. "
                f"Consensus: {consensus[:150]}"
            )
        else:
            # No specific strength matched — assign based on role
            role_short = role.split(".")[0] if "." in role else role[:50]
            task_desc = (
                f"[{agent_name}] As {role_short}, execute on the agreed conclusion. "
                f"Consensus: {consensus[:100]}"
            )

        return TaskAssignment(
            agent_name=agent_name,
            task_description=task_desc,
            priority=len(matched_strengths),  # More matches = higher priority
        )
