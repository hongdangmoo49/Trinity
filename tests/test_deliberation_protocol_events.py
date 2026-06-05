"""Tests for new deliberation protocol events.

Verifies that DELIBERATION_STARTED, DELIBERATION_PHASE, and DELIBERATION_PROGRESS
events are emitted correctly and can be polled from a TUIEventBus.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trinity.tui.events import TUIEvent, TUIEventBus, TUIEventType


# ---------------------------------------------------------------------------
# Helpers – lightweight protocol construction without real agents or shared ctx
# ---------------------------------------------------------------------------


def _make_protocol(*, max_rounds: int = 1, event_bus: TUIEventBus | None = None):
    """Create a DeliberationProtocol with minimal stubs and an optional event bus."""
    from trinity.deliberation.protocol import DeliberationProtocol

    shared = MagicMock()
    shared.initialize = MagicMock()
    shared.path = MagicMock()
    shared.path.parent = MagicMock()
    shared.path.parent.__truediv__ = MagicMock(return_value=MagicMock())

    agents = {
        "agent-a": MagicMock(),
        "agent-b": MagicMock(),
    }
    for ag in agents.values():
        ag.context_usage = MagicMock(used=0, total=100000)

    callback = event_bus.emit if event_bus else None
    proto = DeliberationProtocol(
        agents=agents,
        shared=shared,
        max_rounds=max_rounds,
        event_callback=callback,
        compression_enabled=False,
    )
    return proto


# ---------------------------------------------------------------------------
# Tests – direct emit & poll via TUIEventBus
# ---------------------------------------------------------------------------


class TestNewEventTypesEmitAndPoll:
    """Verify the 3 new event types round-trip through TUIEventBus."""

    def test_deliberation_started_emitted_and_polled(self):
        bus = TUIEventBus()
        bus.emit(TUIEvent(
            type=TUIEventType.DELIBERATION_STARTED,
            data={"prompt": "What framework should we use?"},
        ))
        events = bus.poll()
        assert len(events) == 1
        event = events[0]
        assert event.type == TUIEventType.DELIBERATION_STARTED
        assert "prompt" in event.data
        assert event.data["prompt"] == "What framework should we use?"

    def test_deliberation_phase_emitted_and_polled(self):
        bus = TUIEventBus()
        bus.emit(TUIEvent(
            type=TUIEventType.DELIBERATION_PHASE,
            data={"phase": "opinions", "round_num": 1},
        ))
        events = bus.poll()
        assert len(events) == 1
        event = events[0]
        assert event.type == TUIEventType.DELIBERATION_PHASE
        assert "phase" in event.data
        assert "round_num" in event.data
        assert event.data["phase"] == "opinions"
        assert event.data["round_num"] == 1

    def test_deliberation_progress_emitted_and_polled(self):
        bus = TUIEventBus()
        bus.emit(TUIEvent(
            type=TUIEventType.DELIBERATION_PROGRESS,
            data={"completed": 2, "total": 5, "round_num": 3},
        ))
        events = bus.poll()
        assert len(events) == 1
        event = events[0]
        assert event.type == TUIEventType.DELIBERATION_PROGRESS
        assert "completed" in event.data
        assert "total" in event.data
        assert "round_num" in event.data
        assert event.data["completed"] == 2
        assert event.data["total"] == 5
        assert event.data["round_num"] == 3

    def test_multiple_events_polled_in_order(self):
        bus = TUIEventBus()
        bus.emit(TUIEvent(type=TUIEventType.DELIBERATION_STARTED, data={"prompt": "test"}))
        bus.emit(TUIEvent(type=TUIEventType.DELIBERATION_PHASE, data={"phase": "opinions", "round_num": 1}))
        bus.emit(TUIEvent(type=TUIEventType.DELIBERATION_PROGRESS, data={"completed": 1, "total": 2, "round_num": 1}))
        events = bus.poll()
        assert len(events) == 3
        assert events[0].type == TUIEventType.DELIBERATION_STARTED
        assert events[1].type == TUIEventType.DELIBERATION_PHASE
        assert events[2].type == TUIEventType.DELIBERATION_PROGRESS


# ---------------------------------------------------------------------------
# Tests – protocol-level emit verification
# ---------------------------------------------------------------------------


class TestProtocolEmits:
    """Verify that DeliberationProtocol.run() emits the new events."""

    @pytest.mark.asyncio
    async def test_deliberation_started_emitted_at_run_start(self):
        """DELIBERATION_STARTED should be the very first event emitted."""
        bus = TUIEventBus()
        proto = _make_protocol(event_bus=bus)

        # Stub _collect_opinions to return empty opinions and short-circuit
        async def fake_collect(round_num, prompt):
            return {}

        proto._collect_opinions = fake_collect
        # Stub synthesis to produce a no-consensus result so the loop runs
        from trinity.deliberation.synthesis import SynthesisResult
        from trinity.models import ConsensusResult

        fake_consensus = ConsensusResult(
            reached=True, agreement_count=1, total_agents=1, opinions={}, summary="ok"
        )
        fake_synthesis = SynthesisResult(
            round_num=1,
            consensus_reached=True,
            agreement_count=1,
            total_agents=1,
            consensus=fake_consensus,
            summary_for_shared_md="ok",
            next_round_prompt="",
            structured_consensus=None,
            metadata={},
            source="heuristic",
        )
        proto.synthesis_agent = AsyncMock()
        proto.synthesis_agent.synthesize.return_value = fake_synthesis

        proto.shared.write_synthesis_summary = MagicMock()
        proto.shared.update_consensus = MagicMock()
        proto.shared.update_tasks = MagicMock()

        await proto.run("test prompt")

        events = bus.poll()
        assert len(events) > 0
        # First event should be DELIBERATION_STARTED
        assert events[0].type == TUIEventType.DELIBERATION_STARTED
        assert events[0].data["prompt"] == "test prompt"

    @pytest.mark.asyncio
    async def test_deliberation_phase_opinions_emitted(self):
        """DELIBERATION_PHASE with phase='opinions' should appear each round."""
        bus = TUIEventBus()
        proto = _make_protocol(event_bus=bus)

        async def fake_collect(round_num, prompt):
            return {}

        proto._collect_opinions = fake_collect

        from trinity.deliberation.synthesis import SynthesisResult
        from trinity.models import ConsensusResult

        fake_consensus = ConsensusResult(
            reached=True, agreement_count=1, total_agents=1, opinions={}, summary="ok"
        )
        fake_synthesis = SynthesisResult(
            round_num=1,
            consensus_reached=True,
            agreement_count=1,
            total_agents=1,
            consensus=fake_consensus,
            summary_for_shared_md="ok",
            next_round_prompt="",
            structured_consensus=None,
            metadata={},
            source="heuristic",
        )
        proto.synthesis_agent = AsyncMock()
        proto.synthesis_agent.synthesize.return_value = fake_synthesis

        proto.shared.write_synthesis_summary = MagicMock()
        proto.shared.update_consensus = MagicMock()
        proto.shared.update_tasks = MagicMock()

        await proto.run("test prompt")

        events = bus.poll()
        phase_opinions = [
            e for e in events
            if e.type == TUIEventType.DELIBERATION_PHASE and e.data.get("phase") == "opinions"
        ]
        assert len(phase_opinions) >= 1
        assert "round_num" in phase_opinions[0].data

    @pytest.mark.asyncio
    async def test_deliberation_phase_consensus_emitted(self):
        """DELIBERATION_PHASE with phase='consensus' should appear each round."""
        bus = TUIEventBus()
        proto = _make_protocol(event_bus=bus)

        async def fake_collect(round_num, prompt):
            return {}

        proto._collect_opinions = fake_collect

        from trinity.deliberation.synthesis import SynthesisResult
        from trinity.models import ConsensusResult

        fake_consensus = ConsensusResult(
            reached=True, agreement_count=1, total_agents=1, opinions={}, summary="ok"
        )
        fake_synthesis = SynthesisResult(
            round_num=1,
            consensus_reached=True,
            agreement_count=1,
            total_agents=1,
            consensus=fake_consensus,
            summary_for_shared_md="ok",
            next_round_prompt="",
            structured_consensus=None,
            metadata={},
            source="heuristic",
        )
        proto.synthesis_agent = AsyncMock()
        proto.synthesis_agent.synthesize.return_value = fake_synthesis

        proto.shared.write_synthesis_summary = MagicMock()
        proto.shared.update_consensus = MagicMock()
        proto.shared.update_tasks = MagicMock()

        await proto.run("test prompt")

        events = bus.poll()
        phase_consensus = [
            e for e in events
            if e.type == TUIEventType.DELIBERATION_PHASE and e.data.get("phase") == "consensus"
        ]
        assert len(phase_consensus) >= 1
        assert "round_num" in phase_consensus[0].data

    @pytest.mark.asyncio
    async def test_deliberation_phase_synthesis_emitted(self):
        """DELIBERATION_PHASE with phase='synthesis' should appear each round."""
        bus = TUIEventBus()
        proto = _make_protocol(event_bus=bus)

        async def fake_collect(round_num, prompt):
            return {}

        proto._collect_opinions = fake_collect

        from trinity.deliberation.synthesis import SynthesisResult
        from trinity.models import ConsensusResult

        fake_consensus = ConsensusResult(
            reached=True, agreement_count=1, total_agents=1, opinions={}, summary="ok"
        )
        fake_synthesis = SynthesisResult(
            round_num=1,
            consensus_reached=True,
            agreement_count=1,
            total_agents=1,
            consensus=fake_consensus,
            summary_for_shared_md="ok",
            next_round_prompt="",
            structured_consensus=None,
            metadata={},
            source="heuristic",
        )
        proto.synthesis_agent = AsyncMock()
        proto.synthesis_agent.synthesize.return_value = fake_synthesis

        proto.shared.write_synthesis_summary = MagicMock()
        proto.shared.update_consensus = MagicMock()
        proto.shared.update_tasks = MagicMock()

        await proto.run("test prompt")

        events = bus.poll()
        phase_synthesis = [
            e for e in events
            if e.type == TUIEventType.DELIBERATION_PHASE and e.data.get("phase") == "synthesis"
        ]
        assert len(phase_synthesis) >= 1
        assert "round_num" in phase_synthesis[0].data

    @pytest.mark.asyncio
    async def test_deliberation_progress_emitted_during_opinion_collection(self):
        """DELIBERATION_PROGRESS events should be emitted as each agent responds."""
        bus = TUIEventBus()
        proto = _make_protocol(event_bus=bus)

        from trinity.models import DeliberationMessage, MessageRole

        # Create mock agent responses
        msg_a = DeliberationMessage(
            source="agent-a", target="all", round_num=1,
            role=MessageRole.OPINION, content="Opinion A",
        )
        msg_b = DeliberationMessage(
            source="agent-b", target="all", round_num=1,
            role=MessageRole.OPINION, content="Opinion B",
        )

        # Mock agents to return sequentially
        call_count = 0

        async def fake_send_and_wait_a(prompt, timeout=None):
            return msg_a

        async def fake_send_and_wait_b(prompt, timeout=None):
            return msg_b

        proto.agents["agent-a"].send_and_wait = fake_send_and_wait_a
        proto.agents["agent-b"].send_and_wait = fake_send_and_wait_b

        from trinity.deliberation.synthesis import SynthesisResult
        from trinity.models import ConsensusResult

        fake_consensus = ConsensusResult(
            reached=True, agreement_count=2, total_agents=2,
            opinions={"agent-a": "A", "agent-b": "B"}, summary="ok",
        )
        fake_synthesis = SynthesisResult(
            round_num=1,
            consensus_reached=True,
            agreement_count=2,
            total_agents=2,
            consensus=fake_consensus,
            summary_for_shared_md="ok",
            next_round_prompt="",
            structured_consensus=None,
            metadata={},
            source="heuristic",
        )
        proto.synthesis_agent = AsyncMock()
        proto.synthesis_agent.synthesize.return_value = fake_synthesis

        proto.shared.write_synthesis_summary = MagicMock()
        proto.shared.update_consensus = MagicMock()
        proto.shared.update_tasks = MagicMock()
        proto.shared.append_response_reference = MagicMock()

        await proto.run("test prompt")

        events = bus.poll()
        progress_events = [
            e for e in events if e.type == TUIEventType.DELIBERATION_PROGRESS
        ]
        # Should have progress events for each of the 2 agents
        assert len(progress_events) == 2
        # First progress: completed=1, total=2
        assert progress_events[0].data["completed"] == 1
        assert progress_events[0].data["total"] == 2
        assert progress_events[0].data["round_num"] == 1
        # Second progress: completed=2, total=2
        assert progress_events[1].data["completed"] == 2
        assert progress_events[1].data["total"] == 2
        assert progress_events[1].data["round_num"] == 1

    @pytest.mark.asyncio
    async def test_no_emit_without_event_bus(self):
        """Protocol should not crash when no event bus is set."""
        proto = _make_protocol(event_bus=None)

        async def fake_collect(round_num, prompt):
            return {}

        proto._collect_opinions = fake_collect

        from trinity.deliberation.synthesis import SynthesisResult
        from trinity.models import ConsensusResult

        fake_consensus = ConsensusResult(
            reached=True, agreement_count=1, total_agents=1, opinions={}, summary="ok"
        )
        fake_synthesis = SynthesisResult(
            round_num=1,
            consensus_reached=True,
            agreement_count=1,
            total_agents=1,
            consensus=fake_consensus,
            summary_for_shared_md="ok",
            next_round_prompt="",
            structured_consensus=None,
            metadata={},
            source="heuristic",
        )
        proto.synthesis_agent = AsyncMock()
        proto.synthesis_agent.synthesize.return_value = fake_synthesis

        proto.shared.write_synthesis_summary = MagicMock()
        proto.shared.update_consensus = MagicMock()
        proto.shared.update_tasks = MagicMock()

        # Should complete without error
        result = await proto.run("test prompt")
        assert result is not None
