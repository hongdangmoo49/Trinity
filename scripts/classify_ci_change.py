"""Classify changed files for Trinity CI smoke selection."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass


DOC_ROOTS = ("docs/",)
DOC_FILES = {"README.md"}
VERSION_FILES = {"pyproject.toml", "uv.lock", "src/trinity/__init__.py"}

PROJECT_VERSION_RE = re.compile(r'version\s*=\s*"\d+\.\d+\.\d+(?:[-+][^"]+)?"')
INIT_VERSION_RE = re.compile(r'__version__\s*=\s*"\d+\.\d+\.\d+(?:[-+][^"]+)?"')


@dataclass(frozen=True)
class ChangeClassification:
    ci_mode: str
    changed_count: int


def is_doc_path(path: str) -> bool:
    return path.startswith(DOC_ROOTS) or path in DOC_FILES


def changed_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        check=True,
        text=True,
        capture_output=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def file_diff(base: str, head: str, path: str) -> str:
    result = subprocess.run(
        ["git", "diff", "--unified=1", base, head, "--", path],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def changed_diff_lines(diff: str) -> list[str]:
    lines: list[str] = []
    for line in diff.splitlines():
        if not line.startswith(("+", "-")):
            continue
        if line.startswith(("+++", "---")):
            continue
        lines.append(line[1:].strip())
    return lines


def is_version_only_diff(path: str, diff: str) -> bool:
    changed = changed_diff_lines(diff)
    if not changed:
        return True
    if path == "src/trinity/__init__.py":
        return all(INIT_VERSION_RE.fullmatch(line) for line in changed)
    if path == "pyproject.toml":
        return all(PROJECT_VERSION_RE.fullmatch(line) for line in changed)
    if path == "uv.lock":
        return (
            'name = "trinity-agent"' in diff
            and all(PROJECT_VERSION_RE.fullmatch(line) for line in changed)
        )
    return False


def classify(paths: list[str], diffs: dict[str, str]) -> ChangeClassification:
    if not paths:
        return ChangeClassification(ci_mode="required_smoke", changed_count=0)

    for path in paths:
        if is_doc_path(path):
            continue
        if path in VERSION_FILES and is_version_only_diff(path, diffs.get(path, "")):
            continue
        return ChangeClassification(ci_mode="required_smoke", changed_count=len(paths))

    return ChangeClassification(ci_mode="docs_version_only", changed_count=len(paths))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify Trinity CI change scope.")
    parser.add_argument("base", help="base commit")
    parser.add_argument("head", help="head commit")
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="print GitHub Actions output key/value lines",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv if argv is not None else sys.argv[1:]))
    paths = changed_paths(args.base, args.head)
    diffs = {path: file_diff(args.base, args.head, path) for path in paths if path in VERSION_FILES}
    result = classify(paths, diffs)
    if args.github_output:
        print(f"ci_mode={result.ci_mode}")
        print(f"changed_count={result.changed_count}")
    else:
        print(result.ci_mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
