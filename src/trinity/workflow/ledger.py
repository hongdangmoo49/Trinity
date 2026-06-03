"""Human-readable markdown renderer for the shared workflow ledger."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from trinity.workflow.models import (
    DecisionRecord,
    ExecutionResult,
    OpenQuestion,
    SubtaskResult,
    WorkPackage,
    WorkflowSession,
)


ReadinessInput = Mapping[str, Any] | Iterable[Any] | None


@dataclass(frozen=True)
class _ReadinessView:
    agent_name: str
    provider: str
    ready: str
    state: str
    reason: str
    action_hint: str
    excerpt: str


class SharedLedgerRenderer:
    """Render structured workflow state into the v0.7.0 shared.md layout."""

    def __init__(self, empty_marker: str = "(none)"):
        self.empty_marker = empty_marker

    def render(
        self,
        session: WorkflowSession,
        provider_readiness: ReadinessInput = None,
        *,
        round_opinions: str | Iterable[str] = "",
        response_diagnostics: str | Iterable[str] = "",
        session_history: str | Iterable[str] = "",
    ) -> str:
        """Render a complete shared ledger markdown document."""
        lines = ["# Shared Context", ""]
        self._append_section(lines, "Current Goal", self._render_current_goal(session))
        self._append_section(lines, "Workflow State", self._render_workflow_state(session))
        self._append_section(
            lines,
            "Provider Readiness",
            self._render_provider_readiness(provider_readiness),
        )
        self._append_section(lines, "Decisions", self._render_decisions(session.decisions))
        self._append_section(
            lines,
            "Open Questions",
            self._render_open_questions(session.open_questions),
        )
        self._append_section(lines, "Blueprint", self._render_blueprint(session.blueprint))
        self._append_section(
            lines,
            "Work Packages",
            self._render_work_packages(session.work_packages),
        )
        self._append_section(
            lines,
            "Task Results",
            self._render_task_results(session.execution_results),
        )
        self._append_section(lines, "Subtasks", self._render_subtasks(session))
        self._append_section(lines, "Round Opinions", self._render_freeform(round_opinions))
        self._append_section(
            lines,
            "Response Diagnostics",
            self._render_freeform(response_diagnostics),
        )
        self._append_section(lines, "Session History", self._render_freeform(session_history))
        return "\n".join(lines).rstrip() + "\n"

    def _append_section(self, lines: list[str], title: str, body: list[str]) -> None:
        lines.append(f"## {title}")
        lines.extend(body or [self.empty_marker])
        lines.append("")

    def _render_current_goal(self, session: WorkflowSession) -> list[str]:
        return [self._inline(session.goal)]

    def _render_workflow_state(self, session: WorkflowSession) -> list[str]:
        return [
            f"- id: {self._inline(session.id)}",
            f"- state: {self._inline(session.state)}",
            f"- current_round: {session.current_round}",
            f"- active_agents: {self._join(session.active_agents)}",
        ]

    def _render_provider_readiness(self, readiness: ReadinessInput) -> list[str]:
        results = self._normalize_readiness(readiness)
        if not results:
            return [self.empty_marker]

        lines: list[str] = []
        for result in results:
            if lines:
                lines.append("")
            lines.append(f"### {result.agent_name}")
            lines.append(f"- provider: {self._inline(result.provider)}")
            lines.append(f"- ready: {self._inline(result.ready)}")
            lines.append(f"- state: {self._inline(result.state)}")
            if result.reason:
                lines.append(f"- reason: {self._inline(result.reason)}")
            if result.action_hint:
                lines.append(f"- action_hint: {self._inline(result.action_hint)}")
            if result.excerpt:
                lines.extend(["", "#### Excerpt", "```text"])
                lines.extend(self._fence_text(result.excerpt).splitlines())
                lines.append("```")
        return lines

    def _render_decisions(self, decisions: Iterable[DecisionRecord]) -> list[str]:
        records = list(decisions)
        if not records:
            return [self.empty_marker]

        lines: list[str] = []
        for index, decision in enumerate(records, start=1):
            if lines:
                lines.append("")
            decision_id = self._text(self._field(decision, "id")) or f"Decision {index}"
            lines.append(f"### {decision_id}")
            question_id = self._text(self._field(decision, "question_id"))
            if question_id:
                lines.append(f"- question_id: {question_id}")
            lines.append(f"- decided_by: {self._inline(self._field(decision, 'decided_by'))}")
            lines.append(f"- decision: {self._inline(self._field(decision, 'decision'))}")
            rationale = self._text(self._field(decision, "rationale"))
            if rationale:
                lines.append(f"- rationale: {rationale}")
            timestamp = self._format_timestamp(self._field(decision, "timestamp"))
            if timestamp:
                lines.append(f"- timestamp: {timestamp}")
        return lines

    def _render_open_questions(self, questions: Iterable[OpenQuestion]) -> list[str]:
        records = list(questions)
        if not records:
            return [self.empty_marker]

        lines: list[str] = []
        for index, question in enumerate(records, start=1):
            if lines:
                lines.append("")
            question_id = self._text(self._field(question, "id")) or f"Question {index}"
            lines.append(f"### {question_id}")
            lines.append(f"- status: {self._inline(self._field(question, 'status'))}")
            lines.append(f"- question: {self._inline(self._field(question, 'question'))}")
            lines.append(f"- options: {self._join(self._field(question, 'options', []))}")
            lines.append(
                f"- recommendation: {self._inline(self._field(question, 'recommended_option'))}"
            )
            lines.append(f"- blocking: {self._inline(self._field(question, 'blocking'))}")
            raised_by = self._join(self._field(question, "raised_by", []))
            if raised_by != self.empty_marker:
                lines.append(f"- raised_by: {raised_by}")
            rationale = self._text(self._field(question, "rationale"))
            if rationale:
                lines.append(f"- rationale: {rationale}")
        return lines

    def _render_blueprint(self, blueprint: Any) -> list[str]:
        data = self._mapping(blueprint)
        if not data:
            return [self.empty_marker]

        lines: list[str] = []
        title = self._text(data.get("title"))
        summary = self._text(data.get("summary"))
        if title:
            lines.append(f"### {title}")
        if summary:
            if lines:
                lines.append("")
            lines.extend(["#### Summary", summary])

        architecture = self._items(data.get("architecture", []))
        if architecture:
            lines.extend(["", "#### Architecture"])
            for index, component in enumerate(architecture, start=1):
                lines.append(self._render_architecture_component(component, index))

        self._append_block_list(lines, "Data Flow", data.get("data_flow", []))
        self._append_block_list(
            lines,
            "External Dependencies",
            data.get("external_dependencies", []),
        )

        risks = self._items(data.get("risks", []))
        if risks:
            lines.extend(["", "#### Risks"])
            for risk in risks:
                lines.append(self._render_risk(risk))

        self._append_block_list(
            lines,
            "Acceptance Criteria",
            data.get("acceptance_criteria", []),
        )

        questions = self._items(data.get("open_questions", []))
        if questions:
            lines.extend(["", "#### Open Questions"])
            for question in questions:
                lines.append(self._render_blueprint_question(question))

        return lines or [self.empty_marker]

    def _render_work_packages(self, packages: Iterable[WorkPackage]) -> list[str]:
        records = list(packages)
        if not records:
            return [self.empty_marker]

        lines: list[str] = []
        for package in records:
            if lines:
                lines.append("")
            package_id = self._text(self._field(package, "id"))
            title = self._text(self._field(package, "title"))
            heading = package_id or title or "Work Package"
            if package_id and title:
                heading = f"{package_id}: {title}"
            lines.append(f"### {heading}")
            lines.append(f"- owner: {self._inline(self._field(package, 'owner_agent'))}")
            lines.append(f"- status: {self._inline(self._field(package, 'status'))}")
            lines.append(f"- objective: {self._inline(self._field(package, 'objective'))}")
            lines.append(
                f"- requires_execution: {self._inline(self._field(package, 'requires_execution'))}"
            )
            self._append_keyed_list(lines, "scope", self._field(package, "scope", []))
            self._append_keyed_list(
                lines,
                "out_of_scope",
                self._field(package, "out_of_scope", []),
            )
            self._append_keyed_list(
                lines,
                "dependencies",
                self._field(package, "dependencies", []),
            )
            self._append_keyed_list(
                lines,
                "expected_files",
                self._field(package, "expected_files", []),
            )
            self._append_keyed_list(
                lines,
                "acceptance",
                self._field(package, "acceptance_criteria", []),
            )
        return lines

    def _render_task_results(self, results: Iterable[ExecutionResult]) -> list[str]:
        records = list(results)
        if not records:
            return [self.empty_marker]

        lines: list[str] = []
        for result in records:
            if lines:
                lines.append("")
            package_id = self._inline(self._field(result, "package_id"))
            agent = self._inline(self._field(result, "agent_name"))
            lines.append(f"### {package_id} / {agent}")
            lines.append(f"- status: {self._inline(self._field(result, 'status'))}")
            summary = self._text(self._field(result, "summary"))
            if summary:
                lines.append(f"- summary: {summary}")
            raw_response_path = self._text(self._field(result, "raw_response_path"))
            if raw_response_path:
                lines.append(f"- raw_response_path: `{raw_response_path}`")
            self._append_keyed_list(
                lines,
                "files_changed",
                self._field(result, "files_changed", []),
            )
            self._append_decision_list(
                lines,
                "decisions_made",
                self._field(result, "decisions_made", []),
            )
            self._append_keyed_list(lines, "blockers", self._field(result, "blockers", []))
            self._append_keyed_list(lines, "follow_up", self._field(result, "follow_up", []))
            self._append_subtask_summary_list(
                lines,
                self._field(result, "subtasks", []),
            )
        return lines

    def _render_subtasks(self, session: WorkflowSession) -> list[str]:
        subtasks = self._collect_subtasks(session)
        if not subtasks:
            return [self.empty_marker]

        lines: list[str] = []
        for subtask in subtasks:
            if lines:
                lines.append("")
            subtask_id = self._inline(self._field(subtask, "id"))
            package_id = self._inline(self._field(subtask, "parent_package_id"))
            lines.append(f"### {subtask_id} / {package_id}")
            lines.append(f"- parent_agent: {self._inline(self._field(subtask, 'parent_agent'))}")
            lines.append(f"- delegated_to: {self._inline(self._field(subtask, 'delegated_to'))}")
            lines.append(f"- status: {self._inline(self._field(subtask, 'status'))}")
            objective = self._text(self._field(subtask, "objective"))
            if objective:
                lines.append(f"- objective: {objective}")
            summary = self._text(self._field(subtask, "result_summary"))
            if summary:
                lines.append(f"- result_summary: {summary}")
            self._append_keyed_list(
                lines,
                "decisions_made",
                self._field(subtask, "decisions_made", []),
            )
            self._append_keyed_list(
                lines,
                "files_changed",
                self._field(subtask, "files_changed", []),
            )
            self._append_keyed_list(
                lines,
                "unresolved_issues",
                self._field(subtask, "unresolved_issues", []),
            )
        return lines

    def _render_freeform(self, value: str | Iterable[str]) -> list[str]:
        if isinstance(value, str):
            text = self._block_text(value)
            return text.splitlines() if text else [self.empty_marker]
        items = self._clean_items(value)
        return [f"- {item}" for item in items] if items else [self.empty_marker]

    def _normalize_readiness(self, readiness: ReadinessInput) -> list[_ReadinessView]:
        if readiness is None:
            return []

        if isinstance(readiness, Mapping):
            pairs = list(readiness.items())
        else:
            pairs = [(None, item) for item in readiness]

        results: list[_ReadinessView] = []
        for key, item in pairs:
            agent_name = (
                self._text(self._field(item, "agent_name"))
                or self._text(key)
                or self._text(self._field(item, "provider"))
                or "unknown"
            )
            results.append(
                _ReadinessView(
                    agent_name=agent_name,
                    provider=self._text(self._field(item, "provider")),
                    ready=self._inline(self._field(item, "ready")),
                    state=self._text(self._field(item, "state")),
                    reason=self._text(self._field(item, "reason")),
                    action_hint=self._text(self._field(item, "action_hint")),
                    excerpt=self._block_text(self._field(item, "excerpt")),
                )
            )
        return results

    def _render_architecture_component(self, component: Any, index: int) -> str:
        name = self._text(self._field(component, "name")) or f"Component {index}"
        responsibility = self._text(self._field(component, "responsibility"))
        details = []
        owner = self._text(self._field(component, "owner_agent"))
        dependencies = self._join(self._field(component, "dependencies", []))
        if owner:
            details.append(f"owner: {owner}")
        if dependencies != self.empty_marker:
            details.append(f"depends_on: {dependencies}")
        suffix = f" ({'; '.join(details)})" if details else ""
        return f"- {name}: {responsibility}{suffix}" if responsibility else f"- {name}{suffix}"

    def _render_risk(self, risk: Any) -> str:
        severity = self._text(self._field(risk, "severity")) or "medium"
        description = self._inline(self._field(risk, "description"))
        details = []
        mitigation = self._text(self._field(risk, "mitigation"))
        owner = self._text(self._field(risk, "owner_agent"))
        if mitigation:
            details.append(f"mitigation: {mitigation}")
        if owner:
            details.append(f"owner: {owner}")
        suffix = f" ({'; '.join(details)})" if details else ""
        return f"- {severity}: {description}{suffix}"

    def _render_blueprint_question(self, question: Any) -> str:
        question_id = self._text(self._field(question, "id"))
        question_text = self._inline(self._field(question, "question"))
        prefix = f"{question_id}: " if question_id else ""
        return f"- {prefix}{question_text}"

    def _append_block_list(self, lines: list[str], title: str, values: Any) -> None:
        items = self._clean_items(values)
        if not items:
            return
        lines.extend(["", f"#### {title}"])
        lines.extend(f"- {item}" for item in items)

    def _append_keyed_list(self, lines: list[str], key: str, values: Any) -> None:
        items = self._clean_items(values)
        if not items:
            return
        lines.append(f"- {key}:")
        lines.extend(f"  - {item}" for item in items)

    def _append_decision_list(self, lines: list[str], key: str, decisions: Any) -> None:
        items = [self._decision_summary(item) for item in self._items(decisions)]
        items = [item for item in items if item]
        if not items:
            return
        lines.append(f"- {key}:")
        lines.extend(f"  - {item}" for item in items)

    def _append_subtask_summary_list(self, lines: list[str], subtasks: Any) -> None:
        items = []
        for subtask in self._items(subtasks):
            subtask_id = self._text(self._field(subtask, "id"))
            status = self._text(self._field(subtask, "status"))
            summary = self._text(self._field(subtask, "result_summary"))
            pieces = [piece for piece in (subtask_id, summary) if piece]
            if status:
                pieces.append(f"status: {status}")
            if pieces:
                items.append(" - ".join(pieces))
        if not items:
            return
        lines.append("- subtasks:")
        lines.extend(f"  - {item}" for item in items)

    def _decision_summary(self, decision: Any) -> str:
        decision_id = self._text(self._field(decision, "id"))
        decision_text = self._text(self._field(decision, "decision"))
        if decision_id and decision_text:
            return f"{decision_id}: {decision_text}"
        return decision_text or decision_id

    def _collect_subtasks(self, session: WorkflowSession) -> list[SubtaskResult]:
        collected: list[SubtaskResult] = []
        seen: set[tuple[str, str, str]] = set()

        def add(subtask: SubtaskResult) -> None:
            key = (
                self._text(self._field(subtask, "id")),
                self._text(self._field(subtask, "parent_package_id")),
                self._text(self._field(subtask, "parent_agent")),
            )
            if key in seen:
                return
            seen.add(key)
            collected.append(subtask)

        for subtask in session.subtask_results:
            add(subtask)
        for result in session.execution_results:
            for subtask in result.subtasks:
                add(subtask)
        return collected

    def _mapping(self, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return {str(key): item for key, item in value.items()}
        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            data = to_dict()
            if isinstance(data, Mapping):
                return {str(key): item for key, item in data.items()}
        return {}

    def _items(self, values: Any) -> list[Any]:
        if values is None:
            return []
        if isinstance(values, str):
            return [values] if values.strip() else []
        if isinstance(values, Mapping):
            return [values]
        return list(values)

    def _clean_items(self, values: Any) -> list[str]:
        return [text for item in self._items(values) if (text := self._text(item))]

    def _join(self, values: Any) -> str:
        items = self._clean_items(values)
        return ", ".join(items) if items else self.empty_marker

    def _inline(self, value: Any) -> str:
        return self._text(value) or self.empty_marker

    def _text(self, value: Any) -> str:
        value = self._enum_value(value)
        if value is None:
            return ""
        if isinstance(value, bool):
            return "yes" if value else "no"
        return " ".join(str(value).replace("\r\n", "\n").replace("\r", "\n").splitlines()).strip()

    def _block_text(self, value: Any) -> str:
        value = self._enum_value(value)
        if value is None:
            return ""
        return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()

    def _field(self, value: Any, key: str, default: Any = None) -> Any:
        if isinstance(value, Mapping):
            return value.get(key, default)
        return getattr(value, key, default)

    def _enum_value(self, value: Any) -> Any:
        return value.value if isinstance(value, Enum) else value

    def _format_timestamp(self, value: Any) -> str:
        if value in (None, ""):
            return ""
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError, OverflowError):
            return self._text(value)

    def _fence_text(self, value: str) -> str:
        return value.replace("```", "'''")


def render_shared_ledger(
    session: WorkflowSession,
    provider_readiness: ReadinessInput = None,
    **kwargs: Any,
) -> str:
    """Render a shared ledger with the default renderer."""
    return SharedLedgerRenderer().render(session, provider_readiness, **kwargs)


__all__ = ["ReadinessInput", "SharedLedgerRenderer", "render_shared_ledger"]
