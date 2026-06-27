from trinity.textual_app.model_settings_commands import (
    model_settings_unavailable_notification,
    model_settings_updated_notification,
)


def test_model_settings_unavailable_notification_marks_warning() -> None:
    notification = model_settings_unavailable_notification()

    assert notification.title == "Model Settings"
    assert notification.message == "Model settings are available on Start and Nexus."
    assert notification.severity == "warning"


def test_model_settings_updated_notification_marks_information() -> None:
    notification = model_settings_updated_notification()

    assert notification.title == "Model Settings"
    assert notification.message == "Model settings updated."
    assert notification.severity == ""


def test_model_settings_notifications_use_korean_labels() -> None:
    unavailable = model_settings_unavailable_notification(lang="ko")
    updated = model_settings_updated_notification(lang="ko")

    assert unavailable.title == "모델 설정"
    assert unavailable.message == "모델 설정은 시작 화면과 Nexus에서 사용할 수 있습니다."
    assert unavailable.severity == "warning"
    assert updated.title == "모델 설정"
    assert updated.message == "모델 설정을 업데이트했습니다."
    assert updated.severity == ""
