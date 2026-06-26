# Status/Context 로컬 명령 한국어 라벨 개선

## 배경

`/status`와 `/context`는 에이전트를 호출하지 않는 로컬 명령이지만, 한국어 설정에서도 본문 presenter가 `Workflow`, `State`, `Execution Recovery`, `Current Session Context` 같은 영어 라벨을 직접 출력한다. 모달 chrome 일부는 한국어화되어 있어 화면 안에서 언어가 섞여 보인다.

## 목표

- `snapshot_status_markdown()`과 `snapshot_status_rows()`에 `lang` 인자를 추가하고 기본 영어 동작은 유지한다.
- 한국어 설정에서 `/status`의 Markdown, 표 컬럼, 행 라벨, 실행 복구 라벨을 한국어로 보여준다.
- `snapshot_context_markdown()`에 `lang` 인자를 추가하고 주요 섹션 제목과 필드 라벨을 한국어로 보여준다.
- `ContextCommandModal` 제목/닫기 버튼/binding을 한국어 설정에 맞춘다.
- 사용자 입력, workflow id, provider 이름, raw 상태 값은 임의 번역하지 않는다.

## 설계

1. `presenters.py`에 status/context용 라벨 helper를 추가한다.
2. 기존 presenter 함수들은 `lang="en"` 기본값을 유지해 기존 테스트와 호출을 깨지 않게 한다.
3. `TrinityTextualApp`의 `/status`, `/context` 처리 경로에서 `self.config.lang`을 전달한다.
4. `ContextCommandModal`에 `lang` 인자를 추가하고 기존 `StatusCommandModal`과 같은 방식으로 binding을 현지화한다.
5. 영어 회귀 테스트는 유지하고, 한국어 presenter 및 모달 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "status or context"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
