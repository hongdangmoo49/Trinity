# Artifact 로컬 명령 한국어 라벨 개선

## 배경

`/artifact` 명령은 Nexus에서 메모리 레코드의 artifact 요약을 확인하는 로컬 명령이다. 현재 Textual 결과 제목과 usage가 영어로 고정되어 있고, 공유 artifact 본문도 영어만 반환한다.

## 목표

- 한국어 설정에서 `/artifact` 결과 제목과 usage 안내를 한국어로 표시한다.
- `artifact_markdown()`에 선택적 `lang` 인자를 추가해 한국어 본문을 지원한다.
- 기존 CLI/TUI 호출은 기본 영어 출력이 유지되도록 한다.
- memory index disabled, record not found, record found 경로를 모두 안전하게 처리한다.

## 설계

1. `presenters.py`에 artifact title/usage helper를 추가한다.
2. `context.commands.artifact_markdown()`의 기본값은 영어로 유지하고 `lang="ko"`일 때 한국어 라벨을 사용한다.
3. `TrinityTextualApp._handle_textual_artifact_command()`에서 `config.lang`을 전달한다.
4. context command helper 테스트와 Textual `/artifact` 한국어 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_context_commands.py tests/test_textual_app.py -k "artifact"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
