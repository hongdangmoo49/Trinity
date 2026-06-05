"""Tests for TrinityTUI deliberation state tracking."""

from trinity.tui.app import TrinityTUI
from trinity.tui.events import TUIEvent, TUIEventType


def _make_config():
    """Create minimal config for testing."""
    from trinity.config import TrinityConfig
    config = TrinityConfig.__new__(TrinityConfig)
    config.agents = {}
    config.max_deliberation_rounds = 5
    config.session_name = "test"
    config.caveman_mode = False
    config.caveman_intensity = "off"
    return config


def test_initial_state():
    """Initial deliberation state should be inactive."""
    tui = TrinityTUI(_make_config())
    assert tui.deliberation_active is False
    assert tui.deliberation_prompt == ""
    assert tui.current_phase == ""
    assert tui.progress_completed == 0
    assert tui.progress_total == 0


def test_consume_deliberation_started():
    """DELIBERATION_STARTED should activate deliberation state."""
    tui = TrinityTUI(_make_config())
    tui.consume_event(TUIEvent(
        type=TUIEventType.DELIBERATION_STARTED,
        data={"prompt": "test question"},
    ))
    assert tui.deliberation_active is True
    assert tui.deliberation_prompt == "test question"
    assert tui.current_phase == "opinions"
    assert tui.phase_started_at > 0


def test_consume_deliberation_phase():
    """DELIBERATION_PHASE should update current phase."""
    tui = TrinityTUI(_make_config())
    tui.consume_event(TUIEvent(
        type=TUIEventType.DELIBERATION_PHASE,
        data={"phase": "consensus", "round_num": 1},
    ))
    assert tui.current_phase == "consensus"


def test_consume_deliberation_progress():
    """DELIBERATION_PROGRESS should update completion counter."""
    tui = TrinityTUI(_make_config())
    tui.consume_event(TUIEvent(
        type=TUIEventType.DELIBERATION_PROGRESS,
        data={"completed": 2, "total": 3, "round_num": 1},
    ))
    assert tui.progress_completed == 2
    assert tui.progress_total == 3


def test_deliberation_done_resets_state():
    """DELIBERATION_DONE should reset all deliberation state."""
    tui = TrinityTUI(_make_config())
    tui.deliberation_active = True
    tui.current_phase = "consensus"
    tui.progress_completed = 2
    tui.progress_total = 3
    tui.consume_event(TUIEvent(type=TUIEventType.DELIBERATION_DONE, data={}))
    assert tui.deliberation_active is False
    assert tui.current_phase == ""
    assert tui.progress_completed == 0
    assert tui.progress_total == 0
