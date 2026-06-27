"""Pure helpers for Textual model settings notifications."""

from __future__ import annotations

from dataclasses import dataclass

from trinity.textual_app import presenters as textual_presenters


@dataclass(frozen=True)
class ModelSettingsNotification:
    """Prepared Textual notification for model settings actions."""

    title: str
    message: str
    severity: str = ""


def model_settings_unavailable_notification(
    *,
    lang: str = "en",
) -> ModelSettingsNotification:
    """Return the warning notification shown when model settings cannot open."""
    return ModelSettingsNotification(
        title=textual_presenters.model_settings_title(lang=lang),
        message=textual_presenters.model_settings_unavailable_markdown(lang=lang),
        severity="warning",
    )


def model_settings_updated_notification(
    *,
    lang: str = "en",
) -> ModelSettingsNotification:
    """Return the notification shown after model settings are applied."""
    return ModelSettingsNotification(
        title=textual_presenters.model_settings_title(lang=lang),
        message=textual_presenters.model_settings_updated_markdown(lang=lang),
    )
