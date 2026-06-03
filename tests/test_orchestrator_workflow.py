"""Tests for orchestrator integration with workflow engine (v0.7.0)."""

import pytest
from trinity.config import TrinityConfig
from trinity.orchestrator import TrinityOrchestrator


class TestWorkflowConfig:
    def test_workflow_config_defaults(self):
        config = TrinityConfig()
        assert config.workflow_mode == "guided"
        assert config.strict_provider_readiness is True
        assert config.allow_degraded_agent_set is False
        assert config.persist_workflow_state is True

    def test_workflow_config_from_dict(self):
        from pathlib import Path
        config = TrinityConfig._from_dict(
            {"workflow": {"mode": "autonomous", "strict_provider_readiness": False}},
            Path.cwd(),
        )
        assert config.workflow_mode == "autonomous"
        assert config.strict_provider_readiness is False


class TestOrchestratorWorkflowAttributes:
    def test_orchestrator_has_workflow_attributes(self):
        config = TrinityConfig()
        orch = TrinityOrchestrator(config)
        assert hasattr(orch, "readiness_gate")
        assert hasattr(orch, "workflow_engine")
        assert hasattr(orch, "lifecycle_guard")
        assert hasattr(orch, "workflow_persistence")
