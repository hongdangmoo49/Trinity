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


def compact_status_label(status: str) -> str:
    """Return the Nexus-style compact label for a raw status string."""
    return COMPACT_STATUS_LABELS[compact_status_group(status)]


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
