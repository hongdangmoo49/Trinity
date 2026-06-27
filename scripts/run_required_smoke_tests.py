"""Run the required Trinity smoke test set used by CI."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_LIST = ROOT / ".github" / "required-smoke-tests.txt"


def load_tests() -> list[str]:
    tests: list[str] = []
    seen: dict[str, int] = {}
    lines = TEST_LIST.read_text(encoding="utf-8").splitlines()
    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if not (ROOT / line).exists():
            raise SystemExit(f"{TEST_LIST}:{line_number}: missing test path: {line}")
        if line in seen:
            raise SystemExit(
                f"{TEST_LIST}:{line_number}: duplicate test path: {line} "
                f"(first listed on line {seen[line]})"
            )
        seen[line] = line_number
        tests.append(line)
    if not tests:
        raise SystemExit(f"{TEST_LIST}: no smoke tests configured")
    return tests


def parse_args(argv: list[str]) -> tuple[bool, list[str]]:
    parser = argparse.ArgumentParser(
        description="Run Trinity's required CI smoke test manifest.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the configured smoke test paths and exit",
    )
    args, pytest_args = parser.parse_known_args(argv)
    return bool(args.list), pytest_args


def main(argv: list[str] | None = None) -> int:
    list_only, extra_args = parse_args(list(argv if argv is not None else sys.argv[1:]))
    tests = load_tests()
    if list_only:
        print("\n".join(tests))
        return 0
    command = [sys.executable, "-m", "pytest", *extra_args, *tests]
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
