# Phase 10 Remaining: Timeouts, Lang Validation, Task Exec, Round Rotation

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 4 remaining Phase 10 issues: (1) configurable idle timeouts per provider with IdleDetector in chains, (2) language validation in i18n, (3) task execution after consensus, (4) mid-round context rotation.

**Architecture:** (1) Add IdleDetector to all provider chains in factory.py with configurable timeouts. (2) Add `validate_lang()` to i18n.py that rejects unsupported codes. (3) Add `execute_tasks()` to protocol.py that sends task assignments back to agents. (4) Add rotation callback hook to protocol's round loop so orchestrator can rotate between rounds.

**Tech Stack:** Python 3.10+, asyncio, no new dependencies.

---

## Task 1: Add IdleDetector with configurable timeouts to provider chains

**Files:**
- Modify: `src/trinity/agents/factory.py:98-127`
- Modify: `tests/test_agent_factory.py`

**Why:** Gemini and Codex chains lack IdleDetector fallback. When PromptReturn/Marker fail, there's no safety net. Claude's chain also benefits from idle as last resort. Timeouts should differ: Claude 15s, Codex 20s, Gemini 25s.

**Step 1: Write failing test**

Add to `tests/test_agent_factory.py`:

```python
def test_claude_chain_includes_idle_detector():
    """Claude detector chain should have IdleDetector as fallback."""
    from pathlib import Path
    chain = AgentFactory.create_detector_chain(Path("/tmp/signal.json"), Provider.CLAUDE_CODE)
    names = [d.name for d in chain.detectors]
    assert any("IdleDetector" in n for n in names)

def test_gemini_chain_includes_idle_detector():
    """Gemini detector chain should have IdleDetector with longer timeout."""
    from pathlib import Path
    chain = AgentFactory.create_detector_chain(Path("/tmp/signal.json"), Provider.GEMINI_CLI)
    names = [d.name for d in chain.detectors]
    assert any("IdleDetector" in n for n in names)

def test_codex_chain_includes_idle_detector():
    """Codex detector chain should have IdleDetector."""
    from pathlib import Path
    chain = AgentFactory.create_detector_chain(Path("/tmp/signal.json"), Provider.CODEX)
    names = [d.name for d in chain.detectors]
    assert any("IdleDetector" in n for n in names)

def test_idle_timeouts_differ_by_provider():
    """Each provider should have appropriate idle timeout."""
    from pathlib import Path
    from trinity.completion.idle import IdleDetector

    claude_chain = AgentFactory.create_detector_chain(Path("/tmp/s.json"), Provider.CLAUDE_CODE)
    codex_chain = AgentFactory.create_detector_chain(Path("/tmp/s.json"), Provider.CODEX)
    gemini_chain = AgentFactory.create_detector_chain(Path("/tmp/s.json"), Provider.GEMINI_CLI)

    def get_idle_timeout(chain):
        for d in chain.detectors:
            if isinstance(d, IdleDetector):
                return d.idle_timeout
        return None

    assert get_idle_timeout(claude_chain) == 15.0
    assert get_idle_timeout(codex_chain) == 20.0
    assert get_idle_timeout(gemini_chain) == 25.0
```

**Step 2: Run tests, verify fail**

**Step 3: Implement**

In `src/trinity/agents/factory.py`, modify `create_detector_chain()`:

