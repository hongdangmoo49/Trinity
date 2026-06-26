# Questions 로컬 명령 한국어 라벨 개선

## 배경

`/questions`는 현재 워크플로우 질문을 로컬로 보여주지만, 한국어 설정에서도 `Answer`, `Recommended`, `Selected question`, `Use question panel buttons` 같은 안내 문구와 표 컬럼이 영어로 표시된다. `/status`, `/context`, `/workflow` 개선 이후 남은 로컬 명령 화면의 언어 혼합을 줄일 필요가 있다.

## 목표

- `questions_markdown()`, `questions_select_markdown()`, `questions_rows()`에 `lang` 인자를 추가하고 기본 영어 동작은 유지한다.
- 한국어 설정에서 질문 목록, 선택 모드, 빈 상태, action hint, 표 컬럼을 한국어로 보여준다.
- 질문 ID, 질문 본문, 선택지, raw 상태 값은 임의 번역하지 않는다.
- 앱의 `/questions` 처리 경로가 `config.lang`을 presenter에 전달하도록 연결한다.

## 설계

1. 기존 status/context 라벨 맵에 questions 전용 라벨을 추가한다.
2. questions용 table column/action hint helper를 추가해 앱 호출부에서 중복 문자열을 줄인다.
3. 기존 영어 테스트가 유지되도록 모든 함수는 `lang="en"` 기본값을 유지한다.
4. presenter 단위 테스트와 `/questions`, `/questions --select` 실행 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "questions"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
