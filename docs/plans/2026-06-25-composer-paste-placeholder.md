# Composer 붙여넣기 placeholder 지역화

## 배경

Prompt composer는 긴 텍스트나 여러 줄 텍스트를 붙여넣으면 화면에는 짧은 placeholder를 보여주고, 제출 시에는 내부 매핑을 통해 원문으로 복원한다. 현재 placeholder가 `[Pasted Content 1200 chars]`로 고정되어 한국어 UI에서도 영어 문구가 노출된다.

## 목표

- 한국어 UI에서는 대용량 붙여넣기 placeholder를 한국어로 표시한다.
- 영어 UI의 기존 placeholder 형식은 유지한다.
- placeholder가 지역화되어도 `submission_text`가 원문 붙여넣기 내용으로 복원되는 동작을 보존한다.

## 작업 범위

1. `PromptComposer`에 붙여넣기 placeholder 생성 헬퍼를 추가한다.
2. `lang=ko`일 때 `[붙여넣은 콘텐츠 {count}자]`를 사용한다.
3. 영어/한국어 composer 붙여넣기 회귀 테스트를 추가한다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/widgets/composer.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "prompt_composer_summarizes_large_paste" -q`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest -q`
