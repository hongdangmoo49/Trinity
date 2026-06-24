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
        "repair_blocked": "복구 차단",
        "reviewing": "리뷰중",
        "running": "실행중",
        "skipped": "생략",
        "succeeded": "성공",
        "waiting": "대기",
    },
    "en": {},
}


def compact_status_label(status: str) -> str:
    """Return the Nexus-style compact label for a raw status string."""
    return COMPACT_STATUS_LABELS[compact_status_group(status)]


def display_status_value(status: str, *, lang: str = "en", empty: str = "-") -> str:
    """Return a localized display value for a raw status string."""
    raw = str(status or "").strip()
    if not raw:
        return empty
    labels = STATUS_VALUE_LABELS.get(lang, STATUS_VALUE_LABELS["en"])
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
