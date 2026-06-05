"""Cross-platform log following without shelling out to tail."""

from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator, Literal

LogTailEventKind = Literal["line", "rotated", "deleted", "created"]


@dataclass(frozen=True)
class LogTailEvent:
    """A line or lifecycle event produced while following a log file."""

    kind: LogTailEventKind
    message: str


@dataclass(frozen=True)
class _FileIdentity:
    device: int
    inode: int


def follow_log(
    path: str | Path,
    *,
    lines: int = 50,
    poll_interval: float = 0.5,
) -> Iterator[LogTailEvent]:
    """Yield the last ``lines`` log entries, then poll for appended entries.

    The generator follows the path instead of a specific process. If the file is
    deleted or replaced while following, it emits a friendly event and resumes
    from the recreated file when possible.
    """
    log_path = Path(path)
    line_count = max(0, lines)
    stream: BinaryIO | None = None
    identity: _FileIdentity | None = None
    pending = b""
    reported_missing = False

    try:
        while stream is None:
            try:
                stream, identity, initial_lines = _open_with_tail(log_path, line_count)
            except FileNotFoundError:
                if not reported_missing:
                    reported_missing = True
                    yield LogTailEvent(
                        "deleted",
                        f"Log file {log_path} was not found; waiting for it to be created.",
                    )
                    continue
                time.sleep(poll_interval)
                continue

            if reported_missing:
                yield LogTailEvent(
                    "created",
                    f"Log file {log_path} was created; following it now.",
                )
                reported_missing = False

            for line in initial_lines:
                yield LogTailEvent("line", line)

        while True:
            assert stream is not None
            assert identity is not None

            new_lines, pending = _read_complete_lines(stream, pending)
            if new_lines:
                for line in new_lines:
                    yield LogTailEvent("line", line)
                continue

            state = _detect_state(log_path, stream, identity)
            if state == "same":
                time.sleep(poll_interval)
                continue

            if state == "deleted":
                stream.close()
                stream = None
                pending = b""
                yield LogTailEvent(
                    "deleted",
                    f"Log file {log_path} was deleted; waiting for it to be recreated.",
                )

                while stream is None:
                    try:
                        stream, identity = _open_from_start(log_path)
                    except FileNotFoundError:
                        time.sleep(poll_interval)
                        continue

                yield LogTailEvent(
                    "created",
                    f"Log file {log_path} was recreated; following the new file.",
                )
                continue

            if state == "rotated":
                stream.close()
                stream = None
                pending = b""
                try:
                    stream, identity = _open_from_start(log_path)
                except FileNotFoundError:
                    yield LogTailEvent(
                        "deleted",
                        f"Log file {log_path} was rotated away; waiting for a new file.",
                    )
                    while stream is None:
                        try:
                            stream, identity = _open_from_start(log_path)
                        except FileNotFoundError:
                            time.sleep(poll_interval)
                            continue

                    yield LogTailEvent(
                        "created",
                        f"Log file {log_path} was recreated; following the new file.",
                    )
                    continue

                yield LogTailEvent(
                    "rotated",
                    f"Log file {log_path} was rotated; following the new file.",
                )
                continue

            if state == "truncated":
                stream.seek(0)
                pending = b""
                yield LogTailEvent(
                    "rotated",
                    f"Log file {log_path} was truncated; following from the beginning.",
                )
                continue
    finally:
        if stream is not None:
            stream.close()


def _open_with_tail(
    path: Path,
    line_count: int,
) -> tuple[BinaryIO, _FileIdentity, list[str]]:
    stream = path.open("rb")
    tail: deque[str] = deque(maxlen=line_count)

    while True:
        raw_line = stream.readline()
        if raw_line == b"":
            break
        tail.append(_decode_line(raw_line))

    return stream, _identity_from_stream(stream), list(tail)


def _open_from_start(path: Path) -> tuple[BinaryIO, _FileIdentity]:
    stream = path.open("rb")
    return stream, _identity_from_stream(stream)


def _read_complete_lines(
    stream: BinaryIO,
    pending: bytes,
) -> tuple[list[str], bytes]:
    chunk = stream.read()
    if not chunk:
        return [], pending

    data = pending + chunk
    parts = data.splitlines(keepends=True)
    if parts and not parts[-1].endswith((b"\n", b"\r")):
        pending = parts.pop()
    else:
        pending = b""

    return [_decode_line(part) for part in parts], pending


def _decode_line(raw_line: bytes) -> str:
    return raw_line.rstrip(b"\r\n").decode("utf-8", errors="replace")


def _identity_from_stream(stream: BinaryIO) -> _FileIdentity:
    stat_result = os.fstat(stream.fileno())
    return _FileIdentity(device=stat_result.st_dev, inode=stat_result.st_ino)


def _detect_state(
    path: Path,
    stream: BinaryIO,
    identity: _FileIdentity,
) -> Literal["same", "rotated", "deleted", "truncated"]:
    try:
        path_stat = path.stat()
    except FileNotFoundError:
        return "deleted"

    path_identity = _FileIdentity(device=path_stat.st_dev, inode=path_stat.st_ino)
    if path_identity != identity:
        return "rotated"

    if path_stat.st_size < stream.tell():
        return "truncated"

    return "same"