```python
    @staticmethod
    def create_detector_chain(signal_path: Path, provider: Provider) -> FallbackChainDetector:
        """Create a provider-appropriate completion detector chain.

        Claude: Hook → PromptReturn → Idle(15s)
        Codex: PromptReturn → Idle(20s)
        Gemini: Marker → PromptReturn → Idle(25s)
        """
        if provider == Provider.CLAUDE_CODE:
            return FallbackChainDetector([
                HookDetector(signal_path=signal_path),
                PromptReturnDetector(),
                IdleDetector(idle_timeout=15.0),
            ])
        elif provider == Provider.CODEX:
            return FallbackChainDetector([
                PromptReturnDetector(
                    prompt_patterns=[r"^\s*\$\s*$", r"^\s*>\s*$", r"^\s*›\s*$"]
                ),
                IdleDetector(idle_timeout=20.0),
            ])
        elif provider == Provider.GEMINI_CLI:
            from trinity.agents.gemini_agent import COMPLETION_MARKER

            return FallbackChainDetector([
                MarkerDetector(COMPLETION_MARKER),
                PromptReturnDetector(),
                IdleDetector(idle_timeout=25.0),
            ])
        else:
            return FallbackChainDetector([
                PromptReturnDetector(),
                IdleDetector(idle_timeout=20.0),
            ])
```

**Step 4: Run tests**

**Step 5: Commit**

```bash
git commit -m "fix(phase10): add IdleDetector fallback to all provider chains with tuned timeouts"
```

---

## Task 2: Add language validation to i18n

**Files:**
- Modify: `src/trinity/i18n.py`
- Modify: `tests/test_i18n.py`

**Why:** No validation exists for invalid language codes. Passing "fr" or "ja" silently falls back to English with no warning. Need explicit validation and helpful error messages.

**Step 1: Write failing tests**

Add to `tests/test_i18n.py`:

```python
def test_validate_lang_accepts_en():
    from trinity.i18n import validate_lang
    assert validate_lang("en") == "en"

def test_validate_lang_accepts_ko():
    from trinity.i18n import validate_lang
    assert validate_lang("ko") == "ko"

def test_validate_lang_rejects_unknown():
    from trinity.i18n import validate_lang
    with pytest.raises(ValueError, match="Unsupported language"):
        validate_lang("fr")

def test_validate_lang_falls_back_to_en():
    from trinity.i18n import validate_lang
    result = validate_lang("fr", fallback="en")
    assert result == "en"

def test_get_strings_invalid_lang_returns_english():
    from trinity.i18n import get_strings
    S = get_strings("fr")
    # Should return English strings with a warning
    assert S.wizard_title is not None
```

**Step 2: Run tests, verify fail**

**Step 3: Implement**

In `src/trinity/i18n.py`, add after `Lang` type alias:

```python
SUPPORTED_LANGS: list[str] = ["en", "ko"]
DEFAULT_LANG: str = "en"


def validate_lang(lang: str, fallback: str | None = None) -> str:
    """Validate a language code.

    Args:
        lang: Language code to validate.
        fallback: Language to use if invalid. If None, raises ValueError.

    Returns:
        Validated language code.

    Raises:
        ValueError: If lang is unsupported and no fallback provided.
    """
    if lang in SUPPORTED_LANGS:
        return lang

    if fallback is not None:
        logger.warning(f"Unsupported language '{lang}', falling back to '{fallback}'")
        return fallback if fallback in SUPPORTED_LANGS else DEFAULT_LANG

    raise ValueError(
        f"Unsupported language: '{lang}'. "
        f"Supported languages: {', '.join(SUPPORTED_LANGS)}"
    )
```

Also modify `get_strings()` to use validation:

```python
def get_strings(lang: str = "en") -> Strings:
    """Get localized strings for the given language."""
    safe_lang = validate_lang(lang, fallback=DEFAULT_LANG)
    return _STRINGS.get(safe_lang, _STRINGS[DEFAULT_LANG])
```

**Step 4: Run tests**

**Step 5: Commit**

```bash
git commit -m "fix(phase10): add language validation with helpful error messages"
```

---

## Task 3: Add task execution after consensus

**Files:**
- Modify: `src/trinity/deliberation/protocol.py`
- Modify: `tests/test_protocol.py`

**Why:** After consensus, tasks are assigned but never executed. The protocol should optionally send task descriptions back to agents for actual execution.

**Step 1: Write failing test**

Add to `tests/test_protocol.py`:

