"""Tests for trinity.completion — completion detectors and fallback chain."""

import asyncio
import json
import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from trinity.completion.base import CompletionDetector, CompletionResult, FallbackChainDetector
from trinity.completion.hook import HookDetector
from trinity.completion.idle import IdleDetector
from trinity.completion.marker import MarkerDetector
from trinity.completion.prompt import PromptReturnDetector
from trinity.legacy.tmux.pane import TmuxPane


def _make_pane(capture_outputs: list[str] | None = None) -> MagicMock:
    """Create a mock TmuxPane with configurable capture outputs."""
    pane = MagicMock(spec=TmuxPane)
    pane.pane_id = "%0"
    pane.session_name = "test"
    if capture_outputs:
        pane.capture = MagicMock(side_effect=[
            [line for line in out.splitlines() if line is not None]
            for out in capture_outputs
        ])
    else:
        pane.capture = MagicMock(return_value=[])
    pane.is_alive = MagicMock(return_value=True)
    return pane


# ─── IdleDetector ───────────────────────────────────────────────

class TestIdleDetector:

    def test_name(self):
        d = IdleDetector(idle_timeout=5.0)
        assert "IdleDetector" in d.name
        assert "5.0" in d.name

    @pytest.mark.asyncio
    async def test_detects_idle_after_timeout(self, tmp_path):
        """Output stops changing → completion detected."""
        d = IdleDetector(idle_timeout=0.2)
        pane = _make_pane()

        # Same output every time → idle detected after idle_timeout
        pane.capture = MagicMock(return_value=["line1", "line2"])

        result = await d.wait_for_completion(pane, timeout=2.0, poll_interval=0.1)

        assert result.completed
        assert result.detector_name == d.name
        assert "line1" in result.output

    @pytest.mark.asyncio
    async def test_timeout_when_output_keeps_changing(self):
        """Output never stops changing → hard timeout."""
        d = IdleDetector(idle_timeout=5.0)  # Long idle timeout
        pane = _make_pane()

        call_count = {"n": 0}
        def changing_capture(lines=-100):
            call_count["n"] += 1
            return [f"line{call_count['n']}"]  # Always different

        pane.capture = changing_capture

        result = await d.wait_for_completion(pane, timeout=0.5, poll_interval=0.1)

        assert not result.completed
        assert result.metadata.get("reason") == "hard_timeout"

    @pytest.mark.asyncio
    async def test_eventually_stops_changing(self):
        """Output changes a few times then stops → detected."""
        d = IdleDetector(idle_timeout=0.2)
        pane = _make_pane()

        call_count = {"n": 0}
        def eventually_stable(lines=-100):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                return [f"changing{call_count['n']}"]
            return ["stable"]

        pane.capture = eventually_stable

        result = await d.wait_for_completion(pane, timeout=2.0, poll_interval=0.05)

        assert result.completed


# ─── PromptReturnDetector ───────────────────────────────────────

class TestPromptReturnDetector:

    def test_name(self):
        d = PromptReturnDetector()
        assert d.name == "PromptReturnDetector"

    @pytest.mark.asyncio
    async def test_detects_arrow_prompt(self):
        """Claude's > prompt detected."""
        d = PromptReturnDetector()
        pane = _make_pane()

        call_count = {"n": 0}
        def eventually_prompt(lines=-5):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                return ["some response text"]
            return ["response done", "> "]

        pane.capture = eventually_prompt

        result = await d.wait_for_completion(pane, timeout=2.0, poll_interval=0.05)

        assert result.completed
        assert "response done" in result.output

    @pytest.mark.asyncio
    async def test_detects_dollar_prompt(self):
        """Shell-style $ prompt detected."""
        d = PromptReturnDetector()
        pane = _make_pane()

        pane.capture = MagicMock(return_value=["output", "$ "])

        result = await d.wait_for_completion(pane, timeout=1.0, poll_interval=0.05)

        assert result.completed

    @pytest.mark.asyncio
    async def test_detects_starship_prompt(self):
        """Starship-style ❯ prompt detected."""
        d = PromptReturnDetector()
        pane = _make_pane()

        pane.capture = MagicMock(return_value=["text", "❯ "])

        result = await d.wait_for_completion(pane, timeout=1.0, poll_interval=0.05)

        assert result.completed

    @pytest.mark.asyncio
    async def test_timeout_when_no_prompt(self):
        """No prompt ever appears → timeout."""
        d = PromptReturnDetector()
        pane = _make_pane()

        pane.capture = MagicMock(return_value=["just output", "no prompt here"])

        result = await d.wait_for_completion(pane, timeout=0.3, poll_interval=0.05)

        assert not result.completed
        assert result.metadata.get("reason") == "timeout"

    @pytest.mark.asyncio
    async def test_custom_pattern(self):
        """Custom prompt pattern works."""
        d = PromptReturnDetector(prompt_patterns=[r"READY>\s*$"])
        pane = _make_pane()

        pane.capture = MagicMock(return_value=["output", "READY> "])

        result = await d.wait_for_completion(pane, timeout=1.0, poll_interval=0.05)

        assert result.completed

    @pytest.mark.asyncio
    async def test_scoped_detection_ignores_stale_prompt(self):
        """A prompt visible before the request must not complete the request."""
        d = PromptReturnDetector()
        pane = _make_pane()

        captures = [
            ["ready", "> "],
            ["ready", "> ", "Question", "Thinking..."],
            ["ready", "> ", "Question", "Final answer", "> "],
        ]
        state = {"n": -1}

        def scoped_capture(lines=-5):
            state["n"] += 1
            idx = min(max(state["n"], 0), len(captures) - 1)
            return captures[idx]

        pane.capture = scoped_capture
        d.prepare_for_request(pane=pane, start_line=2, sent_text="Question")

        result = await d.wait_for_completion(pane, timeout=1.0, poll_interval=0.01)

        assert result.completed
        assert state["n"] >= 2
        assert "Final answer" in result.output


