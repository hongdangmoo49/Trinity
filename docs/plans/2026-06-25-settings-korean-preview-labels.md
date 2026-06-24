# Settings Korean Preview Labels

## 배경

설정 화면의 한국어 UI에서 `중앙 Provider`처럼 용어가 섞이고, 미리보기 영역도 `Mode`, `Density`, `Central` 같은 영어 라벨을 그대로 표시한다. 다른 Textual 화면의 한국어 라벨을 정리한 흐름에 맞춰 설정 화면도 같은 용어와 라벨을 사용해야 한다.

## 목표

- 한국어 설정 화면의 `중앙 Provider`를 `중앙 프로바이더`로 표시한다.
- 한국어 미리보기 영역의 `Mode`, `Density`, `Central` 라벨을 한국어로 표시한다.
- 영어 UI와 설정 저장 동작은 유지한다.

## 비목표

- 설정 저장 형식이나 모델/provider 선택 값은 변경하지 않는다.
- 실제 모델 id, profile id, output contract 값은 번역하지 않는다.

## 검증

- `uv run pytest tests/test_textual_app.py::test_settings_screen_uses_korean_preview_labels tests/test_textual_app.py::test_settings_preview_shows_profile_output_contracts -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
