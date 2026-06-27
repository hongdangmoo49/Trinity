from scripts.classify_ci_change import classify, is_version_only_diff


def test_docs_only_change_uses_docs_version_fast_path() -> None:
    result = classify(["docs/plans/example.md", "README.md"], {})

    assert result.ci_mode == "docs_version_only"
    assert result.changed_count == 2


def test_docs_with_version_bump_uses_docs_version_fast_path() -> None:
    diffs = {
        "pyproject.toml": '\n-version = "1.0.1"\n+version = "1.0.2"\n',
        "src/trinity/__init__.py": '\n-__version__ = "1.0.1"\n+__version__ = "1.0.2"\n',
        "uv.lock": '\n name = "trinity-agent"\n-version = "1.0.1"\n+version = "1.0.2"\n',
    }

    result = classify(
        [
            "docs/plans/example.md",
            "pyproject.toml",
            "src/trinity/__init__.py",
            "uv.lock",
        ],
        diffs,
    )

    assert result.ci_mode == "docs_version_only"
    assert result.changed_count == 4


def test_source_change_requires_smoke() -> None:
    result = classify(["src/trinity/cli.py"], {})

    assert result.ci_mode == "required_smoke"


def test_pyproject_dependency_change_requires_smoke() -> None:
    diff = '\n-dependencies = ["click>=8.1"]\n+dependencies = ["click>=8.2"]\n'

    assert not is_version_only_diff("pyproject.toml", diff)
    assert classify(["pyproject.toml"], {"pyproject.toml": diff}).ci_mode == "required_smoke"


def test_uv_lock_other_package_version_change_requires_smoke() -> None:
    diff = '\n name = "click"\n-version = "8.1.0"\n+version = "8.2.0"\n'

    assert not is_version_only_diff("uv.lock", diff)
    assert classify(["uv.lock"], {"uv.lock": diff}).ci_mode == "required_smoke"


def test_empty_change_requires_smoke() -> None:
    result = classify([], {})

    assert result.ci_mode == "required_smoke"
