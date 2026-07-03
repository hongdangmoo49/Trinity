from __future__ import annotations

import ast
from pathlib import Path


def test_test_modules_do_not_shadow_duplicate_top_level_tests() -> None:
    duplicates: list[str] = []
    for path in sorted(Path("tests").glob("test*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        seen: dict[str, int] = {}
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not node.name.startswith("test_"):
                continue
            first_line = seen.setdefault(node.name, node.lineno)
            if first_line != node.lineno:
                duplicates.append(
                    f"{path}:{node.lineno} shadows {node.name} at {first_line}"
                )

    assert duplicates == []
