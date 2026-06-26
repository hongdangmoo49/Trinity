# Provider Inspector 한국어 라벨 개선

## 배경

Nexus에서 Provider Inspector를 열면 모달은 `lang` 값을 받지만 제목, 전체 탭, 닫기 버튼, 메타 정보 라벨은 영어로 고정되어 있다. 한국어 UI에서 프로바이더 상태를 확인할 때 핵심 진단 표면이 영어로 섞여 보이는 문제가 있다.

## 목표

- 한국어 설정에서 Provider Inspector 제목과 닫기 버튼을 한국어로 표시한다.
- `All` 탭과 provider 메타 라벨을 언어 설정에 맞춰 표시한다.
- raw output 자체와 provider가 생성한 원문은 번역하지 않는다.
- 영어 기본값과 기존 pretty-print/truncation 동작은 유지한다.

## 설계

1. `ProviderInspector` 내부에 언어별 라벨 맵과 `_label()` helper를 추가한다.
2. `compose()`, `_provider_meta()`, `_all_output()`에서 라벨 helper를 사용한다.
3. raw output이 없을 때의 fallback 문구만 언어별로 분기한다.
4. 기존 영어 메타 테스트는 유지하고, 한국어 메타/모달 chrome 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "provider_inspector"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `uv run trinity --version`
