# Provider Metadata Label Localization

## 배경

앞선 상태값 한국어화 작업 이후에도 Nexus와 리포트의 provider 메타데이터에는 `Ready`, `Queued`, `ready`, `runtime`, `local_cli_cache` 같은 내부 값이 그대로 노출된다. 한국어 UI에서는 주요 상태와 출처를 같은 언어로 읽을 수 있어야 하지만, snapshot 원본값과 실행 로그는 진단 가치가 있으므로 그대로 유지해야 한다.

## 목표

- `/status` provider 표와 행에서 provider 상태를 표시용 라벨로 렌더링한다.
- Provider Inspector의 상태와 준비 상태를 한국어 표시 라벨로 렌더링한다.
- 리포트와 inspector의 context budget source를 한국어 표시 라벨로 렌더링한다.
- Provider panel의 compact source 라벨도 언어별로 일관되게 유지한다.

## 비목표

- snapshot 저장 형식, workflow persistence, provider invoker metadata는 변경하지 않는다.
- 원본 provider 출력과 실행 로그의 내부 토큰은 번역하지 않는다.
- 모델 선택기 전체의 source reason 라벨링은 별도 작업으로 남긴다.

## 설계

1. `widgets/status_label.py`에 source/readiness 표시 헬퍼를 추가한다.
   - `display_source_value()`: 리포트/inspector처럼 설명형 화면에서 사용한다.
   - `compact_source_value()`: provider panel처럼 공간이 좁은 화면에서 사용한다.
   - `display_readiness_value()`: readiness 전용 라벨을 제공한다.
2. 기존 `display_status_value()`의 한국어 상태 맵에 provider 상태에서 쓰는 `ready`를 추가한다.
3. presenter, report, inspector, provider panel은 snapshot 원본값 대신 표시 헬퍼를 호출한다.
4. 테스트는 한국어 UI의 기대값만 갱신하고, 영어 UI의 raw/source 표현은 유지한다.

## 검증

- `uv run pytest tests/test_textual_app.py tests/test_provider_panel.py tests/test_report.py -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
