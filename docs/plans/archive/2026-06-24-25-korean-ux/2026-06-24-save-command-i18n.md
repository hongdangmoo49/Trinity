# Save 로컬 명령 한국어 라벨 개선

## 배경

Textual Nexus의 `/save` 명령은 워크플로우가 자동 저장된다는 사실과 Markdown 리포트 내보내기 경로를 안내한다. 한국어 설정에서도 제목과 본문이 영어로 고정되어 있어 다른 로컬 명령과 언어 일관성이 맞지 않는다.

## 목표

- 한국어 설정에서 `/save` 결과 제목과 안내 문구를 한국어로 표시한다.
- `/report save` 안내는 명령어 이름 그대로 유지하되, 설명은 한국어로 제공한다.
- 영어 기본 동작은 기존과 동일하게 유지한다.

## 설계

1. `presenters.py`에 save title/body helper를 추가한다.
2. `TrinityTextualApp._handle_textual_slash_command()`의 `/save` 분기를 helper 기반으로 교체한다.
3. presenter 단위 테스트와 한국어 `/save` 실행 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "save"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
