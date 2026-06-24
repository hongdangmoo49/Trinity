# Korean Provider Term Labels

## 배경

한국어 Textual presenter 문구 중 일부가 `provider 프롬프트`, `실패한 provider`처럼 영어 `provider`를 그대로 사용한다. 다른 화면에서는 이미 `프로바이더` 용어를 쓰고 있으므로, 사용자가 보는 help/outcome 문구도 같은 용어로 맞춘다.

## 목표

- 한국어 help intro의 `provider 프롬프트`를 `프로바이더 프롬프트`로 표시한다.
- provider error outcome 문구의 `provider`를 `프로바이더`로 표시한다.
- 영어 UI 문구는 유지한다.

## 비목표

- 내부 변수명, provider 식별자, config key는 변경하지 않는다.
- 사용자/에이전트가 작성한 텍스트는 변경하지 않는다.

## 검증

- `uv run pytest tests/test_textual_app.py::test_help_unknown_presenter_uses_korean_labels tests/test_textual_app.py::test_workflow_outcome_message_uses_korean_labels -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
