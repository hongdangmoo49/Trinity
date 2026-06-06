"""Trinity TUI events — thread-safe event bus for real-time TUI updates.

Bridges the async deliberation thread and the main TUI thread:
- Background thread calls bus.emit(event) from within asyncio tasks
- Main thread calls bus.poll() during Rich Live refresh to consume events
- queue.Queue provides thread-safe delivery without locks
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from queue import Queue
from typing import Any


class TUIEventType(str, Enum):
    """Types of events emitted during deliberation."""

    ROUND_START = "round_start"
    AGENT_THINKING = "agent_thinking"
    AGENT_RESPONDED = "agent_responded"
    AGENT_ERROR = "agent_error"
    PROVIDER_READINESS = "provider_readiness"
    CONSENSUS_CHECKING = "consensus_checking"
    CONSENSUS_RESULT = "consensus_result"
    DELIBERATION_STARTED = "deliberation_started"
    DELIBERATION_PHASE = "deliberation_phase"
    DELIBERATION_PROGRESS = "deliberation_progress"
    EXECUTION_START = "execution_start"
    EXECUTION_BATCH_PLANNED = "execution_batch_planned"
    WORK_PACKAGE_STARTED = "work_package_started"
    WORK_PACKAGE_COMPLETED = "work_package_completed"
    EXECUTION_DONE = "execution_done"
    DELIBERATION_DONE = "deliberation_done"


@dataclass
class TUIEvent:
    """A single event emitted during deliberation.

    Attributes:
        type: The event type.
        data: Arbitrary payload depending on event type.
    """

    type: TUIEventType
    data: dict[str, Any] = field(default_factory=dict)


class TUIEventBus:
    """Thread-safe event bus between deliberation and TUI.

    Usage:
        bus = TUIEventBus()
        # From background thread (inside asyncio tasks):
        bus.emit(TUIEvent(type=TUIEventType.AGENT_RESPONDED, data={...}))
        # From main thread (during Live refresh):
        for event in bus.poll():
            tui.consume_event(event)
    """

    def __init__(self) -> None:
        self._queue: Queue[TUIEvent | None] = Queue()

    def emit(self, event: TUIEvent) -> None:
        """Emit an event (thread-safe, non-blocking).

        Args:
            event: The event to emit.
        """
        self._queue.put(event)

    def poll(self) -> list[TUIEvent]:
        """Poll for all pending events (thread-safe, non-blocking).

        Returns:
            List of events emitted since last poll. Empty list if none.
        """
        events: list[TUIEvent] = []
        while not self._queue.empty():
            item = self._queue.get_nowait()
            if item is not None:
                events.append(item)
        return events
