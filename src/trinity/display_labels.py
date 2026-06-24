"""Shared user-facing display labels."""

from __future__ import annotations

SOURCE_VALUE_LABELS = {
    "ko": {
        "cli-bundled": "CLI 내장",
        "cli-live": "CLI 실시간",
        "local_cli_cache": "로컬 CLI 캐시",
        "provider_log": "프로바이더 로그",
        "runtime": "런타임",
        "runtime_metadata": "런타임 메타데이터",
        "static-fallback": "정적 기본값",
        "trinity_config": "Trinity 설정",
        "unsupported": "지원 안 함",
    },
    "en": {},
}

COMPACT_SOURCE_LABELS = {
    "ko": {
        "local_cli_cache": "로컬",
        "provider_log": "로그",
        "runtime": "런타임",
        "runtime_metadata": "런타임",
        "trinity_config": "설정",
    },
    "en": {
        "local_cli_cache": "local",
        "provider_log": "log",
        "runtime": "runtime",
        "runtime_metadata": "runtime",
        "trinity_config": "config",
    },
}


def display_source_value(
    source: str,
    *,
    lang: str = "en",
    empty: str = "-",
) -> str:
    """Return a localized display value for a metadata source string."""
    raw = str(source or "").strip()
    if not raw:
        return empty
    labels = SOURCE_VALUE_LABELS.get(lang, SOURCE_VALUE_LABELS["en"])
    return labels.get(raw, raw)


def compact_source_value(source: str, *, lang: str = "en") -> str:
    """Return a compact display value for a metadata source string."""
    raw = str(source or "").strip()
    if not raw or raw == "unsupported":
        return ""
    labels = COMPACT_SOURCE_LABELS.get(lang, COMPACT_SOURCE_LABELS["en"])
    return labels.get(raw, display_source_value(raw, lang=lang, empty=""))
