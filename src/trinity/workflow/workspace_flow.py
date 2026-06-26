"""Target workspace selection helpers for WorkflowEngine."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any


class WorkflowWorkspaceFlow:
    """Manage selected implementation workspace state."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def set_target_workspace(
        self,
        path: Path,
        *,
        control_repo_confirmed: bool = False,
    ) -> None:
        """Persist the workspace where provider implementation may write files."""
        resolved = path.expanduser().resolve()
        self.engine.session.target_workspace = resolved
        self.engine.session.control_repo_target_confirmed = control_repo_confirmed
        self.engine.session.updated_at = time.time()
        self.engine._persistence_flow().persist(
            "target_workspace_selected",
            {
                "target_workspace": str(resolved),
                "control_repo_target_confirmed": control_repo_confirmed,
            },
        )

    def clear_target_workspace(self) -> None:
        """Clear the selected implementation workspace."""
        self.engine.session.target_workspace = None
        self.engine.session.control_repo_target_confirmed = False
        self.engine.session.updated_at = time.time()
        self.engine._persistence_flow().persist("target_workspace_cleared", {})
