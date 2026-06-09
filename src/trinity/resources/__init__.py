"""Trinity-managed agent resource overlay support."""

from trinity.resources.models import (
    AgentResourceProjection,
    AgentResourceRef,
    ResourceOverlayContext,
    ResourcePathSet,
)
from trinity.resources.projector import ResourceProjector
from trinity.resources.registry import ResourceRegistry

__all__ = [
    "AgentResourceProjection",
    "AgentResourceRef",
    "ResourceOverlayContext",
    "ResourcePathSet",
    "ResourceProjector",
    "ResourceRegistry",
]
