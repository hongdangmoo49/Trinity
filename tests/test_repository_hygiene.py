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


def test_pypi_publish_on_main_and_requires_full_tests() -> None:
    workflow = (ROOT / ".github" / "workflows" / "publish-pypi.yml").read_text(
        encoding="utf-8"
    )

    assert "\n  push:" in workflow
    assert "branches:\n      - main" in workflow
    assert "\n  workflow_dispatch:" in workflow
    assert "needs:\n      - test\n      - full-test" in workflow
    assert "run: uv run pytest -q" in workflow
