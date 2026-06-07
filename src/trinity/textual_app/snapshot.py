"""Read-only workflow snapshot projection for Textual screens."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from trinity.config import TrinityConfig
from trinity.context.shared import SharedContextEngine
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.workflow import WorkflowPersistence, WorkflowSession


@dataclass(frozen=True)
class ProviderSnapshot:
    """Projected provider state for Textual UI."""

    name: str
    provider: str
    enabled: bool
    status: str
    summary: str = ""
    readiness: str = "unknown"
    readiness_reason: str = ""
    raw_output: str = ""


@dataclass(frozen=True)
class SynthesisSnapshot:
    """Projected central synthesis state."""

    summary: str = ""
    consensus_progress: str = ""
    source: str = "none"
    status: str = "idle"


@dataclass(frozen=True)
class QuestionSnapshot:
    """Projected user question for interactive synthesis."""

    id: str
    question: str
    options: list[str] = field(default_factory=list)
    recommended_option: str = ""
    status: str = "open"
    answer: str = ""


@dataclass(frozen=True)
class SubtaskSnapshot:
    """Projected provider-internal delegation result."""

    id: str
    parent_package_id: str
    parent_agent: str
    delegated_to: str
    objective: str
    result_summary: str
    status: str


@dataclass(frozen=True)
class LocalCommandSnapshot:
    """A locally handled slash command result for Textual display."""

    command: str
    title: str
    body: str
    severity: str = "info"
    result_kind: str = "markdown"
    empty: bool = False
    action_hint: str = ""
    table_columns: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class WorkflowNexusSnapshot:
    """Read-only UI projection of the current workflow."""

    session_id: str = ""
    goal: str = ""
    state: str = "idle"
    round_num: int = 0
    providers: list[ProviderSnapshot] = field(default_factory=list)
    synthesis: SynthesisSnapshot = field(default_factory=SynthesisSnapshot)
    questions: list[QuestionSnapshot] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    central_work_packages: list[str] = field(default_factory=list)
    work_packages: list[str] = field(default_factory=list)
    subtasks: list[SubtaskSnapshot] = field(default_factory=list)
    work_package_repairs: list[str] = field(default_factory=list)
    execution_log: list[str] = field(default_factory=list)
    local_commands: list[LocalCommandSnapshot] = field(default_factory=list)


class NexusSnapshotAdapter:
    """Build a read-only Nexus snapshot from persisted Trinity state."""

    def __init__(self, config: TrinityConfig) -> None:
        self.config = config
        self.persistence = WorkflowPersistence(config.effective_state_dir)
        self.shared = SharedContextEngine(config.shared_context_path)

    def new_session_snapshot(self, goal: str) -> WorkflowNexusSnapshot:
        """Create a fresh in-memory snapshot for a newly submitted UI prompt."""
        return WorkflowNexusSnapshot(
            session_id=f"wf-{uuid4().hex[:12]}",
            goal=goal.strip(),
            state="preflight",
            providers=list(self._provider_states(None).values()),
        )

    def load_snapshot(
        self,
        recent_events: Iterable[TUIEvent] = (),
    ) -> WorkflowNexusSnapshot:
        """Load a snapshot without mutating workflow/session state."""
        session = self.persistence.load()
        recent = list(recent_events)
        provider_states = self._provider_states(session)
        self._fold_recent_events(provider_states, recent)
        round_num = self._round_num(session, recent)

        return WorkflowNexusSnapshot(
            session_id=session.id if session else "",
            goal=session.goal if session else "",
            state=session.state.value if session else "idle",
            round_num=round_num,
            providers=list(provider_states.values()),
            synthesis=self._synthesis(session, recent, round_num),
            questions=self._questions(session),
            decisions=[d.decision for d in session.decisions] if session else [],
            central_work_packages=self._central_work_packages(session),
            work_packages=[
                f"{package.id} {package.owner_agent}: {package.title} ({package.status.value})"
                for package in session.work_packages
            ]
            if session
            else [],
            subtasks=self._subtasks(session),
            work_package_repairs=self._work_package_repairs(session),
            execution_log=self._execution_log(session),
        )

    @staticmethod
    def _central_work_packages(session: WorkflowSession | None) -> list[str]:
        if session is None or session.blueprint is None:
            return []
        return [
            NexusSnapshotAdapter._format_central_package(package)
            for package in session.blueprint.work_packages
        ]

    @staticmethod
    def _work_package_repairs(session: WorkflowSession | None) -> list[str]:
        if session is None:
            return []
        repairs: list[str] = []
        for package in session.work_packages:
            for note in package.repair_notes:
                repairs.append(f"{package.id}: {note}")
        return repairs

    @staticmethod
    def _subtasks(session: WorkflowSession | None) -> list[SubtaskSnapshot]:
        if session is None:
            return []

        subtasks: list[SubtaskSnapshot] = []
        seen: set[tuple[str, str, str]] = set()

        def add(subtask: object) -> None:
            subtask_id = str(getattr(subtask, "id", "")).strip()
            parent_package_id = str(
                getattr(subtask, "parent_package_id", "")
            ).strip()
            parent_agent = str(getattr(subtask, "parent_agent", "")).strip()
            key = (subtask_id, parent_package_id, parent_agent)
            if key in seen:
                return
            seen.add(key)
            status = getattr(getattr(subtask, "status", ""), "value", "")
            if not status:
                status = getattr(subtask, "status", "")
            subtasks.append(
                SubtaskSnapshot(
                    id=subtask_id,
                    parent_package_id=parent_package_id,
                    parent_agent=parent_agent,
                    delegated_to=str(getattr(subtask, "delegated_to", "")).strip(),
                    objective=str(getattr(subtask, "objective", "")).strip(),
                    result_summary=str(
                        getattr(subtask, "result_summary", "")
                    ).strip(),
                    status=str(status).strip() or "unknown",
                )
            )

        for subtask in session.subtask_results:
            add(subtask)
        for result in session.execution_results:
            for subtask in result.subtasks:
                add(subtask)
        return subtasks

    @staticmethod
    def _format_central_package(package: object) -> str:
        package_id = str(getattr(package, "id", "")).strip()
        owner = str(getattr(package, "owner_agent", "")).strip() or "unassigned"
        title = str(getattr(package, "title", "")).strip() or "Untitled package"
        dependencies = [
            str(item).strip()
            for item in getattr(package, "dependencies", [])
            if str(item).strip()
        ]
        expected_files = [
            str(item).strip()
            for item in getattr(package, "expected_files", [])
            if str(item).strip()
        ]
        details = [
            f"deps={','.join(dependencies) if dependencies else '-'}",
            f"files={','.join(expected_files) if expected_files else '-'}",
        ]
        prefix = f"{package_id} " if package_id else ""
        return f"{prefix}{owner}: {title} ({'; '.join(details)})"

    @staticmethod
    def _questions(session: WorkflowSession | None) -> list[QuestionSnapshot]:
        if session is None:
            return []
        answer_by_question_id = {
            str(decision.question_id): decision.decision
            for decision in session.decisions
            if decision.question_id
        }
        return [
            QuestionSnapshot(
                id=q.id,
                question=q.question,
                options=list(q.options),
                recommended_option=q.recommended_option or "",
                status=q.status,
                answer=answer_by_question_id.get(q.id, ""),
            )
            for q in session.pending_questions
        ]

    def _provider_states(
        self,
        session: WorkflowSession | None,
    ) -> dict[str, ProviderSnapshot]:
        active = set(session.active_agents) if session else set()
        artifacts = self._latest_response_artifacts(session)
        states: dict[str, ProviderSnapshot] = {}
        for name, spec in self.config.agents.items():
            enabled = spec.enabled
            if session and session.active_agents:
                enabled = name in active
            artifact = artifacts.get(name)
            summary = ""
            raw_output = ""
            status = "Queued" if enabled else "Disabled"
            if enabled and artifact is not None:
                clean_output = self._read_artifact_text(artifact[0])
                raw_output = self._read_artifact_text(artifact[1]) or clean_output
                summary = self._short_summary(clean_output or raw_output)
                status = "Ready"
            elif enabled and session and session.state.value == "deliberating":
                status = "Running"
            states[name] = ProviderSnapshot(
                name=name,
                provider=spec.provider.value,
                enabled=enabled,
                status=status,
                summary=summary,
                raw_output=raw_output,
            )
        return states

    def _fold_recent_events(
        self,
        states: dict[str, ProviderSnapshot],
        recent_events: Iterable[TUIEvent],
    ) -> None:
        for event in recent_events:
            data = event.data
            agent = str(data.get("agent", ""))
            if not agent or agent not in states:
                continue

            current = states[agent]
            if event.type == TUIEventType.AGENT_THINKING:
                states[agent] = self._replace(current, status="Running")
            elif event.type == TUIEventType.AGENT_RESPONDED:
                content = str(data.get("content", ""))
                states[agent] = self._replace(
                    current,
                    status="Ready",
                    summary=self._short_summary(content),
                    raw_output=content,
                )
            elif event.type == TUIEventType.AGENT_ERROR:
                error = str(data.get("error", ""))
                states[agent] = self._replace(
                    current,
                    status="Error",
                    summary=self._short_summary(error),
                    raw_output=error,
                )
            elif event.type == TUIEventType.PROVIDER_READINESS:
                states[agent] = self._replace(
                    current,
                    readiness=str(data.get("state", "unknown")),
                    readiness_reason=str(data.get("reason", "")),
                )

    def _synthesis(
        self,
        session: WorkflowSession | None,
        recent_events: list[TUIEvent],
        round_num: int,
    ) -> SynthesisSnapshot:
        if session and session.blueprint:
            return SynthesisSnapshot(
                summary=session.blueprint.summary,
                consensus_progress="blueprint ready",
                source="workflow",
                status="ready",
            )

        event_synthesis = self._synthesis_from_events(recent_events)
        if event_synthesis is not None:
            return event_synthesis

        if session is None or not self._has_workflow_context(session):
            return SynthesisSnapshot()

        if round_num:
            section = self.shared.read_section(f"Round {round_num} Synthesis")
            if section:
                return SynthesisSnapshot(
                    summary=section.strip(),
                    consensus_progress=f"round {round_num}",
                    source="shared.md",
                    status="ready",
                )

        agreed = self.shared.read_section("Agreed Conclusion")
        if agreed:
            return SynthesisSnapshot(
                summary=agreed.strip(),
                consensus_progress="agreed",
                source="shared.md",
                status="ready",
            )

        if session and session.state.value == "deliberating":
            active_round = round_num or 1
            return SynthesisSnapshot(
                summary=f"Collecting provider responses for round {active_round}.",
                consensus_progress=f"round {active_round} collecting",
                source="runtime",
                status="waiting",
            )

        return SynthesisSnapshot()

    @staticmethod
    def _has_workflow_context(session: WorkflowSession) -> bool:
        """Return whether a persisted session should project shared synthesis."""
        return bool(
            session.goal
            or session.current_round
            or session.active_agents
            or session.blueprint
            or session.open_questions
            or session.decisions
            or session.work_packages
            or session.subtask_results
            or session.review_packages
        )

    def _round_num(
        self,
        session: WorkflowSession | None,
        recent_events: list[TUIEvent],
    ) -> int:
        current = session.current_round if session else 0
        for event in recent_events:
            value = event.data.get("round_num")
            try:
                current = max(current, int(value))
            except (TypeError, ValueError):
                continue
        if current == 0 and session and session.state.value == "deliberating":
            current = 1
        return current

    def _synthesis_from_events(
        self,
        recent_events: list[TUIEvent],
    ) -> SynthesisSnapshot | None:
        synthesis: SynthesisSnapshot | None = None
        for event in recent_events:
            data = event.data
            if event.type == TUIEventType.ROUND_START:
                round_num = self._event_round(data)
                synthesis = SynthesisSnapshot(
                    summary=f"Collecting provider responses for round {round_num}.",
                    consensus_progress=f"round {round_num} collecting",
                    source="runtime",
                    status="waiting",
                )
            elif event.type == TUIEventType.CONSENSUS_CHECKING:
                round_num = self._event_round(data)
                synthesis = SynthesisSnapshot(
                    summary=(
                        f"Central agent is synthesizing round {round_num} "
                        "provider responses."
                    ),
                    consensus_progress=f"round {round_num} synthesizing",
                    source="runtime",
                    status="running",
                )
            elif event.type == TUIEventType.CONSENSUS_RESULT:
                round_num = self._event_round(data)
                summary = str(data.get("summary", "")).strip()
                reached = bool(data.get("reached", False))
                agreement = self._event_int(data.get("agreement_count"))
                total = self._event_int(data.get("total_agents"))
                vote_text = f"{agreement}/{total}" if total else "0/0"
                state_text = "reached" if reached else "not reached"
                if not summary:
                    summary = (
                        f"Round {round_num} consensus {state_text} "
                        f"({vote_text})."
                    )
                fallback_reason = str(data.get("fallback_reason", "")).strip()
                if fallback_reason:
                    summary = f"{summary}\n\nSynthesis fallback: {fallback_reason}"
                source = str(data.get("synthesis_source", "runtime")) or "runtime"
                progress = f"round {round_num} consensus {state_text} ({vote_text})"
                if bool(data.get("fallback_used", False)):
                    progress = f"{progress}; fallback used"
                synthesis = SynthesisSnapshot(
                    summary=summary,
                    consensus_progress=progress,
                    source=source,
                    status="ready",
                )
        return synthesis

    @staticmethod
    def _event_round(data: dict[str, object]) -> int:
        return NexusSnapshotAdapter._event_int(data.get("round_num")) or 1

    @staticmethod
    def _event_int(value: object) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _execution_log(self, session: WorkflowSession | None) -> list[str]:
        if session is None:
            return []

        lines: list[str] = []
        session_events = [
            event
            for event in self.persistence.load_events()
            if str(event.get("workflow_id", "")) == session.id
        ]
        completed_event_package_ids = {
            self._event_package_id(event)
            for event in session_events
            if str(event.get("event", "")) == "work_package_completed"
        }
        display_events = session_events[-80:]
        displayed_finished_package_ids: set[str] = set()
        for event in display_events:
            event_name = str(event.get("event", ""))
            package_id = self._event_package_id(event)
            if (
                event_name == "execution_result_recorded"
                and package_id in completed_event_package_ids
            ):
                continue
            lines.append(self._format_execution_event(event))
            if event_name in {"work_package_completed", "execution_result_recorded"}:
                displayed_finished_package_ids.add(package_id)

        if session:
            for result in session.execution_results[-10:]:
                if str(getattr(result, "package_id", "")) in displayed_finished_package_ids:
                    continue
                lines.append(self._format_execution_result(result))
        return lines

    @staticmethod
    def _format_execution_result(result: object) -> str:
        package_id = str(getattr(result, "package_id", "")).strip()
        agent = str(getattr(result, "agent_name", "")).strip()
        status = str(getattr(getattr(result, "status", ""), "value", "")).strip()
        if not status:
            status = str(getattr(result, "status", "")).strip()
        details = " ".join(part for part in (package_id, agent) if part)
        line = f"{details}: {status}" if details else status
        blockers = getattr(result, "blockers", []) or []
        reason = ""
        if blockers:
            reason = str(blockers[0]).strip()
        if not reason:
            reason = str(getattr(result, "summary", "")).strip()
        if reason and status in {"failed", "blocked"}:
            line = f"{line} - {NexusSnapshotAdapter._short_summary(reason, limit=120)}"
        return line

    @staticmethod
    def _format_execution_event(event: dict[str, object]) -> str:
        event_name = str(event.get("event", "event"))
        state = str(event.get("state", ""))
        data = event.get("data", {})
        data = data if isinstance(data, dict) else {}
        prefix = NexusSnapshotAdapter._format_event_timestamp(event)

        if event_name == "work_package_started":
            package_id = str(data.get("package_id", "")).strip()
            agent = str(data.get("agent", "")).strip()
            status = str(data.get("status", "")).strip()
            details = " ".join(part for part in (package_id, agent, status) if part)
            line = f"{event_name}: {details}" if details else event_name
            return f"{prefix}{line}"

        if event_name in {"work_package_completed", "execution_result_recorded"}:
            package_id = str(data.get("package_id", "")).strip()
            agent = str(data.get("agent", "")).strip()
            status = str(data.get("status", "")).strip()
            summary = str(data.get("summary", "")).strip()
            details = " ".join(part for part in (package_id, agent, status) if part)
            if summary:
                details = f"{details} - {summary}" if details else summary
            line = f"work_package_completed: {details}" if details else event_name
            return f"{prefix}{line}"

        if event_name in {"execution_enabled", "implementation_requested"}:
            packages = data.get("work_packages", [])
            package_count = len(packages) if isinstance(packages, list) else 0
            target = str(data.get("target_workspace", "")).strip()
            if target:
                return f"{prefix}{event_name}: {package_count} packages -> {target}"
            return f"{prefix}{event_name}: {package_count} packages"

        if event_name == "execution_batch_planned":
            batches = data.get("batches", [])
            batch_count = len(batches) if isinstance(batches, list) else 0
            notices = data.get("notices", [])
            notice_count = len(notices) if isinstance(notices, list) else 0
            detail = f"{batch_count} batches"
            if notice_count:
                first_notice = notices[0] if isinstance(notices[0], dict) else {}
                reason = str(first_notice.get("reason", "")).strip()
                detail = f"{detail}; {notice_count} policy notices"
                if reason:
                    detail = f"{detail} - {reason}"
            return f"{prefix}{event_name}: {detail}"

        if event_name == "target_workspace_selected":
            target = str(data.get("target_workspace", "")).strip()
            line = f"{event_name}: {target}" if target else event_name
            return f"{prefix}{line}"

        if state:
            return f"{prefix}{event_name}: {state}"
        return f"{prefix}{event_name}"

    @staticmethod
    def _event_package_id(event: dict[str, object]) -> str:
        data = event.get("data", {})
        data = data if isinstance(data, dict) else {}
        return str(data.get("package_id", "")).strip()

    @staticmethod
    def _format_event_timestamp(event: dict[str, object]) -> str:
        value = event.get("timestamp")
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            return ""
        if timestamp <= 0:
            return ""
        return f"[{datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')}] "

    def _latest_response_artifacts(
        self,
        session: WorkflowSession | None,
    ) -> dict[str, tuple[Path, Path | None]]:
        if session is None or session.current_round <= 0:
            return {}

        round_dir = (
            self.config.effective_state_dir
            / "responses"
            / f"round-{session.current_round:02d}"
        )
        if not round_dir.exists():
            return {}

        cutoff = max(0.0, session.created_at - 1.0)
        artifacts: dict[str, tuple[Path, Path | None]] = {}
        for name in self.config.agents:
            candidates = sorted(
                round_dir.glob(f"{name}-*.clean.txt"),
                key=lambda path: self._mtime(path),
                reverse=True,
            )
            for clean_path in candidates:
                if self._mtime(clean_path) < cutoff:
                    continue
                raw_path = Path(str(clean_path).removesuffix(".clean.txt") + ".raw.txt")
                artifacts[name] = (
                    clean_path,
                    raw_path if raw_path.exists() else None,
                )
                break
        return artifacts

    @staticmethod
    def _mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    @staticmethod
    def _read_artifact_text(path: Path | None, limit: int = 120_000) -> str:
        if path is None:
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text if len(text) <= limit else text[:limit].rstrip() + "\n..."

    @staticmethod
    def _replace(snapshot: ProviderSnapshot, **updates: object) -> ProviderSnapshot:
        data = {
            "name": snapshot.name,
            "provider": snapshot.provider,
            "enabled": snapshot.enabled,
            "status": snapshot.status,
            "summary": snapshot.summary,
            "readiness": snapshot.readiness,
            "readiness_reason": snapshot.readiness_reason,
            "raw_output": snapshot.raw_output,
        }
        data.update(updates)
        return ProviderSnapshot(**data)

    @staticmethod
    def _short_summary(text: str, limit: int = 96) -> str:
        cleaned = " ".join(line.strip() for line in text.splitlines() if line.strip())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 1].rstrip() + "…"
