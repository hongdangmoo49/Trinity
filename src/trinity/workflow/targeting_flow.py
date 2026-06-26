"""Agent targeting and model override helpers for WorkflowEngine."""

from __future__ import annotations

from trinity.models import AgentSpec


class WorkflowTargetingFlow:
    """Normalize targeted agent and model override selections."""

    @staticmethod
    def decomposition_agents(
        agent_specs: dict[str, AgentSpec],
        active_agents: list[str],
    ) -> list[str] | dict[str, AgentSpec]:
        """Return the active agent list or the active subset of configured specs."""
        if not agent_specs:
            return list(active_agents)
        active = set(active_agents)
        return {
            name: spec
            for name, spec in agent_specs.items()
            if name in active
        }

    @staticmethod
    def effective_target_agents(
        active_agents: list[str],
        target_agents: list[str] | tuple[str, ...] | None,
    ) -> tuple[str, ...]:
        active = [
            str(agent).strip()
            for agent in active_agents
            if str(agent).strip()
        ]
        active_set = set(active)
        requested = [
            str(agent).strip()
            for agent in (target_agents or active)
            if str(agent).strip()
        ]
        selected = tuple(agent for agent in requested if agent in active_set)
        return selected or tuple(active)

    @staticmethod
    def normalized_model_overrides(
        agent_model_overrides: dict[str, str] | None,
        allowed_agents: tuple[str, ...] | list[str] = (),
    ) -> dict[str, str]:
        if not agent_model_overrides:
            return {}
        allowed = {
            str(agent).strip()
            for agent in allowed_agents
            if str(agent).strip()
        }
        return {
            str(agent).strip(): str(model).strip()
            for agent, model in agent_model_overrides.items()
            if str(agent).strip()
            and str(model).strip()
            and (not allowed or str(agent).strip() in allowed)
        }
