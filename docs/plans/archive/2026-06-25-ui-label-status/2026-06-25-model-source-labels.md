# Model Source Label Localization

## 배경

Provider 메타데이터 라벨을 정리한 뒤에도 `/model` 모달의 모델 선택지에는 `static-fallback`, `cli-live` 같은 source 값이 그대로 표시된다. 모델 선택은 사용자가 직접 조작하는 설정 화면이므로 한국어 UI에서는 source 값도 읽기 쉬운 표시 라벨로 맞출 필요가 있다.

## 목표

- `/model` 모달의 모델 선택지 source 값을 한국어 표시 라벨로 렌더링한다.
- 기존 공용 `display_source_value()` 헬퍼를 재사용해 report/inspector와 source 표기법을 공유한다.
- 영어 UI에서는 기존 raw source 표기를 유지한다.
- 모델 선택 결과와 저장되는 `ProviderModelChoice.source` 원본값은 변경하지 않는다.

## 비목표

- provider model discovery 로직과 cache 저장 형식은 변경하지 않는다.
- setup wizard의 Rich 테이블 source 표기는 이번 작업에 포함하지 않는다.
- `source_reason` 설명 문구의 번역은 별도 작업으로 남긴다.

## 설계

1. `ModelSettingsModal._choice_label()`에서 `choice.source`를 직접 append하지 않고 `display_source_value()`를 호출한다.
2. `lang="ko"`일 때 `cli-live`, `static-fallback` 등은 한국어 라벨로 표시한다.
3. 테스트는 한국어 `/model` 모달 선택지에서 `CLI 실시간`이 보이는지 확인하고, 영어 모드는 기존 `cli-live` 표기를 유지하는 회귀 테스트로 둔다.

## 검증

- `uv run pytest tests/test_textual_app.py -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
