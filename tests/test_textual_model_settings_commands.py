from trinity.textual_app.model_settings_commands import (
    model_settings_modal_request,
    model_settings_unavailable_notification,
    model_settings_updated_notification,
)


def test_model_settings_unavailable_notification_marks_warning() -> None:
    notification = model_settings_unavailable_notification()

    assert notification.title == "Next Request Models"
    assert notification.message == (
        "Next request models are available on Start and Nexus."
    )
    assert notification.severity == "warning"


def test_model_settings_updated_notification_marks_information() -> None:
    notification = model_settings_updated_notification()

    assert notification.title == "Next Request Models"
    assert notification.message == "Next request models updated."
    assert notification.severity == ""


def test_model_settings_notifications_use_korean_labels() -> None:
    unavailable = model_settings_unavailable_notification(lang="ko")
    updated = model_settings_updated_notification(lang="ko")

    assert unavailable.title == "다음 요청 모델"
    assert unavailable.message == (
        "다음 요청 모델은 시작 화면과 넥서스에서 사용할 수 있습니다."
    )
    assert unavailable.severity == "warning"
    assert updated.title == "다음 요청 모델"
    assert updated.message == "다음 요청 모델을 업데이트했습니다."
    assert updated.severity == ""


def test_model_settings_modal_request_returns_unavailable_notification() -> None:
    request = model_settings_modal_request(None, {}, lang="ko")

    assert request.show_modal is False
    assert request.notification is not None
    assert request.notification.title == "다음 요청 모델"
    assert request.choices_by_agent is None
    assert request.selected_models is None


def test_model_settings_modal_request_merges_discovered_choices() -> None:
    selector = _FakeModelSelector(
        choices={
            "codex": ("codex(default)",),
            "claude": ("sonnet",),
        },
        selected={"codex": "codex(default)"},
    )

    request = model_settings_modal_request(
        selector,
        {
            "codex": ("gpt-5.5",),
            "antigravity": ("agy(default)",),
        },
    )

    assert request.show_modal is True
    assert request.notification is None
    assert request.choices_by_agent == {
        "codex": ("gpt-5.5",),
        "claude": ("sonnet",),
        "antigravity": ("agy(default)",),
    }
    assert request.selected_models == {"codex": "codex(default)"}


class _FakeModelSelector:
    def __init__(self, *, choices, selected) -> None:
        self._choices = choices
        self._selected = selected

    def model_choices_by_agent(self):
        return dict(self._choices)

    def selected_models(self):
        return dict(self._selected)
