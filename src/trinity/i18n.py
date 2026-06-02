"""Trinity i18n — localized strings for setup wizard and CLI.

Central source of all user-facing strings that vary by language.
Currently supports English (en) and Korean (ko).

Usage:
    from trinity.i18n import get_strings, localized_roles

    S = get_strings("ko")
    print(S.wizard_title)

    roles = localized_roles("ko")
    print(roles["claude"])
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Type alias for supported languages
Lang = Literal["en", "ko"]

# ─── Agent Role Prompts ──────────────────────────────────────────────────

ROLE_PROMPTS: dict[Lang, dict[str, str]] = {
    "en": {
        "claude": (
            "You are the Architect. You design systems, review code, "
            "and make high-level technical decisions. Think carefully "
            "and provide structured, well-reasoned opinions."
        ),
        "codex": (
            "You are the Implementer. You write clean, efficient code "
            "based on architectural decisions. Focus on practical "
            "implementation and edge cases."
        ),
        "gemini": (
            "You are the Reviewer. You explore alternatives, identify "
            "potential issues, and ensure quality. Think critically "
            "about trade-offs and propose tests."
        ),
    },
    "ko": {
        "claude": (
            "당신은 아키텍트입니다. "
            "시스템을 설계하고 코드를 리뷰하며, "
            "고수준의 기술적 결정을 내립니다. "
            "신중하게 생각하고 논리적이고 체계적인 의견을 제시하세요."
        ),
        "codex": (
            "당신은 구현자입니다. "
            "아키텍처 결정에 기반하여 깊끔하고 효율적인 코드를 작성합니다. "
            "실제 구현과 엓지 케이스에 집중하세요."
        ),
        "gemini": (
            "당신은 리뷰어입니다. "
            "대안을 탐색하고 잠재적인 문제를 식별하며 품질을 보장합니다. "
            "트레이드오프에 대해 비판적으로 생각하고 테스트를 제안하세요."
        ),
    },
}


# ─── Localized Strings Dataclass ─────────────────────────────────────────

@dataclass(frozen=True)
class Strings:
    """All localizable strings used in the setup wizard and CLI init."""

    # Wizard welcome
    wizard_title: str
    wizard_body: str

    # Language selection (Step 0)
    lang_title: str
    lang_prompt: str

    # Step 1: Detect
    step1_title: str
    col_tool: str
    col_status: str
    col_info: str
    detected: str
    not_found: str
    install_hint: str
    no_tools: str

    # Step 2: Select
    step2_title: str
    enable_prompt: str
    recommended: str
    selected_agents: str
    no_agents: str

    # Step 3: Customize
    step3_title: str
    step3_hint: str
    current_role: str
    customize_role: str
    enter_role: str
    context_budget: str
    change_budget: str
    enter_budget: str

    # Step 4: Review
    step4_title: str
    col_agent: str
    col_provider: str
    col_role: str
    col_budget: str
    save_prompt: str

    # CLI init summary
    summary_initialized: str
    summary_directory: str
    summary_config: str
    summary_shared: str
    summary_agents: str
    summary_active: str
    summary_skipped: str
    summary_not_installed: str
    summary_start_hint: str
    summary_start_tui: str
    summary_start_ask: str

    # Setup cancelled
    cancelled: str


EN_STRINGS = Strings(
    wizard_title="Welcome",
    wizard_body="Let's configure your multi-agent AI environment.",
    lang_title="🌐 Language / 언어",
    lang_prompt="Select language",
    step1_title="🔍 Step 1: Detecting AI CLI tools...",
    col_tool="Tool",
    col_status="Status",
    col_info="Version / Info",
    detected="✅ Detected",
    not_found="❌ Not found",
    install_hint="💡 Install missing tools:",
    no_tools=(
        "No AI CLI tools detected. Install at least one of: "
        "claude, codex, gemini"
    ),
    step2_title="📋 Step 2: Select agents to enable",
    enable_prompt="Enable {display_name} ({agent_name})?",
    recommended=" (recommended)",
    selected_agents="Selected {count} agent(s): {names}",
    no_agents="No agents selected. Setup cancelled.",
    step3_title="⚙️  Step 3: Customize agent roles",
    step3_hint="Press Enter to accept defaults, or type custom values.",
    current_role="Current role: {role}",
    customize_role="Customize role for {name}?",
    enter_role="Enter role prompt",
    context_budget="Context budget: {budget:,} tokens",
    change_budget="Change context budget?",
    enter_budget="Enter context budget (tokens)",
    step4_title="📝 Step 4: Review configuration",
    col_agent="Agent",
    col_provider="Provider",
    col_role="Role",
    col_budget="Context Budget",
    save_prompt="Save this configuration?",
    summary_initialized="✓ Trinity initialized!",
    summary_directory="Directory: {path}",
    summary_config="Config:    {path}",
    summary_shared="Shared:    {path}",
    summary_agents="Agents: {agents} (active)",
    summary_active="active",
    summary_skipped="Skipped: {agents} (CLI not installed)",
    summary_not_installed="CLI not installed",
    summary_start_hint="💡 Start deliberation:",
    summary_start_tui="trinity          — Interactive TUI mode",
    summary_start_ask='trinity ask "..." — One-shot question',
    cancelled="Setup cancelled.",
)

KO_STRINGS = Strings(
    wizard_title="환영합니다",
    wizard_body="멀티 에이전트 AI 환경을 설정합니다.",
    lang_title="🌐 Language / 언어",
    lang_prompt="언어를 선택하세요",
    step1_title="🔍 Step 1: AI CLI 도구 탐지 중...",
    col_tool="도구",
    col_status="상태",
    col_info="버전 / 정보",
    detected="✅ 감지됨",
    not_found="❌ 없음",
    install_hint="💡 누락된 도구 설치:",
    no_tools=(
        "AI CLI 도구가 감지되지 않았습니다. claude, codex, gemini 중 "
        "최소 하나를 설치하세요."
    ),
    step2_title="📋 Step 2: 활성화할 에이전트 선택",
    enable_prompt="{display_name} ({agent_name})을(를) 활성화하시겠습니까?",
    recommended=" (권장)",
    selected_agents="{count}개 에이전트 선택됨: {names}",
    no_agents="선택된 에이전트가 없습니다. 설정이 취소되었습니다.",
    step3_title="⚙️  Step 3: 에이전트 역할 커스터마이징",
    step3_hint="Enter를 눌러 기본값을 적용하거나, 직접 입력하세요.",
    current_role="현재 역할: {role}",
    customize_role="{name}의 역할을 커스터마이징하시겠습니까?",
    enter_role="역할 프롬프트를 입력하세요",
    context_budget="컨텍스트 예산: {budget:,} 토큰",
    change_budget="컨텍스트 예산을 변경하시겠습니까?",
    enter_budget="컨텍스트 예산을 입력하세요 (토큰)",
    step4_title="📝 Step 4: 설정 검토",
    col_agent="에이전트",
    col_provider="제공자",
    col_role="역할",
    col_budget="컨텍스트 예산",
    save_prompt="이 설정을 저장하시겠습니까?",
    summary_initialized="✓ Trinity 초기화 완료!",
    summary_directory="디렉토리: {path}",
    summary_config="설정:      {path}",
    summary_shared="공유:      {path}",
    summary_agents="에이전트: {agents} (활성)",
    summary_active="활성",
    summary_skipped="건너뜀: {agents} (CLI 미설치)",
    summary_not_installed="CLI 미설치",
    summary_start_hint="💡 토론 시작:",
    summary_start_tui="trinity          — 대화형 TUI 모드",
    summary_start_ask='trinity ask "..." — 단발성 질문',
    cancelled="설정이 취소되었습니다.",
)

_STRINGS: dict[Lang, Strings] = {
    "en": EN_STRINGS,
    "ko": KO_STRINGS,
}


# ─── Public API ──────────────────────────────────────────────────────────

def get_strings(lang: Lang = "en") -> Strings:
    """Get the localized string bundle for a language.

    Args:
        lang: "en" for English, "ko" for Korean.

    Returns:
        Strings dataclass with all localized values.
    """
    return _STRINGS[lang]


def role_prompt(agent_name: str, lang: Lang = "en") -> str:
    """Get a single agent's role prompt in the specified language.

    Args:
        agent_name: One of "claude", "codex", "gemini".
        lang: "en" or "ko".

    Returns:
        Localized role prompt string.
    """
    return ROLE_PROMPTS[lang][agent_name]


def localized_roles(lang: Lang = "en") -> dict[str, str]:
    """Get all agent role prompts in the specified language.

    Args:
        lang: "en" or "ko".

    Returns:
        Dict of agent_name → localized role prompt.
    """
    return dict(ROLE_PROMPTS[lang])


# ─── Caveman Compression ─────────────────────────────────────────────────

CAVEMAN_RULES: dict[str, str] = {
    "lite": (
        "Drop filler words, hedging, and pleasantries. "
        "Keep full sentences and articles. Professional but tight."
    ),
    "full": (
        "Drop articles (a, an, the), filler, hedging (I think, perhaps), "
        "and pleasantries. Use sentence fragments. Prefer short synonyms. "
        "No intro phrases like 'Here is' or 'Let me'. "
        "Code and technical terms stay untouched."
    ),
    "ultra": (
        "Abbreviate prose words (database→DB, authentication→auth, "
        "configuration→config). Use arrows (→) for causality. "
        "Strip conjunctions where unambiguous. "
        "NEVER abbreviate code symbols, function names, or identifiers. "
        "No filler, no hedging, no pleasantries."
    ),
}

CAVEMAN_REINFORCEMENT: dict[str, str] = {
    "lite": "[Respond in concise professional style. No filler.]",
    "full": "[Caveman: respond in compressed style. No articles, no filler, fragments OK.]",
    "ultra": "[Caveman ULTRA: max compression. Abbreviate prose, preserve all code symbols.]",
}

VALID_CAVEMAN_INTENSITIES = ("lite", "full", "ultra")


def get_agent_prompt(
    agent_name: str,
    lang: Lang = "en",
    caveman_mode: bool = True,
    caveman_intensity: str = "full",
) -> str:
    """Get an agent's role prompt, optionally with caveman compression rules.

    Args:
        agent_name: One of "claude", "codex", "gemini".
        lang: "en" or "ko".
        caveman_mode: Whether to append caveman compression rules.
        caveman_intensity: "lite", "full", or "ultra".

    Returns:
        Role prompt string, with caveman rules appended if enabled.
    """
    base = ROLE_PROMPTS[lang][agent_name]
    if caveman_mode and caveman_intensity in CAVEMAN_RULES:
        rules = CAVEMAN_RULES[caveman_intensity]
        return f"{base}\n\n[Output Style] {rules}"
    return base


def localized_roles_with_caveman(
    lang: Lang = "en",
    caveman_mode: bool = True,
    caveman_intensity: str = "full",
) -> dict[str, str]:
    """Get all agent role prompts with optional caveman compression.

    Args:
        lang: "en" or "ko".
        caveman_mode: Whether to append caveman rules.
        caveman_intensity: "lite", "full", or "ultra".

    Returns:
        Dict of agent_name → role prompt (with caveman if enabled).
    """
    return {
        name: get_agent_prompt(name, lang, caveman_mode, caveman_intensity)
        for name in ROLE_PROMPTS[lang]
    }
