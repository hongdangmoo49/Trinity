"""Run the required Trinity smoke test set used by CI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_LIST = ROOT / ".github" / "required-smoke-tests.txt"


def load_tests() -> list[str]:
    tests: list[str] = []
    lines = TEST_LIST.read_text(encoding="utf-8").splitlines()
    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if not (ROOT / line).exists():
            raise SystemExit(f"{TEST_LIST}:{line_number}: missing test path: {line}")
        tests.append(line)
    if not tests:
        raise SystemExit(f"{TEST_LIST}: no smoke tests configured")
    return tests


def main(argv: list[str] | None = None) -> int:
    extra_args = list(argv if argv is not None else sys.argv[1:])
    command = [sys.executable, "-m", "pytest", *extra_args, *load_tests()]
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
