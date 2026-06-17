"""Trinity configuration — TOML-based config loader."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
import logging

from trinity.agent_profiles import agent_profile_overrides, resolve_agent_profile
from trinity.models import AgentSpec, Provider
from trinity.providers.policy import (
    DEFAULT_BROAD_WRITE_PATHS,
    DEFAULT_SHARED_WRITE_PATHS,
)

PROVIDER_STATE_MODES = {"user-home", "isolated"}
TRANSPORT_MODES = {"one-shot", "tmux"}
SYNTHESIS_MODES = {"auto", "model", "heuristic"}
RESOURCE_PROJECTION_MODES = {"managed-overlay", "prompt-only", "disabled"}
RESOURCE_COLLISION_POLICIES = {"namespace", "fail", "native-wins"}
RESOURCE_FAILURE_POLICIES = {
    "degrade",
    "skip",
    "fail-provider-call",
    "fail-workflow",
}
RESOURCE_ACTIVATIONS = {"auto", "project", "prompt-only", "off"}
PROVIDER_PROCESS_NAMESPACES = {"auto", "host", "wsl", "windows"}

logger = logging.getLogger(__name__)

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

    # Provider state/auth handling
    provider_state_mode: str = "user-home"  # "user-home" | "isolated"

    # Agent invocation transport
    transport_mode: str = "one-shot"  # "one-shot" | "tmux"
    provider_process_namespace: str = "auto"

    # Language (affects deliberation prompts + role prompts)
    lang: str = "en"  # "en" | "ko"

    # Deliberation
    max_deliberation_rounds: int = 5
    consensus_threshold: float = 0.6  # fraction of agents required
    round_timeout_seconds: float = 300.0
    execution_timeout_seconds: float = 1800.0
    provider_readiness_mode: str = "strict"  # "strict" | "degraded"
    provider_readiness_timeout_seconds: float = 20.0
    synthesis_mode: str = "auto"  # "auto" | "model" | "heuristic"
    synthesis_agent: str = ""
    synthesis_model: str = "strong"
    synthesis_timeout_seconds: float = 300.0
    synthesis_max_input_chars: int = 60_000

    # Execution policy
    parallel_shared_write_paths: list[str] = field(
        default_factory=lambda: sorted(DEFAULT_SHARED_WRITE_PATHS)
    )
    parallel_broad_write_paths: list[str] = field(
        default_factory=lambda: sorted(DEFAULT_BROAD_WRITE_PATHS)
    )

    # Context management
    context_rotate_threshold: float = 0.60
    keep_sections: list[str] = field(
        default_factory=lambda: ["## Current Goal", "## Agreed Conclusion"]
    )
    recent_rounds_on_rotate: int = 3
    summary_max_tokens: int = 500
    shared_max_bytes: int = 1_048_576
    shared_compact_target_bytes: int = 524_288
    shared_section_entry_max_chars: int = 12_000
    auto_compact_on_start: bool = True
    memory_index_enabled: bool = True
    memory_prompt_budget_tokens: int = 24_000
    memory_recent_records: int = 30
    memory_retrieval_max_bytes: int = 262_144
    compression_mode: str = "deterministic"
    repair_max_attempts: int = 3

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

    # Trinity-managed agent resources
    resources_enabled: bool = True
    resources_root: Path = field(default_factory=lambda: Path(".trinity/resources"))
    resource_projection_mode: str = "managed-overlay"
    resource_collision_policy: str = "namespace"
    resource_default_failure_policy: str = "degrade"
    resource_audit: bool = True

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
        # Detect language: explicit lang field, or infer from role prompts.
        # Older configs could persist lang="en" while Korean role prompts were
        # selected; prefer the observable agent language in that legacy mismatch.
        detected_lang = cls._detect_lang_from_agents(data.get("agents", {}))
        data = cls._normalize_legacy_agents(data, detected_lang)

        general = data.get("general", {})
        deliberation = data.get("deliberation", {})
        execution = data.get("execution", {})
        context = data.get("context", {})
        health = data.get("health", {})
        logging_conf = data.get("logging", {})
        resources_conf = data.get("resources", {})

        lang = general.get("lang", None)
        if lang is None or (lang == "en" and detected_lang == "ko"):
            lang = detected_lang

        agents = {}
        for name, agent_data in data.get("agents", {}).items():
            provider = Provider(agent_data.get("provider", "claude-code"))
            profile_data = (
                agent_data.get("profile", {})
                if isinstance(agent_data.get("profile", {}), dict)
                else {}
            )
            agent_resources = (
                agent_data.get("resources", {})
                if isinstance(agent_data.get("resources", {}), dict)
                else {}
            )
            agents[name] = AgentSpec(
                name=name,
                provider=provider,
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
                resource_packs=cls._string_list(agent_resources.get("packs", [])),
                resource_types=cls._string_list(agent_resources.get("types", [])),
                resource_disabled=cls._string_list(
                    agent_resources.get("disabled", [])
                ),
                resource_activation=cls._normalize_resource_activation(
                    agent_resources.get("activation", "auto")
                ),
                profile=resolve_agent_profile(name, provider, profile_data),
            )

        return cls(
            project_dir=project_dir,
            state_dir=(
                Path(general["state_dir"]) if "state_dir" in general else None
            ),
            session_name=general.get("session_name", "trinity"),
            provider_state_mode=cls._normalize_provider_state_mode(
                general.get("provider_state_mode", "user-home")
            ),
            transport_mode=cls._normalize_transport_mode(
                general.get("transport_mode", "one-shot")
            ),
            provider_process_namespace=cls._normalize_provider_process_namespace(
                general.get("provider_process_namespace", "auto")
            ),
            lang=lang,
            max_deliberation_rounds=deliberation.get(
                "max_rounds", general.get("max_deliberation_rounds", 5)
            ),
            consensus_threshold=deliberation.get(
                "consensus_threshold", general.get("consensus_threshold", 0.6)
            ),
            round_timeout_seconds=deliberation.get("round_timeout_seconds", 300.0),
            execution_timeout_seconds=float(
                deliberation.get("execution_timeout_seconds", 1800.0)
            ),
            provider_readiness_mode=deliberation.get(
                "provider_readiness_mode", "strict"
            ),
            provider_readiness_timeout_seconds=deliberation.get(
                "provider_readiness_timeout_seconds", 20.0
            ),
            synthesis_mode=cls._normalize_synthesis_mode(
                deliberation.get("synthesis_mode", "auto")
            ),
            synthesis_agent=str(deliberation.get("synthesis_agent", "")),
            synthesis_model=str(deliberation.get("synthesis_model", "strong")),
            synthesis_timeout_seconds=float(
                deliberation.get("synthesis_timeout_seconds", 300.0)
            ),
            synthesis_max_input_chars=int(
                deliberation.get("synthesis_max_input_chars", 60_000)
            ),
            parallel_shared_write_paths=cls._string_list(
                execution.get(
                    "parallel_shared_write_paths",
                    sorted(DEFAULT_SHARED_WRITE_PATHS),
                )
            ),
            parallel_broad_write_paths=cls._string_list(
                execution.get(
                    "parallel_broad_write_paths",
                    sorted(DEFAULT_BROAD_WRITE_PATHS),
                )
            ),
            context_rotate_threshold=context.get(
                "rotate_threshold", general.get("context_rotate_threshold", 0.60)
            ),
            keep_sections=context.get(
                "keep_sections", ["## Current Goal", "## Agreed Conclusion"]
            ),
            recent_rounds_on_rotate=context.get("recent_rounds_on_rotate", 3),
            summary_max_tokens=context.get("summary_max_tokens", 500),
            shared_max_bytes=int(context.get("shared_max_bytes", 1_048_576)),
            shared_compact_target_bytes=int(
                context.get("shared_compact_target_bytes", 524_288)
            ),
            shared_section_entry_max_chars=int(
                context.get("shared_section_entry_max_chars", 12_000)
            ),
            auto_compact_on_start=bool(context.get("auto_compact_on_start", True)),
            memory_index_enabled=bool(context.get("memory_index_enabled", True)),
            memory_prompt_budget_tokens=int(
                context.get("memory_prompt_budget_tokens", 24_000)
            ),
            memory_recent_records=int(context.get("memory_recent_records", 30)),
            memory_retrieval_max_bytes=int(
                context.get("memory_retrieval_max_bytes", 262_144)
            ),
            compression_mode=str(context.get("compression_mode", "deterministic")),
            repair_max_attempts=int(context.get("repair_max_attempts", 3)),
            prompt_compression_enabled=context.get("prompt_compression_enabled", True),
            prompt_compression_round_threshold=context.get("prompt_compression_round_threshold", 2),
            prompt_compression_max_summary_tokens=context.get("prompt_compression_max_summary_tokens", 200),
            caveman_mode=context.get("caveman_mode", True),
            caveman_intensity=context.get("caveman_intensity", "full"),
            health_check_interval_seconds=health.get("check_interval_seconds", 30.0),
            log_level=logging_conf.get("level", "INFO"),
            log_file=logging_conf.get("file", ".trinity/logs/trinity.log"),
            resources_enabled=bool(resources_conf.get("enabled", True)),
            resources_root=Path(resources_conf.get("root", ".trinity/resources")),
            resource_projection_mode=cls._normalize_resource_projection_mode(
                resources_conf.get("projection_mode", "managed-overlay")
            ),
            resource_collision_policy=cls._normalize_resource_collision_policy(
                resources_conf.get("collision_policy", "namespace")
            ),
            resource_default_failure_policy=cls._normalize_resource_failure_policy(
                resources_conf.get("default_failure_policy", "degrade")
            ),
            resource_audit=bool(resources_conf.get("audit", True)),
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
                    profile=resolve_agent_profile("claude", Provider.CLAUDE_CODE),
                ),
                "codex": AgentSpec(
                    name="codex",
                    provider=Provider.CODEX,
                    cli_command="codex",
                    role_prompt=roles["codex"],
                    enabled=False,  # Disabled by default until codex CLI is available
                    profile=resolve_agent_profile("codex", Provider.CODEX),
                ),
                "antigravity": AgentSpec(
                    name="antigravity",
                    provider=Provider.ANTIGRAVITY_CLI,
                    cli_command="agy",
                    role_prompt=roles["antigravity"],
                    enabled=False,  # Enabled by setup only when agy is selected
                    profile=resolve_agent_profile(
                        "antigravity",
                        Provider.ANTIGRAVITY_CLI,
                    ),
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
                "provider_state_mode": self.provider_state_mode,
                "transport_mode": self.transport_mode,
                "provider_process_namespace": self.provider_process_namespace,
                "max_deliberation_rounds": self.max_deliberation_rounds,
                "consensus_threshold": self.consensus_threshold,
                "context_rotate_threshold": self.context_rotate_threshold,
            },
            "resources": {
                "enabled": self.resources_enabled,
                "root": str(self.resources_root),
                "projection_mode": self.resource_projection_mode,
                "collision_policy": self.resource_collision_policy,
                "default_failure_policy": self.resource_default_failure_policy,
                "audit": self.resource_audit,
            },
            "deliberation": {
                "round_timeout_seconds": self.round_timeout_seconds,
                "execution_timeout_seconds": self.execution_timeout_seconds,
                "provider_readiness_mode": self.provider_readiness_mode,
                "provider_readiness_timeout_seconds": (
                    self.provider_readiness_timeout_seconds
                ),
                "synthesis_mode": self.synthesis_mode,
                "synthesis_agent": self.synthesis_agent,
                "synthesis_model": self.synthesis_model,
                "synthesis_timeout_seconds": self.synthesis_timeout_seconds,
                "synthesis_max_input_chars": self.synthesis_max_input_chars,
            },
            "context": {
                "shared_max_bytes": self.shared_max_bytes,
                "shared_compact_target_bytes": self.shared_compact_target_bytes,
                "shared_section_entry_max_chars": self.shared_section_entry_max_chars,
                "auto_compact_on_start": self.auto_compact_on_start,
                "memory_index_enabled": self.memory_index_enabled,
                "memory_prompt_budget_tokens": self.memory_prompt_budget_tokens,
                "memory_recent_records": self.memory_recent_records,
                "memory_retrieval_max_bytes": self.memory_retrieval_max_bytes,
                "compression_mode": self.compression_mode,
                "repair_max_attempts": self.repair_max_attempts,
                "prompt_compression_enabled": self.prompt_compression_enabled,
                "prompt_compression_round_threshold": (
                    self.prompt_compression_round_threshold
                ),
                "prompt_compression_max_summary_tokens": (
                    self.prompt_compression_max_summary_tokens
                ),
                "caveman_mode": self.caveman_mode,
                "caveman_intensity": self.caveman_intensity,
            },
            "execution": {
                "parallel_shared_write_paths": list(self.parallel_shared_write_paths),
                "parallel_broad_write_paths": list(self.parallel_broad_write_paths),
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
            if (
                spec.resource_packs
                or spec.resource_types
                or spec.resource_disabled
                or spec.resource_activation != "auto"
            ):
                agent_data["resources"] = {
                    "packs": list(spec.resource_packs),
                    "types": list(spec.resource_types),
                    "disabled": list(spec.resource_disabled),
                    "activation": spec.resource_activation,
                }
            profile_overrides = agent_profile_overrides(name, spec.provider, spec.profile)
            if profile_overrides:
                agent_data["profile"] = profile_overrides
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

    @staticmethod
    def _normalize_legacy_agents(data: dict, lang: str) -> dict:
        """Normalize deprecated Gemini agent config to Antigravity.

        The raw TOML dict must be normalized before Provider enum parsing so old
        user configs remain loadable after the Gemini runtime provider is
        removed.
        """
        agents_data = data.get("agents")
        if not isinstance(agents_data, dict):
            return data

        normalized = dict(data)
        normalized_agents: dict[str, dict] = {
            name: dict(agent_data)
            for name, agent_data in agents_data.items()
            if isinstance(agent_data, dict)
        }

        has_antigravity = "antigravity" in normalized_agents
        legacy_gemini = normalized_agents.get("gemini")
        if legacy_gemini and legacy_gemini.get("provider") == "gemini-cli":
            if has_antigravity:
                logger.warning(
                    "Ignoring deprecated [agents.gemini] config because "
                    "[agents.antigravity] is already present."
                )
                normalized_agents.pop("gemini", None)
            else:
                normalized_agents.pop("gemini", None)
                normalized_agents["antigravity"] = TrinityConfig._as_antigravity_agent(
                    legacy_gemini,
                    lang,
                )
                logger.warning(
                    "Migrated deprecated [agents.gemini] gemini-cli config to "
                    "[agents.antigravity] antigravity-cli."
                )

        for name, agent_data in list(normalized_agents.items()):
            if agent_data.get("provider") == "gemini-cli":
                normalized_agents[name] = TrinityConfig._as_antigravity_agent(
                    agent_data,
                    lang,
                    preserve_name=True,
                )
                logger.warning(
                    "Migrated deprecated gemini-cli provider for agent '%s' to "
                    "antigravity-cli.",
                    name,
                )

        normalized["agents"] = normalized_agents
        return normalized

    @staticmethod
    def _as_antigravity_agent(
        agent_data: dict,
        lang: str,
        preserve_name: bool = False,
    ) -> dict:
        """Return a copied agent dict using the Antigravity CLI provider."""
        migrated = dict(agent_data)
        migrated["provider"] = "antigravity-cli"
        migrated["cli_command"] = "agy"
        if not preserve_name:
            migrated["name"] = "antigravity"

        role_prompt = migrated.get("role_prompt", "")
        if TrinityConfig._is_default_gemini_role_prompt(role_prompt):
            from trinity.i18n import localized_roles

            roles = localized_roles(lang if lang in {"en", "ko"} else "en")
            migrated["role_prompt"] = roles["antigravity"]

        return migrated

    @staticmethod
    def _is_default_gemini_role_prompt(role_prompt: str) -> bool:
        """Return True when a role prompt is Trinity's old Gemini default."""
        if not role_prompt:
            return False

        legacy_prompts = (
            (
                "You are the Reviewer. You explore alternatives, identify "
                "potential issues, and ensure quality. Think critically "
                "about trade-offs and propose tests."
            ),
            (
                "당신은 리뷰어입니다. "
                "대안을 탐색하고 잠재적인 문제를 식별하며 품질을 보장합니다. "
                "트레이드오프에 대해 비판적으로 생각하고 테스트를 제안하세요."
            ),
        )
        return role_prompt in legacy_prompts

    @staticmethod
    def _normalize_provider_state_mode(value: str) -> str:
        """Validate provider auth/state handling mode from config."""
        normalized = (value or "user-home").strip().lower()
        if normalized not in PROVIDER_STATE_MODES:
            allowed = ", ".join(sorted(PROVIDER_STATE_MODES))
            raise ValueError(
                f"Unsupported provider_state_mode: {value!r}. "
                f"Expected one of: {allowed}"
            )
        return normalized

    @staticmethod
    def _normalize_transport_mode(value: str) -> str:
        """Validate agent invocation transport mode from config."""
        normalized = (value or "one-shot").strip().lower()
        if normalized not in TRANSPORT_MODES:
            allowed = ", ".join(sorted(TRANSPORT_MODES))
            raise ValueError(
                f"Unsupported transport_mode: {value!r}. "
                f"Expected one of: {allowed}"
            )
        return normalized

    @staticmethod
    def _normalize_provider_process_namespace(value: str) -> str:
        """Validate provider process namespace policy."""
        normalized = (value or "auto").strip().lower()
        if normalized not in PROVIDER_PROCESS_NAMESPACES:
            allowed = ", ".join(sorted(PROVIDER_PROCESS_NAMESPACES))
            raise ValueError(
                f"Unsupported provider_process_namespace: {value!r}. "
                f"Expected one of: {allowed}"
            )
        return normalized

    @staticmethod
    def _normalize_resource_projection_mode(value: str) -> str:
        """Validate Trinity resource projection mode."""
        normalized = (value or "managed-overlay").strip().lower()
        if normalized not in RESOURCE_PROJECTION_MODES:
            allowed = ", ".join(sorted(RESOURCE_PROJECTION_MODES))
            raise ValueError(
                f"Unsupported resource projection_mode: {value!r}. "
                f"Expected one of: {allowed}"
            )
        return normalized

    @staticmethod
    def _normalize_resource_collision_policy(value: str) -> str:
        """Validate Trinity resource collision policy."""
        normalized = (value or "namespace").strip().lower()
        if normalized not in RESOURCE_COLLISION_POLICIES:
            allowed = ", ".join(sorted(RESOURCE_COLLISION_POLICIES))
            raise ValueError(
                f"Unsupported resource collision_policy: {value!r}. "
                f"Expected one of: {allowed}"
            )
        return normalized

    @staticmethod
    def _normalize_resource_failure_policy(value: str) -> str:
        """Validate Trinity resource failure policy."""
        normalized = (value or "degrade").strip().lower()
        if normalized not in RESOURCE_FAILURE_POLICIES:
            allowed = ", ".join(sorted(RESOURCE_FAILURE_POLICIES))
            raise ValueError(
                f"Unsupported resource failure_policy: {value!r}. "
                f"Expected one of: {allowed}"
            )
        return normalized

    @staticmethod
    def _normalize_resource_activation(value: str) -> str:
        """Validate per-agent Trinity resource activation mode."""
        normalized = (value or "auto").strip().lower()
        if normalized not in RESOURCE_ACTIVATIONS:
            allowed = ", ".join(sorted(RESOURCE_ACTIVATIONS))
            raise ValueError(
                f"Unsupported agent resource activation: {value!r}. "
                f"Expected one of: {allowed}"
            )
        return normalized

    @staticmethod
    def _normalize_synthesis_mode(value: str) -> str:
        """Validate central synthesis mode from config."""
        normalized = (value or "auto").strip().lower()
        if normalized not in SYNTHESIS_MODES:
            allowed = ", ".join(sorted(SYNTHESIS_MODES))
            raise ValueError(
                f"Unsupported synthesis_mode: {value!r}. "
                f"Expected one of: {allowed}"
            )
        return normalized

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return [str(value)]
