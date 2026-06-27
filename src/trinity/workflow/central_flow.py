"""Central-agent interaction helpers for WorkflowEngine."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from trinity.workflow.models import Blueprint, DecisionRecord, OpenQuestion


class WorkflowCentralFlow:
    """Handle central-agent transcript, questions, and continuation prompts."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def _record_central_conversation(
        self,
        *,
        title: str,
        body: str,
        role: str = "central",
        channel: str = "nexus",
        command: str = "",
        related_ids: Iterable[str] = (),
        truncated: bool = False,
    ) -> None:
        """Persist a central-agent transcript item for report reconstruction."""
        self.engine._persistence_flow().persist(
            "central_conversation_recorded",
            {
                "message_id": f"cc-{uuid4().hex[:12]}",
                "role": role,
                "channel": channel,
                "title": title,
                "body": body,
                "command": command,
                "related_ids": [
                    str(item) for item in related_ids if str(item).strip()
                ],
                "truncated": truncated,
            },
        )

    @staticmethod
    def _central_blueprint_body(blueprint: Blueprint) -> str:
        lines = [f"# {blueprint.title or 'Blueprint'}"]
        if blueprint.summary:
            lines.extend(["", blueprint.summary])
        if blueprint.architecture:
            lines.extend(["", "## Architecture"])
            lines.extend(
                f"- {component.name}: {component.responsibility}"
                for component in blueprint.architecture
            )
        if blueprint.data_flow:
            lines.extend(["", "## Data Flow"])
            lines.extend(f"- {item}" for item in blueprint.data_flow)
        if blueprint.acceptance_criteria:
            lines.extend(["", "## Acceptance Criteria"])
            lines.extend(f"- {item}" for item in blueprint.acceptance_criteria)
        return "\n".join(lines)

    def _apply_structured_questions(self, structured: dict) -> bool:
        raw_questions = structured.get("open_questions", [])
        if not isinstance(raw_questions, list) or not raw_questions:
            return False

        session = self.engine.session
        existing = {
            self._normalize_question(question.question)
            for question in session.pending_questions
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
            session.pending_questions.append(question)
            existing.add(normalized)
            added = True
        return added or saw_valid_question

    @staticmethod
    def _normalize_question(question: str) -> str:
        return " ".join(question.strip().lower().split())

    def _unique_question_id(self, question_id: str) -> str:
        """Return a question id that does not collide with session history."""
        session = self.engine.session
        base = question_id.strip() or "oq"
        existing = {question.id for question in session.pending_questions}
        existing.update(
            decision.question_id
            for decision in session.decisions
            if decision.question_id
        )
        if base not in existing:
            return base

        index = 2
        while f"{base}-{index}" in existing:
            index += 1
        return f"{base}-{index}"

    def build_decision_continuation_prompt(self, decision: DecisionRecord) -> str:
        session = self.engine.session
        decisions = "\n".join(
            f"- {item.id}: {item.decision}" for item in session.decisions
        )
        return (
            "Continue the existing workflow using the user's decision below.\n\n"
            f"Original goal:\n{session.goal}\n\n"
            f"{self._target_workspace_prompt_block()}"
            f"Latest decision ({decision.id}):\n{decision.decision}\n\n"
            f"All decisions:\n{decisions}\n\n"
            "Update the design based on these decisions and continue deliberation. "
            "If a final blueprint is approved, include executable work packages "
            "covering the full deliverable graph, with owners, dependencies, "
            "expected files, acceptance criteria, risk, and parallelization metadata."
        )

    def _build_decision_continuation_prompt(self, decision: DecisionRecord) -> str:
        return self.build_decision_continuation_prompt(decision)

    def build_blueprint_continuation_prompt(self, instruction: str) -> str:
        session = self.engine.session
        blueprint = session.blueprint
        blueprint_title = blueprint.title if blueprint else "(none)"
        blueprint_summary = blueprint.summary if blueprint else "(none)"
        criteria = (
            "\n".join(f"- {item}" for item in blueprint.acceptance_criteria)
            if blueprint and blueprint.acceptance_criteria
            else "- none"
        )
        decisions = (
            "\n".join(f"- {item.id}: {item.decision}" for item in session.decisions)
            or "- none"
        )
        return (
            "Continue the existing workflow instead of starting a new one.\n\n"
            f"Original goal:\n{session.goal}\n\n"
            f"{self._target_workspace_prompt_block()}"
            "Current approved blueprint:\n"
            f"- Title: {blueprint_title}\n"
            f"- Summary: {blueprint_summary}\n"
            f"- Acceptance Criteria:\n{criteria}\n\n"
            f"User follow-up instruction:\n{instruction}\n\n"
            f"Recorded decisions:\n{decisions}\n\n"
            "Revise or confirm the blueprint using the user's follow-up. "
            "If the user is asking for implementation, produce an executable "
            "final blueprint and approve it. Preserve or regenerate a complete "
            "work package graph with owners, dependencies, expected files, "
            "acceptance criteria, risk, and parallelization metadata. If more "
            "user input is required, raise OPEN QUESTIONS."
        )

    def _build_blueprint_continuation_prompt(self, instruction: str) -> str:
        return self.build_blueprint_continuation_prompt(instruction)

    def _target_workspace_prompt_block(self) -> str:
        target = self.engine.session.target_workspace
        if target is None:
            return ""
        return (
            "Target Workspace Context:\n"
            f"- Target workspace: {target}\n"
            "- Scope project file references and implementation artifacts to this "
            "workspace.\n"
            "- The Trinity control repository is orchestration state unless it "
            "was explicitly selected as the target workspace.\n\n"
        )
