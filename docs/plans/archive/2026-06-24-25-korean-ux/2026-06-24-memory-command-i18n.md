# Memory 로컬 명령 한국어 라벨 개선

## 배경

`/memory` 명령은 Nexus 로컬 명령으로 처리되지만 결과 제목, 표 컬럼, cleanup 옵션 오류가 영어로 고정되어 있다. 메모리 본문 렌더링은 `context.commands`에서 CLI/TUI와 공유하므로, 이번 작업에서는 Textual 표시 계층의 라벨부터 분리한다.

## 목표

- 한국어 설정에서 `/memory` 기본 통계 결과 제목을 한국어로 표시한다.
- `/memory compact`, `/memory cleanup` 결과 제목을 한국어로 표시한다.
- `/memory cleanup` 옵션 오류를 한국어 설정에서 한국어로 표시한다.
- 표 컬럼은 기존 `status_table_columns()` 라벨을 재사용해 언어 설정을 따른다.

## 설계

1. `presenters.py`에 memory title/helper와 cleanup 오류 변환 helper를 추가한다.
2. `TrinityTextualApp._handle_textual_memory_command()`에서 언어 설정에 맞는 title, table columns, error body를 사용한다.
3. 공유 메모리 본문 생성기는 CLI/TUI와의 영향 범위를 피하기 위해 그대로 둔다.
4. presenter 단위 테스트와 한국어 `/memory` 실행/오류 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "memory"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
