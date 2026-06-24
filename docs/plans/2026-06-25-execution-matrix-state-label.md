# Execution Matrix Workflow State Label

## 배경

실행 매트릭스의 한국어 요약 줄은 대부분 한국어 라벨을 사용하지만 workflow state는 `워크플로우 running`처럼 원본 상태값을 그대로 표시한다. 다른 Nexus/Report/status 표면은 이미 공용 상태 라벨을 쓰고 있으므로 실행 매트릭스 요약도 같은 규칙을 따라야 한다.

## 목표

- 실행 매트릭스 요약의 workflow/recovery state를 표시용 상태 라벨로 렌더링한다.
- 한국어 UI에서는 `running`을 `실행중`처럼 표시한다.
- 영어 UI와 snapshot 원본값은 유지한다.

## 비목표

- execution matrix 상태 집계 로직은 변경하지 않는다.
- workflow snapshot state 저장 형식은 변경하지 않는다.

## 검증

- `uv run pytest tests/test_textual_app.py -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