# ─── HookDetector ───────────────────────────────────────────────

class TestHookDetector:

    def test_name(self):
        d = HookDetector(signal_path=Path("/tmp/signal.json"))
        assert "HookDetector" in d.name
        assert "signal.json" in d.name

    @pytest.mark.asyncio
    async def test_detects_signal_file_creation(self, tmp_path):
        """Signal file appears → completion detected."""
        signal = tmp_path / "signal.json"
        d = HookDetector(signal_path=signal)
        pane = _make_pane()

        pane.capture = MagicMock(return_value=["response text"])

        # Write signal file after a short delay
        async def write_signal():
            await asyncio.sleep(0.2)
            signal.write_text('{"completed": true}', encoding="utf-8")

        asyncio.create_task(write_signal())

        result = await d.wait_for_completion(pane, timeout=2.0, poll_interval=0.05)

        assert result.completed
        assert result.metadata.get("signal", {}).get("completed") is True

    @pytest.mark.asyncio
    async def test_timeout_when_no_signal(self, tmp_path):
        """No signal file appears → timeout."""
        signal = tmp_path / "signal.json"
        d = HookDetector(signal_path=signal)
        pane = _make_pane()

        pane.capture = MagicMock(return_value=["output"])

        result = await d.wait_for_completion(pane, timeout=0.3, poll_interval=0.05)

        assert not result.completed

    def test_reset_cleans_signal_file(self, tmp_path):
        """reset() removes the signal file."""
        signal = tmp_path / "signal.json"
        signal.write_text('{"completed": true}', encoding="utf-8")

        d = HookDetector(signal_path=signal)
        d.reset()

        assert not signal.exists()

    def test_reset_no_file_ok(self, tmp_path):
        """reset() doesn't crash if no signal file exists."""
        signal = tmp_path / "signal.json"
        d = HookDetector(signal_path=signal)
        d.reset()  # Should not raise

    @pytest.mark.asyncio
    async def test_ignores_old_signal(self, tmp_path):
        """Pre-existing signal file is ignored; only new writes trigger."""
        signal = tmp_path / "signal.json"
        signal.write_text('{"completed": true}', encoding="utf-8")

        d = HookDetector(signal_path=signal)
        pane = _make_pane()
        pane.capture = MagicMock(return_value=["output"])

        # The old file should be recorded as baseline mtime
        result = await d.wait_for_completion(pane, timeout=0.3, poll_interval=0.05)

        # Should timeout because mtime didn't change
        assert not result.completed


# ─── MarkerDetector ─────────────────────────────────────────────

