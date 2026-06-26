# Setup Wizard Model Source Labels

## 배경

`trinity init`의 모델 선택 테이블은 `Version / Info` 칸에 `static-fallback`, `cli-live` 같은 source 원본값을 그대로 보여준다. 이는 사용자가 초기 설정 중 직접 보는 정보이며, 한국어 init 흐름에서는 `정적 기본값`, `CLI 실시간`처럼 읽히는 표시 라벨이 더 자연스럽다.

## 목표

- setup wizard 모델 선택 테이블의 source 값을 언어별 표시 라벨로 렌더링한다.
- Textual에 있던 source 라벨 헬퍼를 `trinity.display_labels` 공용 모듈로 분리한다.
- Textual report/inspector/model modal/provider panel은 새 공용 모듈을 사용하도록 유지한다.
- `ProviderModelChoice.source` 원본값과 provider discovery/cache 동작은 변경하지 않는다.

## 비목표

- `source_reason` 문구 번역은 이번 작업에 포함하지 않는다.
- setup wizard 테이블 컬럼명 변경은 하지 않는다.
- provider model discovery 결과 자체는 변경하지 않는다.

## 설계

1. `trinity.display_labels`에 `display_source_value()`와 `compact_source_value()`를 둔다.
2. 기존 Textual source 표시 지점은 새 모듈에서 import하도록 변경한다.
3. `SetupWizard._ask_model_choice()`는 `choice.source` 대신 `display_source_value(choice.source, lang=self.lang)`를 테이블에 표시한다.
4. 테스트는 한국어 setup wizard 출력에 `CLI 실시간`이 포함되는지 확인한다.

## 검증

- `uv run pytest tests/test_setup_wizard.py tests/test_textual_app.py tests/test_provider_panel.py tests/test_report.py -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
