"""Pure helpers for Textual model settings notifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trinity.textual_app import presenters as textual_presenters


@dataclass(frozen=True)
class ModelSettingsNotification:
    """Prepared Textual notification for model settings actions."""

    title: str
    message: str
    severity: str = ""


@dataclass(frozen=True)
class ModelSettingsModalRequest:
    """Prepared state for opening the model settings modal."""

    notification: ModelSettingsNotification | None = None
    choices_by_agent: dict[str, Any] | None = None
    selected_models: dict[str, str] | None = None

    @property
    def show_modal(self) -> bool:
        """Return whether a model settings modal should be opened."""
        return self.notification is None


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


def model_settings_modal_request(
    selector: Any | None,
    discovered_model_choices: dict[str, Any],
    *,
    lang: str = "en",
) -> ModelSettingsModalRequest:
    """Return the notification or modal data for model settings."""
    if selector is None:
        return ModelSettingsModalRequest(
            notification=model_settings_unavailable_notification(lang=lang)
        )
    choices_by_agent = dict(selector.model_choices_by_agent())
    choices_by_agent.update(discovered_model_choices)
    return ModelSettingsModalRequest(
        choices_by_agent=choices_by_agent,
        selected_models=dict(selector.selected_models()),
    )
