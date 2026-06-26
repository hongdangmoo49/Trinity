"""Provider runtime metadata observation helpers for WorkflowEngine."""

from __future__ import annotations

import time
from typing import Any

from trinity.workflow.models import (
    AgentRuntimeModel,
    AgentResourceProjection,
    ProviderSessionRef,
)


class WorkflowProviderObservations:
    """Merge provider runtime observations into the workflow session."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def record_provider_observations(self, metadata: dict[str, Any]) -> None:
        """Persist provider session/model observations from result metadata."""
        provider_sessions = metadata.get("provider_sessions")
        runtime_models = metadata.get("runtime_models")
        resource_projections = metadata.get("resource_projections")
        changed = False

        if isinstance(provider_sessions, dict):
            for key, value in provider_sessions.items():
                if not isinstance(value, dict):
                    continue
                session = ProviderSessionRef.from_dict(value)
                if not session.provider_session_id:
                    continue
                session_key = session.session_key or str(key)
                if not session_key:
                    continue
                self.engine.session.provider_sessions[session_key] = session
                changed = True

        if isinstance(runtime_models, dict):
            for key, value in runtime_models.items():
                if not isinstance(value, dict):
                    continue
                model = AgentRuntimeModel.from_dict(value)
                model_key = model.agent_name or str(key)
                if not model_key:
                    continue
                self.engine.session.runtime_models[model_key] = model
                changed = True

        if isinstance(resource_projections, dict):
            for key, value in resource_projections.items():
                if not isinstance(value, dict):
                    continue
                projection = AgentResourceProjection.from_dict(value)
                projection_key = str(key).strip() or projection.key
                if not projection_key:
                    continue
                self.engine.session.resource_projections[projection_key] = projection
                changed = True

        if not changed:
            return

        self.engine.session.updated_at = time.time()
        self.engine._persist(
            "provider_metadata_observed",
            {
                "provider_sessions": sorted(
                    self.engine.session.provider_sessions.keys()
                ),
                "runtime_models": sorted(self.engine.session.runtime_models.keys()),
                "resource_projections": sorted(
                    self.engine.session.resource_projections.keys()
                ),
            },
        )
