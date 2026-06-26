# Textual Workflow Outcome Presenter Refactor

## 배경

`TrinityTextualApp._workflow_outcome_message`는 앱 상태를 변경하지 않고 `textual_presenters.workflow_outcome_message_markdown`에 `lang=self.config.lang`만 전달하는 얇은 wrapper였다. 최근 presenter wrapper 제거 작업의 흐름에 맞춰 이 delegate를 제거하면 TextualApp은 orchestration/control 흐름에 더 집중할 수 있다.

## 목표

- `TrinityTextualApp._workflow_outcome_message`를 제거한다.
- 기존 메시지 현지화 동작은 `textual_presenters.workflow_outcome_message_markdown` 직접 호출로 유지한다.
- review/improve/execute/resume/answer/recovery 알림의 severity, empty, action hint 동작은 변경하지 않는다.
- 패치 버전을 `1.0.325`로 올린다.

## 변경 계획

1. `_workflow_outcome_message` 호출부를 presenter 직접 호출로 교체한다.
2. wrapper method를 삭제한다.
3. 기존 presenter 단위 테스트와 TextualApp focused 테스트로 회귀를 확인한다.

## 검증

- `git diff --check`
- `uv run trinity --version`
- `uv run pytest -q tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_textual_command_parsers.py tests/test_slash_commands.py`
- `uv run pytest -q`
