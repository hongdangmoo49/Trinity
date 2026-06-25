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

RISK_VALUE_LABELS = {
    "ko": {
        "critical": "치명적",
        "high": "높음",
        "medium": "보통",
        "low": "낮음",
        "unknown": "알 수 없음",
    },
    "en": {},
}

SEVERITY_VALUE_LABELS = {
    "ko": {
        "critical": "치명적",
        "error": "오류",
        "high": "높음",
        "info": "정보",
        "low": "낮음",
        "medium": "보통",
        "warning": "경고",
        "unknown": "알 수 없음",
    },
    "en": {},
}

KIND_VALUE_LABELS = {
    "ko": {
        "architecture": "아키텍처",
        "bugfix": "버그 수정",
        "component": "컴포넌트",
        "dependency": "의존성",
        "documentation": "문서화",
        "enhancement": "개선",
        "implementation": "구현",
        "integration": "통합",
        "large_implementation": "대규모 구현",
        "planning": "계획",
        "repair": "복구",
        "research": "조사",
        "review": "리뷰",
        "test": "테스트",
        "testing": "테스트",
        "validation": "검증",
    },
    "en": {},
}

PROFILE_VALUE_LABELS = {
    "ko": {
        "architect": "설계자",
        "balanced": "균형",
        "execute": "실행",
        "execution_v1": "실행 v1",
        "final_review_v1": "최종 리뷰 v1",
        "implementer": "구현자",
        "implementation": "구현",
        "integration": "통합",
        "planning": "계획",
        "repair": "복구",
        "review": "리뷰",
        "review_v1": "리뷰 v1",
        "reviewer": "리뷰어",
        "strength": "강점",
        "strengths": "강점",
        "test": "테스트",
        "testing": "테스트",
        "validation": "검증",
    },
    "en": {},
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


def display_risk_value(
    risk: str,
    *,
    lang: str = "en",
    empty: str = "-",
) -> str:
    """Return a localized display value for a risk level string."""
    return _display_labeled_value(
        risk,
        labels_by_lang=RISK_VALUE_LABELS,
        lang=lang,
        empty=empty,
    )


def display_severity_value(
    severity: str,
    *,
    lang: str = "en",
    empty: str = "-",
) -> str:
    """Return a localized display value for a severity level string."""
    return _display_labeled_value(
        severity,
        labels_by_lang=SEVERITY_VALUE_LABELS,
        lang=lang,
        empty=empty,
    )


def display_kind_value(
    kind: str,
    *,
    lang: str = "en",
    empty: str = "-",
) -> str:
    """Return a localized display value for a task/action kind string."""
    return _display_labeled_value(
        kind,
        labels_by_lang=KIND_VALUE_LABELS,
        lang=lang,
        empty=empty,
    )


def display_profile_value(
    value: str,
    *,
    lang: str = "en",
    empty: str = "-",
) -> str:
    """Return a localized display value for profile metadata tokens."""
    raw = str(value or "").strip()
    if not raw:
        return empty
    labels = PROFILE_VALUE_LABELS.get(lang, PROFILE_VALUE_LABELS["en"])
    direct = labels.get(raw.lower())
    if direct:
        return direct
    if " " not in raw:
        return raw
    return " ".join(labels.get(part.lower(), part) for part in raw.split(" "))


def _display_labeled_value(
    value: str,
    *,
    labels_by_lang: dict[str, dict[str, str]],
    lang: str,
    empty: str,
) -> str:
    raw = str(value or "").strip()
    if not raw:
        return empty
    labels = labels_by_lang.get(lang, labels_by_lang["en"])
    return labels.get(raw.lower(), raw)
