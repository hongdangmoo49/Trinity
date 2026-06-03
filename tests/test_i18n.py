"""Tests for trinity.i18n — localized strings and role prompts."""

import pytest

from trinity.i18n import (
    EN_STRINGS,
    KO_STRINGS,
    get_strings,
    localized_roles,
    role_prompt,
    Lang,
    ROLE_PROMPTS,
    Strings,
)


class TestGetStrings:
    def test_english(self):
        S = get_strings("en")
        assert S is EN_STRINGS
        assert "Detecting" in S.step1_title

    def test_korean(self):
        S = get_strings("ko")
        assert S is KO_STRINGS
        assert "탐지" in S.step1_title

    def test_invalid_lang_falls_back_to_english(self):
        """Invalid lang no longer raises — it falls back to English."""
        S = get_strings("fr")
        assert S is EN_STRINGS


class TestRolePrompt:
    @pytest.mark.parametrize("agent", ["claude", "codex", "gemini"])
    def test_english_role_prompts(self, agent):
        prompt = role_prompt(agent, "en")
        assert isinstance(prompt, str)
        assert len(prompt) > 20

    @pytest.mark.parametrize("agent", ["claude", "codex", "gemini"])
    def test_korean_role_prompts(self, agent):
        prompt = role_prompt(agent, "ko")
        assert isinstance(prompt, str)
        assert len(prompt) > 10
        # Korean role prompts should contain Korean characters
        assert any("사" <= c <= "힣" for c in prompt)

    def test_claude_english_is_architect(self):
        assert "Architect" in role_prompt("claude", "en")

    def test_codex_english_is_implementer(self):
        assert "Implementer" in role_prompt("codex", "en")

    def test_gemini_english_is_reviewer(self):
        assert "Reviewer" in role_prompt("gemini", "en")

    def test_claude_korean_is_architect(self):
        assert "아키텍트" in role_prompt("claude", "ko")

    def test_codex_korean_is_implementer(self):
        assert "구현자" in role_prompt("codex", "ko")

    def test_gemini_korean_is_reviewer(self):
        assert "리뷰어" in role_prompt("gemini", "ko")

    def test_invalid_agent_raises(self):
        with pytest.raises(KeyError):
            role_prompt("nonexistent", "en")


class TestLocalizedRoles:
    def test_english_returns_three(self):
        roles = localized_roles("en")
        assert set(roles.keys()) == {"claude", "codex", "gemini"}

    def test_korean_returns_three(self):
        roles = localized_roles("ko")
        assert set(roles.keys()) == {"claude", "codex", "gemini"}

    def test_returns_copy(self):
        """localized_roles should return a copy, not the original dict."""
        roles = localized_roles("en")
        roles["extra"] = "test"
        assert "extra" not in ROLE_PROMPTS["en"]


class TestValidateLang:
    def test_validate_lang_accepts_en(self):
        from trinity.i18n import validate_lang
        assert validate_lang("en") == "en"

    def test_validate_lang_accepts_ko(self):
        from trinity.i18n import validate_lang
        assert validate_lang("ko") == "ko"

    def test_validate_lang_rejects_unknown(self):
        from trinity.i18n import validate_lang
        with pytest.raises(ValueError, match="Unsupported language"):
            validate_lang("fr")

    def test_validate_lang_falls_back_to_en(self):
        from trinity.i18n import validate_lang
        result = validate_lang("fr", fallback="en")
        assert result == "en"

    def test_get_strings_invalid_lang_returns_english(self):
        from trinity.i18n import get_strings
        S = get_strings("fr")
        # Should return English strings with a warning
        assert S.wizard_title is not None


class TestStringsCompleteness:
    """Ensure EN and KO have the same fields (no missing translations)."""

    def test_both_have_all_fields(self):
        en_fields = {f.name for f in EN_STRINGS.__dataclass_fields__.values()}
        ko_fields = {f.name for f in KO_STRINGS.__dataclass_fields__.values()}
        assert en_fields == ko_fields

    def test_no_empty_strings_en(self):
        for name in EN_STRINGS.__dataclass_fields__:
            value = getattr(EN_STRINGS, name)
            assert value.strip(), f"EN_STRINGS.{name} is empty"

    def test_no_empty_strings_ko(self):
        for name in KO_STRINGS.__dataclass_fields__:
            value = getattr(KO_STRINGS, name)
            assert value.strip(), f"KO_STRINGS.{name} is empty"
