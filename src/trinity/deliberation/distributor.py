"""Task distributor — map consensus decisions to agent-specific tasks."""

from __future__ import annotations

import logging

from trinity.models import AgentSpec, TaskAssignment, TaskIntent

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

    DESIGN_ONLY_MARKERS = (
        "design only",
        "planning only",
        "plan only",
        "proposal only",
        "spec only",
        "architecture only",
        "do not implement",
        "don't implement",
        "without implementing",
        "no implementation",
        "no code changes",
        "without code changes",
        "do not change files",
        "don't change files",
        "do not edit files",
        "don't edit files",
        "without editing files",
    )
    DESIGN_MARKERS = (
        "analyze",
        "architecture",
        "brainstorm",
        "compare",
        "design",
        "evaluate",
        "outline",
        "plan",
        "proposal",
        "recommend",
        "review",
        "rfc",
        "spec",
        "specification",
        "strategy",
        "tradeoff",
    )
    EXECUTION_MARKERS = (
        "add",
        "build",
        "change",
        "edit",
        "execute",
        "fix",
        "implement",
        "implementation",
        "integrate",
        "migrate",
        "modify",
        "refactor",
        "ship",
        "test",
        "update",
        "wire",
        "write code",
    )

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
        intent = self._classify_intent(consensus_text)

        for name, spec in agents.items():
            strengths = self.strengths.get(name, ["general"])
            matched_strengths = [s for s in strengths if s in consensus_lower]

            task = self._generate_task(
                name,
                spec,
                consensus_text,
                matched_strengths,
                intent,
            )
            assignments.append(task)

            logger.info(
                f"Task plan assigned to {name} ({task.intent.value}): "
                f"{task.task_description[:80]}..."
            )

        return assignments

    def _classify_intent(self, consensus: str) -> TaskIntent:
        """Classify whether the agreed plan asks for design or execution work."""
        normalized = " ".join(consensus.lower().split())

        if any(marker in normalized for marker in self.DESIGN_ONLY_MARKERS):
            return TaskIntent.DESIGN_ONLY

        has_execution = any(marker in normalized for marker in self.EXECUTION_MARKERS)
        has_design = any(marker in normalized for marker in self.DESIGN_MARKERS)

        if has_execution:
            return TaskIntent.EXECUTION
        if has_design:
            return TaskIntent.DESIGN_ONLY
        return TaskIntent.PLAN

    def _generate_task(
        self,
        agent_name: str,
        spec: AgentSpec,
        consensus: str,
        matched_strengths: list[str],
        intent: TaskIntent,
    ) -> TaskAssignment:
        """Generate a task description for a specific agent."""
        role = spec.role_prompt or agent_name

        if matched_strengths:
            strengths_text = ", ".join(matched_strengths)
            focus = f"focus on {strengths_text}"
            reference = consensus[:150]
        else:
            # No specific strength matched — assign based on role
            role_short = role.split(".")[0] if "." in role else role[:50]
            focus = f"act from role: {role_short}"
            reference = consensus[:100]

        if intent == TaskIntent.DESIGN_ONLY:
            task_desc = (
                f"[{agent_name}] Plan item (design only): {focus}; "
                f"produce analysis or specification only. Do not edit files. "
                f"Reference: {reference}"
            )
        elif intent == TaskIntent.EXECUTION:
            task_desc = (
                f"[{agent_name}] Plan item (execution): {focus}; "
                f"prepare actionable implementation or test work from the agreed conclusion. "
                f"Reference: {reference}"
            )
        else:
            task_desc = (
                f"[{agent_name}] Plan item: {focus}; "
                f"clarify next steps from the agreed conclusion. Reference: {reference}"
            )

        return TaskAssignment(
            agent_name=agent_name,
            task_description=task_desc,
            priority=len(matched_strengths),  # More matches = higher priority
            intent=intent,
            requires_execution=intent == TaskIntent.EXECUTION,
        )
