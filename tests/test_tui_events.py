"""Tests for TUI event types — deliberation tracking events."""

from trinity.tui.events import TUIEvent, TUIEventBus, TUIEventType


def test_new_event_types_exist():
    """Verify the 3 new deliberation event types are defined with correct string values."""
    assert TUIEventType.DELIBERATION_STARTED.value == "deliberation_started"
    assert TUIEventType.DELIBERATION_PHASE.value == "deliberation_phase"
    assert TUIEventType.DELIBERATION_PROGRESS.value == "deliberation_progress"
    assert TUIEventType.EXECUTION_BATCH_PLANNED.value == "execution_batch_planned"


def test_deliberation_phase_event():
    """Emit a DELIBERATION_PHASE event, poll it, and verify the payload."""
    bus = TUIEventBus()
    phase_data = {"phase": "counter", "round": 2}
    bus.emit(TUIEvent(type=TUIEventType.DELIBERATION_PHASE, data=phase_data))

    events = bus.poll()
    assert len(events) == 1
    assert events[0].type is TUIEventType.DELIBERATION_PHASE
    assert events[0].data == phase_data


def test_deliberation_progress_event():
    """Emit a DELIBERATION_PROGRESS event, poll it, and verify the payload."""
    bus = TUIEventBus()
    progress_data = {"completed": 3, "total": 5}
    bus.emit(TUIEvent(type=TUIEventType.DELIBERATION_PROGRESS, data=progress_data))

    events = bus.poll()
    assert len(events) == 1
    assert events[0].type is TUIEventType.DELIBERATION_PROGRESS
    assert events[0].data == progress_data
