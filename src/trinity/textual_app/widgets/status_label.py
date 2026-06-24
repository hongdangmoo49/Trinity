"""Shared compact status labels for Textual status surfaces."""

from __future__ import annotations


RUNNING_STATUSES = {"deliberating", "executing", "reviewing", "running"}
WAITING_STATUSES = {
    "needs_review",
    "pending",
    "queued",
    "waiting",
    "waiting_on_decision",
}
IDLE_STATUSES = {"idle"}
DONE_STATUSES = {"completed", "done", "ready", "success"}
ISSUE_STATUSES = {"blocked", "error", "failed", "timeout"}

COMPACT_STATUS_LABELS = {
    "done": "DONE",
    "idle": "IDLE",
    "issue": "ISSUE",
    "running": "RUN",
    "unknown": "?",
    "waiting": "WAIT",
}

COMPACT_STATUS_LABELS_BY_LANG = {
    "en": COMPACT_STATUS_LABELS,
    "ko": {
        "done": "완료",
        "idle": "대기",
        "issue": "문제",
        "running": "실행",
        "unknown": "?",
        "waiting": "대기",
    },
}

STATUS_VALUE_LABELS = {
    "ko": {
        "approved": "승인",
        "accepted": "수락",
        "blocked": "차단",
        "blueprint_ready": "설계 준비",
        "changes_requested": "변경 요청",
        "completed": "완료",
        "deliberating": "숙의 중",
        "done": "완료",
        "executing": "실행 중",
        "failed": "실패",
        "ignored": "무시",
        "idle": "대기",
        "improving": "개선 중",
        "interrupted": "중단",
        "needs_review": "리뷰 필요",
        "needs_second_review": "2차 리뷰 필요",
        "needs_user_decision": "사용자 결정 대기",
        "pending": "대기",
        "post_review_ready": "후속 조치 대기",
        "preflight": "사전 점검",
        "proposed": "제안",
        "queued": "대기",
        "ready": "준비됨",
        "repair_blocked": "복구 차단",
        "reviewing": "리뷰중",
        "running": "실행중",
        "skipped": "생략",
        "succeeded": "성공",
        "waiting": "대기",
    },
    "en": {},
}

READINESS_VALUE_LABELS = {
    "ko": {
        "ready": "준비됨",
        "unknown": "미확인",
        "unavailable": "사용 불가",
        "unsupported": "지원 안 함",
    },
    "en": {},
}

def compact_status_label(status: str, *, lang: str = "en") -> str:
    """Return the Nexus-style compact label for a raw status string."""
    labels = COMPACT_STATUS_LABELS_BY_LANG.get(lang, COMPACT_STATUS_LABELS)
    return labels[compact_status_group(status)]


def display_status_value(status: str, *, lang: str = "en", empty: str = "-") -> str:
    """Return a localized display value for a raw status string."""
    raw = str(status or "").strip()
    if not raw:
        return empty
    labels = STATUS_VALUE_LABELS.get(lang, STATUS_VALUE_LABELS["en"])
    return labels.get(raw.lower(), raw)


def display_readiness_value(
    readiness: str,
    *,
    lang: str = "en",
    empty: str = "-",
) -> str:
    """Return a localized display value for a provider readiness string."""
    raw = str(readiness or "").strip()
    if not raw:
        return empty
    labels = READINESS_VALUE_LABELS.get(lang, READINESS_VALUE_LABELS["en"])
    return labels.get(raw.lower(), raw)


def display_review_status_value(
    status: str,
    *,
    reviewer_agent: str = "",
    summary: str = "",
    skipped_reason: str = "",
    lang: str = "en",
    empty: str = "(none)",
) -> str:
    """Return a display value for a review status string."""
    raw = str(status or "").strip()
    if not raw:
        return empty
    if raw.lower() == "skipped" and is_no_peer_review_skip(
        reviewer_agent=reviewer_agent,
        summary=summary,
        skipped_reason=skipped_reason,
    ):
        return "peer 없음" if lang == "ko" else "no peer"
    return display_status_value(raw, lang=lang, empty=empty)


def display_review_skip_reason(reason: str, *, lang: str = "en") -> str:
    """Return a localized display value for known review skip reasons."""
    raw = str(reason or "").strip()
    if not raw or lang != "ko":
        return raw
    text = raw.lower()
    if text.rstrip(".") in {"peer review skipped", "peer review was skipped"}:
        return "동료 리뷰가 생략되었습니다."
    if "no non-owner peer reviewer" not in text and "no peer reviewer" not in text:
        return raw
    agent = _only_active_agent(raw)
    if agent:
        return f"활성 에이전트가 {agent}뿐이라 peer 리뷰어가 없습니다."
    return "사용 가능한 peer 리뷰어가 없습니다."


def is_no_peer_review_skip(
    *,
    reviewer_agent: str = "",
    summary: str = "",
    skipped_reason: str = "",
) -> bool:
    """Return whether a skipped review means no peer reviewer was available."""
    if str(reviewer_agent or "").strip():
        return False
    text = f"{summary or ''} {skipped_reason or ''}".lower()
    if "no non-owner peer reviewer" in text or "no peer reviewer" in text:
        return True
    return "only " in text and " active" in text


def _only_active_agent(reason: str) -> str:
    lower = reason.lower()
    prefix = "only "
    suffix = " is active"
    start = lower.find(prefix)
    if start == -1:
        return ""
    end = lower.find(suffix, start + len(prefix))
    if end == -1:
        return ""
    return reason[start + len(prefix) : end].strip()


def compact_status_group(status: str) -> str:
    """Return the compact UI state bucket for a raw status string."""
    raw = str(status or "").strip().lower()
    if raw in RUNNING_STATUSES:
        return "running"
    if raw in WAITING_STATUSES:
        return "waiting"
    if raw in IDLE_STATUSES:
        return "idle"
    if raw in DONE_STATUSES:
        return "done"
    if raw in ISSUE_STATUSES:
        return "issue"
    return "unknown"
