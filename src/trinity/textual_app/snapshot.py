"""Read-only workflow snapshot projection for Textual screens."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

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


@dataclass(frozen=True)
class QuestionSnapshot:
    """Projected user question for interactive synthesis."""

    id: str
    question: str
    options: list[str] = field(default_factory=list)
    recommended_option: str = ""


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
    work_packages: list[str] = field(default_factory=list)
    execution_log: list[str] = field(default_factory=list)


class NexusSnapshotAdapter:
    """Build a read-only Nexus snapshot from persisted Trinity state."""

    def __init__(self, config: TrinityConfig) -> None:
        self.config = config
        self.persistence = WorkflowPersistence(config.effective_state_dir)
        self.shared = SharedContextEngine(config.shared_context_path)

    def load_snapshot(
        self,
        recent_events: Iterable[TUIEvent] = (),
    ) -> WorkflowNexusSnapshot:
        """Load a snapshot without mutating workflow/session state."""
        session = self.persistence.load()
        provider_states = self._provider_states(session)
        self._fold_recent_events(provider_states, recent_events)

        return WorkflowNexusSnapshot(
            session_id=session.id if session else "",
            goal=session.goal if session else "",
            state=session.state.value if session else "idle",
            round_num=session.current_round if session else 0,
            providers=list(provider_states.values()),
            synthesis=self._synthesis(session),
            questions=[
                QuestionSnapshot(
                    id=q.id,
                    question=q.question,
                    options=list(q.options),
                    recommended_option=q.recommended_option or "",
                )
                for q in session.open_questions
            ]
            if session
            else [],
            decisions=[d.decision for d in session.decisions] if session else [],
            work_packages=[
                f"{package.id} {package.owner_agent}: {package.title} ({package.status.value})"
                for package in session.work_packages
            ]
            if session
            else [],
            execution_log=self._execution_log(session),
        )

    def _provider_states(
        self,
        session: WorkflowSession | None,
    ) -> dict[str, ProviderSnapshot]:
        active = set(session.active_agents) if session else set()
        states: dict[str, ProviderSnapshot] = {}
        for name, spec in self.config.agents.items():
            enabled = spec.enabled
            if session and session.active_agents:
                enabled = name in active
            states[name] = ProviderSnapshot(
                name=name,
                provider=spec.provider.value,
                enabled=enabled,
                status="Queued" if enabled else "Disabled",
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

    def _synthesis(self, session: WorkflowSession | None) -> SynthesisSnapshot:
        if session and session.blueprint:
            return SynthesisSnapshot(
                summary=session.blueprint.summary,
                consensus_progress="blueprint ready",
                source="workflow",
            )

        round_num = session.current_round if session else 0
        if round_num:
            section = self.shared.read_section(f"Round {round_num} Synthesis")
            if section:
                return SynthesisSnapshot(
                    summary=section.strip(),
                    consensus_progress=f"round {round_num}",
                    source="shared.md",
                )

        agreed = self.shared.read_section("Agreed Conclusion")
        if agreed:
            return SynthesisSnapshot(
                summary=agreed.strip(),
                consensus_progress="agreed",
                source="shared.md",
            )

        return SynthesisSnapshot()

    def _execution_log(self, session: WorkflowSession | None) -> list[str]:
        lines: list[str] = []
        for event in self.persistence.load_events()[-20:]:
            event_name = str(event.get("event", "event"))
            state = str(event.get("state", ""))
            if state:
                lines.append(f"{event_name}: {state}")
            else:
                lines.append(event_name)

        if session:
            for result in session.execution_results[-10:]:
                lines.append(
                    f"{result.package_id} {result.agent_name}: {result.status.value}"
                )
        return lines

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
