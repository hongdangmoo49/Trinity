from trinity.textual_app.execute_commands import (
    execute_result_presentation,
    execute_retry_no_packages_presentation,
)


def test_execute_result_presentation_skips_empty_message() -> None:
    assert execute_result_presentation(None) is None
    assert execute_result_presentation("") is None


def test_execute_result_presentation_wraps_message() -> None:
    presentation = execute_result_presentation("Finish planning before execution.")

    assert presentation is not None
    assert presentation.title == "Execute"
    assert presentation.body == "Finish planning before execution."
    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.action_hint == (
        "Finish planning first, then run `/execute` from Nexus."
    )


def test_execute_retry_no_packages_presentation_uses_retry_copy() -> None:
    presentation = execute_retry_no_packages_presentation()

    assert presentation.title == "Execute Retry"
    assert presentation.body == (
        "No work packages are available in the current workflow."
    )
    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.action_hint == (
        "Finish planning and execute at least one package first."
    )


def test_execute_retry_no_packages_presentation_supports_korean() -> None:
    presentation = execute_retry_no_packages_presentation(lang="ko")

    assert presentation.title == "실행 재시도"
    assert presentation.body == (
        "현재 워크플로우에 사용할 수 있는 작업 패키지가 없습니다."
    )
    assert presentation.action_hint == (
        "먼저 계획을 완료하고 하나 이상의 작업 패키지를 실행하세요."
    )
