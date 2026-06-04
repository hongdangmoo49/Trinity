"""Deliberation primitives and synthesis contracts."""

from trinity.deliberation.consensus import ConsensusEngine
from trinity.deliberation.distributor import TaskDistributor
from trinity.deliberation.protocol import DeliberationProtocol, RoundBudgetWarning
from trinity.deliberation.synthesis import (
    FallbackSynthesisAgent,
    HeuristicSynthesisAgent,
    ModelBackedSynthesisAgent,
    SynthesisValidationError,
    SynthesisAgent,
    SynthesisInput,
    SynthesisResult,
)

__all__ = [
    "ConsensusEngine",
    "DeliberationProtocol",
    "FallbackSynthesisAgent",
    "HeuristicSynthesisAgent",
    "ModelBackedSynthesisAgent",
    "RoundBudgetWarning",
    "SynthesisAgent",
    "SynthesisInput",
    "SynthesisResult",
    "SynthesisValidationError",
    "TaskDistributor",
]
