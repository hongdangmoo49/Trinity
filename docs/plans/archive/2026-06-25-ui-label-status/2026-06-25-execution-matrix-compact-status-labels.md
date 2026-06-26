# Execution Matrix Compact Status Labels

## 배경

실행 매트릭스의 패키지 상태 칩은 한국어 UI에서도 `RUN`, `WAIT`, `DONE`, `ISSUE` 같은 영어 축약값을 표시한다. 최근 작업에서 summary, 위험도, 작업 종류, recovery 상태를 한국어 표시값으로 정리했으므로, 매트릭스 본문 상태 칩도 같은 방향으로 맞출 필요가 있다.

## 목표

- `compact_status_label`이 언어별 표시 라벨을 선택할 수 있게 한다.
- 실행 매트릭스 패키지 행에서는 현재 UI 언어에 맞는 상태 칩을 표시한다.
- 영어 UI의 기존 `RUN/WAIT/DONE/ISSUE/IDLE/?` 표시는 유지한다.

## 비목표

- 상태 그룹 분류 규칙은 변경하지 않는다.
- summary 집계 로직과 workflow snapshot 원본값은 변경하지 않는다.

## 검증

- `uv run pytest tests/test_textual_app.py::test_execution_matrix_renders_compact_status_labels -q`
- `uv run pytest tests/test_textual_app.py::test_execution_matrix_renders_korean_compact_status_labels -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
