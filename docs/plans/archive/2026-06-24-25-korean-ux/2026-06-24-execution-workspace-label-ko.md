# Execution Matrix workspace 라벨 한국어화

## 배경

Execution Matrix는 한국어 UI 라벨을 대부분 지원하지만, 헤더의 작업 폴더 라벨만 `workspace`로 남아 있다. 실행 화면 상단에 항상 보이는 문구라 한국어 설정에서는 `작업 폴더`로 맞추는 것이 자연스럽다.

## 목표

- 한국어 설정에서 Execution Matrix 헤더의 `workspace` 라벨을 `작업 폴더`로 표시한다.
- 영어 기본값과 기존 레이아웃은 유지한다.
- 기존 한국어 chrome 테스트에 헤더 라벨 기대값을 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "execution_matrix_supports_korean_chrome_labels"`
- `uv run pytest`
- `uv run trinity --version`