```python
    def test_tasks_executed_after_consensus(self):
        """Protocol should execute tasks after distribution."""
        agent = _make_mock_agent("claude", "I agree.")
        protocol, shared = _make_protocol({"claude": agent})

        result = asyncio.run(protocol.run("Design auth"))

        # Tasks should be distributed
        assert len(result.tasks) > 0

        # Tasks should be marked as executed in result metadata
        executed = result.metadata.get("tasks_executed", False)
        assert executed is True
```

Note: This test requires `DeliberationResult` to have a `metadata` field. Check `models.py` first — if it doesn't have one, add it.

**Step 2: Run test, verify fail**

**Step 3: Implement**

First, check if `DeliberationResult` in `models.py` has a `metadata` field. If not, add:
```python
    metadata: dict[str, Any] = field(default_factory=dict)
```

Then in `protocol.py`, add `execute_tasks()` method and call it in `run()`:

```python
    async def _execute_tasks(self, tasks: list[TaskAssignment]) -> None:
        """Send task assignments to agents for execution."""
        for task in tasks:
            agent = self.agents.get(task.agent_name)
            if not agent:
                logger.warning(f"No agent '{task.agent_name}' for task execution")
                continue

            try:
                logger.info(f"Executing task on {task.agent_name}: {task.task_description[:80]}...")
                msg = await agent.send_and_wait(task.task_description, timeout=self.round_timeout)
                logger.info(f"Task execution response from {task.agent_name}: {msg.content[:100]}...")
            except Exception as e:
                logger.error(f"Task execution failed for {task.agent_name}: {e}")
```

In `run()`, after `self.shared.update_tasks(task_dict)`, add:

```python
        # Execute tasks
        await self._execute_tasks(tasks)
```

And update the `DeliberationResult` to include execution status:
```python
        return DeliberationResult(
            ...,
            metadata={"tasks_executed": True},
        )
```

**Step 4: Run tests**

**Step 5: Commit**

```bash
git commit -m "feat(phase10): execute tasks after consensus via agent send_and_wait"
```

---

## Task 4: Move context rotation into protocol round loop

**Files:**
- Modify: `src/trinity/deliberation/protocol.py`
- Modify: `src/trinity/orchestrator.py`
- Modify: `tests/test_orchestrator.py`

**Why:** Currently `_check_and_rotate()` is called only after ALL deliberation rounds complete (`orchestrator.py:272`). For long deliberations, context overflow happens mid-session. Need to check after each round.

**Step 1: Write failing test**

Add to `tests/test_orchestrator.py`:

```python
    def test_rotation_callback_called_per_round(self, tmp_path):
        """Orchestrator should register rotation callback with protocol."""
        config = TrinityConfig.default_config(project_dir=tmp_path)
        orchestrator = TrinityOrchestrator(config)
        orchestrator._ensure_initialized()

        # Protocol should have a rotation callback registered
        assert orchestrator.protocol._rotation_callback is not None
```

**Step 2: Run test, verify fail**

**Step 3: Implement**

In `protocol.py`, add to `__init__()`:
```python
        self._rotation_callback: Callable | None = None
```

Add method:
```python
    def set_rotation_callback(self, callback: Callable) -> None:
        """Set callback to be called after each round for context rotation check."""
        self._rotation_callback = callback
```

In `run()`, inside the round loop, after consensus check but before the `continue`:
```python
            # Check context rotation between rounds
            if self._rotation_callback:
                await self._rotation_callback()
```

In `orchestrator.py`, in `_ensure_initialized()`, after creating the protocol:
```python
        # Register rotation callback for mid-round context checks
        self.protocol.set_rotation_callback(self._check_and_rotate)
```

**Step 4: Run tests**

**Step 5: Commit**

```bash
git commit -m "fix(phase10): move context rotation inside round loop via callback"
```

---

## Task 5: Full regression test + version bump

**Step 1:** `pytest tests/ -q --tb=short`
**Step 2:** Bump version to `0.7.0`
**Step 3:** Update checkpoint.md
**Step 4:** Commit and push
