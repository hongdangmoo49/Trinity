"""Trinity configuration — TOML-based config loader."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from trinity.models import AgentSpec, Provider

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]


@dataclass
class TrinityConfig:
    """Top-level Trinity configuration."""

    # Paths
    project_dir: Path = field(default_factory=lambda: Path.cwd())
    state_dir: Path | None = None  # defaults to project_dir/.trinity

    # Session
    session_name: str = "trinity"

    # Language (affects deliberation prompts + role prompts)
    lang: str = "en"  # "en" | "ko"

    # Deliberation
    max_deliberation_rounds: int = 5
    consensus_threshold: float = 0.6  # fraction of agents required
    round_timeout_seconds: float = 120.0
    provider_readiness_mode: str = "strict"  # "strict" | "degraded"
    provider_readiness_timeout_seconds: float = 20.0

    # Context management
    context_rotate_threshold: float = 0.60
    keep_sections: list[str] = field(
        default_factory=lambda: ["## Current Goal", "## Agreed Conclusion"]
    )
    recent_rounds_on_rotate: int = 3
    summary_max_tokens: int = 500

    # Prompt compression (Phase 7)
    prompt_compression_enabled: bool = True
    prompt_compression_round_threshold: int = 2
    prompt_compression_max_summary_tokens: int = 200

    # Caveman output compression (default: on, full intensity)
    caveman_mode: bool = True
    caveman_intensity: str = "full"  # "lite" | "full" | "ultra"

    # Health
    health_check_interval_seconds: float = 30.0

    # Logging
    log_level: str = "INFO"
    log_file: str = ".trinity/logs/trinity.log"

    # Agents
    agents: dict[str, AgentSpec] = field(default_factory=dict)

    @property
    def effective_state_dir(self) -> Path:
        """Resolved state directory."""
        if self.state_dir:
            return self.state_dir
        return self.project_dir / ".trinity"

    @property
    def shared_context_path(self) -> Path:
        return self.effective_state_dir / "shared.md"

    @property
    def active_agents(self) -> dict[str, AgentSpec]:
        """Only enabled agents."""
        return {name: spec for name, spec in self.agents.items() if spec.enabled}

    @classmethod
    def load(cls, path: Path) -> "TrinityConfig":
        """Load config from a TOML file."""
        if tomllib is None:
            raise RuntimeError(
                "No TOML parser available. Install tomli: pip install tomli"
            )

        text = path.read_text(encoding="utf-8")
        data = tomllib.loads(text)
        # path = <project>/.trinity/trinity.config → project_dir = <project>/
        return cls._from_dict(data, path.parent.parent)

    @classmethod
    def _from_dict(cls, data: dict, project_dir: Path) -> "TrinityConfig":
        """Parse config from a deserialized TOML dict."""
        general = data.get("general", {})
        deliberation = data.get("deliberation", {})
        context = data.get("context", {})
        health = data.get("health", {})
        logging_conf = data.get("logging", {})

        # Detect language: explicit lang field, or infer from role prompts
        lang = general.get("lang", None)
        if lang is None:
            lang = cls._detect_lang_from_agents(data.get("agents", {}))

        agents = {}
        for name, agent_data in data.get("agents", {}).items():
            agents[name] = AgentSpec(
                name=name,
                provider=Provider(agent_data.get("provider", "claude-code")),
                cli_command=agent_data.get("cli_command", name),
                model=agent_data.get("model", "default"),
                role_prompt=agent_data.get("role_prompt", ""),
                role_file=(
                    Path(agent_data["role_file"])
                    if "role_file" in agent_data
                    else None
                ),
                workspace_mode=agent_data.get("workspace_mode", "inplace"),
                branch_template=agent_data.get("branch_template", f"trinity/{name}"),
                context_budget=agent_data.get("context_budget", 0),
                enabled=agent_data.get("enabled", True),
                extra_args=agent_data.get("extra_args", []),
            )

        return cls(
            project_dir=project_dir,
            state_dir=(
                Path(general["state_dir"]) if "state_dir" in general else None
            ),
            session_name=general.get("session_name", "trinity"),
            lang=lang,
            max_deliberation_rounds=deliberation.get(
                "max_rounds", general.get("max_deliberation_rounds", 5)
            ),
            consensus_threshold=deliberation.get(
                "consensus_threshold", general.get("consensus_threshold", 0.6)
            ),
            round_timeout_seconds=deliberation.get("round_timeout_seconds", 120.0),
            provider_readiness_mode=deliberation.get(
                "provider_readiness_mode", "strict"
            ),
            provider_readiness_timeout_seconds=deliberation.get(
                "provider_readiness_timeout_seconds", 20.0
            ),
            context_rotate_threshold=context.get(
                "rotate_threshold", general.get("context_rotate_threshold", 0.60)
            ),
            keep_sections=context.get(
                "keep_sections", ["## Current Goal", "## Agreed Conclusion"]
            ),
            recent_rounds_on_rotate=context.get("recent_rounds_on_rotate", 3),
            summary_max_tokens=context.get("summary_max_tokens", 500),
            prompt_compression_enabled=context.get("prompt_compression_enabled", True),
            prompt_compression_round_threshold=context.get("prompt_compression_round_threshold", 2),
            prompt_compression_max_summary_tokens=context.get("prompt_compression_max_summary_tokens", 200),
            caveman_mode=context.get("caveman_mode", True),
            caveman_intensity=context.get("caveman_intensity", "full"),
            health_check_interval_seconds=health.get("check_interval_seconds", 30.0),
            log_level=logging_conf.get("level", "INFO"),
            log_file=logging_conf.get("file", ".trinity/logs/trinity.log"),
            agents=agents,
        )

    @classmethod
    def default_config(cls, project_dir: Path | None = None, lang: str = "en") -> "TrinityConfig":
        """Create a config with sensible defaults for 3 agents.

        Args:
            project_dir: Project root directory.
            lang: "en" for English role prompts, "ko" for Korean.
        """
        from trinity.i18n import localized_roles_with_caveman

        pd = project_dir or Path.cwd()
        roles = localized_roles_with_caveman(lang)
        return cls(
            project_dir=pd,
            lang=lang,
            agents={
                "claude": AgentSpec(
                    name="claude",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    role_prompt=roles["claude"],
                    extra_args=["--dangerously-skip-permissions"],
                ),
                "codex": AgentSpec(
                    name="codex",
                    provider=Provider.CODEX,
                    cli_command="codex",
                    role_prompt=roles["codex"],
                    enabled=False,  # Disabled by default until codex CLI is available
                ),
                "gemini": AgentSpec(
                    name="gemini",
                    provider=Provider.GEMINI_CLI,
                    cli_command="gemini",
                    role_prompt=roles["gemini"],
                    enabled=False,  # Disabled by default until gemini CLI is available
                ),
            },
        )

    def save(self, path: Path) -> None:
        """Serialize config to TOML file."""
        import tomli_w

        data = {
            "general": {
                "session_name": self.session_name,
                "lang": self.lang,
                "max_deliberation_rounds": self.max_deliberation_rounds,
                "consensus_threshold": self.consensus_threshold,
                "context_rotate_threshold": self.context_rotate_threshold,
            },
            "deliberation": {
                "provider_readiness_mode": self.provider_readiness_mode,
                "provider_readiness_timeout_seconds": (
                    self.provider_readiness_timeout_seconds
                ),
            },
            "context": {
                "caveman_mode": self.caveman_mode,
                "caveman_intensity": self.caveman_intensity,
            },
            "agents": {},
        }

        for name, spec in self.agents.items():
            agent_data = {
                "provider": spec.provider.value,
                "cli_command": spec.cli_command,
                "model": spec.model,
                "enabled": spec.enabled,
                "workspace_mode": spec.workspace_mode,
                "context_budget": spec.context_budget,
            }
            if spec.role_prompt:
                agent_data["role_prompt"] = spec.role_prompt
            if spec.extra_args:
                agent_data["extra_args"] = spec.extra_args
            data["agents"][name] = agent_data

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(tomli_w.dumps(data).encode("utf-8"))

    @staticmethod
    def _detect_lang_from_agents(agents_data: dict) -> str:
        """Detect language from existing role prompts.

        If any role prompt contains Korean characters (hangul), return "ko".
        Otherwise return "en". This handles configs created before the
        lang field was added.
        """
        import re
        hangul = re.compile(r"[ㄱ-ㆎ가-힣]")
        for agent_data in agents_data.values():
            role = agent_data.get("role_prompt", "")
            if hangul.search(role):
                return "ko"
        return "en"
