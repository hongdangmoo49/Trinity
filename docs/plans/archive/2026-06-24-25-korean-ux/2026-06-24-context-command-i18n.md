# Context 로컬 명령 한국어 라벨 개선

## 배경

`/context` 명령은 현재 Textual 세션의 워크플로우 컨텍스트를 보여준다. 본문 렌더링은 일부 한국어 라벨을 지원하지만, 로컬 명령 결과 제목과 현재 세션 컨텍스트가 없을 때의 빈 상태 안내는 영어로 고정되어 있다.

## 목표

- 한국어 설정에서 `/context` 결과 제목을 한국어로 표시한다.
- 현재 세션 컨텍스트가 없을 때의 빈 상태 메시지를 한국어로 표시한다.
- 기존 snapshot context markdown의 한국어 라벨 경로를 유지한다.
- stale shared.md를 읽지 않고 현재 snapshot만 사용하는 기존 동작은 유지한다.

## 설계

1. `presenters.py`에 context title/no-context helper를 추가한다.
2. `snapshot_context_markdown()`의 빈 상태 문구가 `lang`에 맞게 나오도록 변경한다.
3. `TrinityTextualApp._handle_textual_context_command()`에서 title 생성에 `config.lang`을 전달한다.
4. presenter 단위 테스트와 한국어 `/context` 빈 상태/정상 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "context"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
