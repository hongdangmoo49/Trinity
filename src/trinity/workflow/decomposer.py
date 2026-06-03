"""BlueprintDecomposer — splits a Blueprint into agent-scoped WorkPackages."""

from __future__ import annotations

from collections import defaultdict

from trinity.models import ArchitectureComponent, Blueprint, WorkPackage, WorkStatus


class BlueprintDecomposer:
    """Decompose a Blueprint into WorkPackages, one per agent.

    Strategy
    --------
    1. Group ArchitectureComponents by ``owner_agent`` when it matches an
       active agent name.
    2. Distribute unassigned components round-robin across agents.
    3. Each WorkPackage receives scoped acceptance criteria.
    """

    def decompose(self, blueprint: Blueprint, agents: list[str]) -> list[WorkPackage]:
        """Return one WorkPackage per agent, covering all architecture components.

        Parameters
        ----------
        blueprint:
            The architecture blueprint to decompose.
        agents:
            Active agent names.  If empty, returns an empty list.

        Returns
        -------
        list[WorkPackage]
            One package per agent with sequential ids (WP-001, WP-002, ...).
        """
        if not agents:
            return []

        agent_set = set(agents)

        # Step 1 — group components whose owner_agent matches an active agent.
        assigned: dict[str, list[ArchitectureComponent]] = defaultdict(list)
        unassigned: list[ArchitectureComponent] = []

        for component in blueprint.architecture:
            if component.owner_agent and component.owner_agent in agent_set:
                assigned[component.owner_agent].append(component)
            else:
                unassigned.append(component)

        # Step 2 — distribute unassigned components round-robin.
        if unassigned:
            sorted_agents = sorted(agents)
            for idx, component in enumerate(unassigned):
                target_agent = sorted_agents[idx % len(sorted_agents)]
                assigned[target_agent].append(component)

        # Step 3 — build WorkPackages.
        packages: list[WorkPackage] = []
        for seq, agent in enumerate(agents, start=1):
            components = assigned.get(agent, [])
            if not components:
                continue

            package_id = f"WP-{seq:03d}"
            component_names = ", ".join(c.name for c in components)

            objective = (
                f"Implement {component_names} for {blueprint.title}"
                if components
                else f"Contribute to {blueprint.title} per the shared design"
            )

            scope = [
                f"{c.name}: {c.responsibility}" for c in components
            ]

            acceptance = list(blueprint.acceptance_criteria)
            acceptance.extend(
                f"{c.name}: {c.responsibility} — implemented and tested"
                for c in components
            )

            packages.append(
                WorkPackage(
                    id=package_id,
                    title=f"{blueprint.title} — {agent} package",
                    owner_agent=agent,
                    objective=objective,
                    scope=scope,
                    acceptance_criteria=acceptance,
                    status=WorkStatus.PENDING,
                )
            )

        return packages
