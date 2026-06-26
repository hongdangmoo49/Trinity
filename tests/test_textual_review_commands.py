from trinity.textual_app.review_commands import review_result_presentation


def test_review_result_presentation_skips_empty_message() -> None:
    assert review_result_presentation(None) is None
    assert review_result_presentation("") is None


def test_review_result_presentation_warns_without_review_package() -> None:
    presentation = review_result_presentation("No review packages are ready.")

    assert presentation is not None
    assert presentation.message == "No review packages are ready."
    assert presentation.severity == "warning"


def test_review_result_presentation_warns_when_not_connected() -> None:
    presentation = review_result_presentation("Review provider is not connected.")

    assert presentation is not None
    assert presentation.severity == "warning"


def test_review_result_presentation_keeps_info_message() -> None:
    presentation = review_result_presentation("Review requested for WP-001.")

    assert presentation is not None
    assert presentation.severity == "info"
