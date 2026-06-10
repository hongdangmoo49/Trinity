"""Persistence helpers for Trinity loop runs."""

from __future__ import annotations

import json
import time
from pathlib import Path
from uuid import uuid4

try:  # pragma: no cover - Python 3.10 compatibility.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from trinity.loop.models import LoopRun, LoopSpec, LoopStatus


class LoopPersistenceError(ValueError):
    """Raised when loop spec or run persistence fails."""


class LoopPersistence:
    """Read loop specs and persist loop run state under `.trinity/loops`."""

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.root = state_dir / "loops"
        self.specs_dir = self.root / "specs"
        self.runs_dir = self.root / "runs"
        self.queue_dir = self.root / "queue"

    def load_spec(self, ref: str | Path) -> LoopSpec:
        """Load a loop spec by id or TOML path."""
        path = self._resolve_spec_path(ref)
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise LoopPersistenceError(f"Failed to read loop spec {path}: {exc}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise LoopPersistenceError(f"Invalid loop spec TOML {path}: {exc}") from exc
        try:
            return LoopSpec.from_dict(data)
        except ValueError as exc:
            raise LoopPersistenceError(f"Invalid loop spec {path}: {exc}") from exc

    def create_run(self, spec: LoopSpec) -> LoopRun:
        """Create a new queued run for a spec."""
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        run = LoopRun(
            id=self._new_run_id(),
            spec_id=spec.id,
            spec_title=spec.title,
            status=LoopStatus.QUEUED,
        )
        self.save_run(run)
        self.append_event(run, "loop_run_created", {"spec_id": spec.id})
        self.append_ledger(
            run,
            f"# Loop Run: {spec.title}\n\n"
            f"- run_id: `{run.id}`\n"
            f"- spec_id: `{spec.id}`\n"
            f"- goal: {spec.goal}\n",
        )
        return run

    def save_run(self, run: LoopRun) -> None:
        """Persist loop run JSON."""
        run.updated_at = time.time()
        path = self.run_path(run.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(run.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_run(self, run_id: str) -> LoopRun:
        """Load one loop run by id."""
        if run_id == "latest":
            run = self.latest_run()
            if run is None:
                raise LoopPersistenceError("No loop runs found.")
            return run
        path = self.run_path(run_id)
        if not path.exists():
            raise LoopPersistenceError(f"Loop run not found: {run_id}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LoopPersistenceError(f"Failed to load loop run {run_id}: {exc}") from exc
        if not isinstance(data, dict):
            raise LoopPersistenceError(f"Loop run {run_id} is invalid.")
        return LoopRun.from_dict(data)

    def latest_run(self, *, spec_id: str = "") -> LoopRun | None:
        """Return the newest run, optionally filtered by spec id."""
        if not self.runs_dir.exists():
            return None
        runs: list[LoopRun] = []
        for path in self.runs_dir.glob("*/loop.json"):
            try:
                run = self.load_run(path.parent.name)
            except LoopPersistenceError:
                continue
            if spec_id and run.spec_id != spec_id:
                continue
            runs.append(run)
        if not runs:
            return None
        return sorted(runs, key=lambda item: item.updated_at, reverse=True)[0]

    def append_event(
        self,
        run: LoopRun,
        event: str,
        data: dict[str, object] | None = None,
    ) -> None:
        """Append one machine-readable loop event."""
        event_path = self.run_dir(run.id) / "events.jsonl"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": time.time(),
            "run_id": run.id,
            "spec_id": run.spec_id,
            "iteration": run.iteration,
            "event": event,
            "data": dict(data or {}),
        }
        with event_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def append_ledger(self, run: LoopRun, markdown: str) -> None:
        """Append human-readable loop ledger text."""
        ledger_path = self.run_dir(run.id) / "ledger.md"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as fh:
            text = markdown.rstrip()
            if text:
                fh.write(text + "\n\n")

    def write_iteration_gate_results(self, run: LoopRun) -> Path:
        """Write gate results for the current iteration."""
        path = self.iteration_dir(run.id, run.iteration) / "gate-results.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        latest = [
            result.to_dict()
            for result in run.gate_results
            if result.iteration == run.iteration
        ]
        path.write_text(
            json.dumps(latest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def run_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "loop.json"

    def iteration_dir(self, run_id: str, iteration: int) -> Path:
        return self.run_dir(run_id) / f"iteration-{iteration:03d}"

    def artifact_dir(self, run_id: str, iteration: int) -> Path:
        return self.iteration_dir(run_id, iteration) / "artifacts"

    def _resolve_spec_path(self, ref: str | Path) -> Path:
        raw = Path(ref)
        candidates: list[Path] = []
        if raw.exists():
            candidates.append(raw)
        if raw.suffix == ".toml":
            candidates.append(raw)
        candidates.append(self.specs_dir / f"{raw.name}.toml")
        candidates.append(self.root / str(raw))
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        raise LoopPersistenceError(f"Loop spec not found: {ref}")

    @staticmethod
    def _new_run_id() -> str:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        return f"looprun-{stamp}-{uuid4().hex[:6]}"
