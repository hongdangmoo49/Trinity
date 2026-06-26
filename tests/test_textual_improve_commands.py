from trinity.textual_app.improve_commands import improve_result_presentation


def test_improve_result_presentation_skips_empty_message() -> None:
    assert improve_result_presentation(None) is None
    assert improve_result_presentation("") is None


def test_improve_result_presentation_warns_without_matching_item() -> None:
    presentation = improve_result_presentation("No matching post-review item.")

    assert presentation is not None
    assert presentation.message == "No matching post-review item."
    assert presentation.severity == "warning"


def test_improve_result_presentation_warns_when_required() -> None:
    presentation = improve_result_presentation("Target workspace is required.")

    assert presentation is not None
    assert presentation.severity == "warning"


def test_improve_result_presentation_keeps_info_message() -> None:
    presentation = improve_result_presentation("Queued supplemental work.")

    assert presentation is not None
    assert presentation.severity == "info"