class TestMarkerDetector:

    def test_name(self):
        d = MarkerDetector("[DONE]")
        assert "MarkerDetector" in d.name
        assert "[DONE]" in d.name

    @pytest.mark.asyncio
    async def test_detects_marker(self):
        d = MarkerDetector("[DONE]")
        pane = _make_pane()

        call_count = {"n": 0}
        def eventually_done(lines=-200):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                return ["thinking..."]
            return ["final answer", "[DONE]"]

        pane.capture = eventually_done

        result = await d.wait_for_completion(pane, timeout=2.0, poll_interval=0.05)

        assert result.completed
        assert result.metadata["marker"] == "[DONE]"
        assert "final answer" in result.output

    @pytest.mark.asyncio
    async def test_timeout_without_marker(self):
        d = MarkerDetector("[DONE]")
        pane = _make_pane()
        pane.capture = MagicMock(return_value=["thinking..."])

        result = await d.wait_for_completion(pane, timeout=0.2, poll_interval=0.05)

        assert not result.completed
        assert result.metadata["reason"] == "timeout"

    @pytest.mark.asyncio
    async def test_scoped_detection_ignores_prompt_echo_marker(self):
        """The marker inside the echoed prompt must not signal completion."""
        marker = "[DONE]"
        d = MarkerDetector(marker)
        pane = _make_pane()
        d.prepare_for_request(
            pane=pane,
            start_line=2,
            sent_text=f"Question\n\nAfter completing your response, output: {marker}",
        )

        captures = [
            ["ready", "> ", "Question", f"After completing your response, output: {marker}"],
            [
                "ready",
                "> ",
                "Question",
                f"After completing your response, output: {marker}",
                "Final answer",
                marker,
            ],
        ]
        state = {"n": 0}

        def scoped_capture(lines=-200):
            idx = min(state["n"], len(captures) - 1)
            state["n"] += 1
            return captures[idx]

        pane.capture = scoped_capture

        result = await d.wait_for_completion(pane, timeout=1.0, poll_interval=0.01)

        assert result.completed
        assert state["n"] == 2
        assert result.metadata["marker_count"] == 2
        assert result.metadata["ignored_marker_count"] == 1
        assert "Final answer" in result.output

    @pytest.mark.asyncio
    async def test_request_scope_ignores_stale_marker_before_boundary(self):
        """A stale marker before the request boundary must not complete a request."""
        marker = "[DONE]"
        d = MarkerDetector(marker)
        pane = _make_pane()
        d.prepare_for_request(
            pane=pane,
            start_line=3,
            sent_text=f"Question\nAfter completing your response, output: {marker}",
        )

        captures = [
            [
                "old response",
                marker,
                "> ",
                "Question",
                f"After completing your response, output: {marker}",
            ],
            [
                "old response",
                marker,
                "> ",
                "Question",
                f"After completing your response, output: {marker}",
                "Fresh answer",
                marker,
            ],
        ]
        state = {"n": 0}

        def scoped_capture(lines=-200):
            idx = min(state["n"], len(captures) - 1)
            state["n"] += 1
            return captures[idx]

        pane.capture = scoped_capture

        result = await d.wait_for_completion(pane, timeout=1.0, poll_interval=0.01)

        assert result.completed
        assert state["n"] == 2
        assert "Fresh answer" in result.output
        assert "old response" not in result.output
        assert result.metadata["request_start_line"] == 3


# ─── FallbackChainDetector ──────────────────────────────────────

class TestFallbackChainDetector:

    def test_name_includes_all_detectors(self):
        chain = FallbackChainDetector([
            IdleDetector(idle_timeout=5.0),
            PromptReturnDetector(),
        ])
        assert "IdleDetector" in chain.name
        assert "PromptReturnDetector" in chain.name

    @pytest.mark.asyncio
    async def test_returns_first_positive_result(self, tmp_path):
        """Fastest detector wins."""
        slow = MagicMock(spec=CompletionDetector)
        slow.name = "SlowDetector"
        slow.wait_for_completion = AsyncMock(return_value=CompletionResult(
            completed=True, detector_name="SlowDetector",
        ))

        fast = MagicMock(spec=CompletionDetector)
        fast.name = "FastDetector"
        fast.wait_for_completion = AsyncMock(return_value=CompletionResult(
            completed=True, detector_name="FastDetector",
        ))

        chain = FallbackChainDetector([slow, fast])
        pane = _make_pane()

        result = await chain.wait_for_completion(pane, timeout=2.0)

        assert result.completed
        # One of them should have been used
        assert result.detector_name in ("SlowDetector", "FastDetector")

    @pytest.mark.asyncio
    async def test_all_timeout_returns_failure(self):
        """All detectors timeout → failure."""
        d1 = MagicMock(spec=CompletionDetector)
        d1.name = "D1"
        d1.wait_for_completion = AsyncMock(return_value=CompletionResult(
            completed=False, detector_name="D1",
        ))

        d2 = MagicMock(spec=CompletionDetector)
        d2.name = "D2"
        d2.wait_for_completion = AsyncMock(return_value=CompletionResult(
            completed=False, detector_name="D2",
        ))

        chain = FallbackChainDetector([d1, d2])
        pane = _make_pane()
        pane.capture = MagicMock(return_value=["output"])

        result = await chain.wait_for_completion(pane, timeout=1.0)

        assert not result.completed

    @pytest.mark.asyncio
    async def test_with_real_detectors_prompt_wins(self):
        """PromptReturnDetector fires faster than IdleDetector."""
        chain = FallbackChainDetector([
            IdleDetector(idle_timeout=5.0),  # Won't trigger quickly
            PromptReturnDetector(),
        ])

        pane = _make_pane()

        call_count = {"n": 0}
        def eventually_prompt(lines=-5):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                return ["thinking..."]
            return ["done", "> "]

        pane.capture = eventually_prompt

        result = await chain.wait_for_completion(pane, timeout=2.0, poll_interval=0.05)

        assert result.completed
        assert "PromptReturn" in result.detector_name
