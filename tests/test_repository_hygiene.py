import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
GENERATED_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}
GENERATED_SUFFIXES = (".pyc", ".pyo")


def test_generated_python_artifacts_are_not_tracked() -> None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    tracked_generated = []
    for raw_path in result.stdout.splitlines():
        path = raw_path.strip()
        if not path:
            continue
        parts = set(PurePosixPath(path).parts)
        if parts & GENERATED_PARTS or path.endswith(GENERATED_SUFFIXES):
            tracked_generated.append(path)

    assert tracked_generated == []
