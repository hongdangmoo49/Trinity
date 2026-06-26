# Slash Command 알림 제목 한국어 라벨 개선

## 배경

Nexus에서 로컬 slash command를 실행하면 중앙 패널에 결과가 기록되고 notify가 표시된다. 이 notify의 제목은 `"Slash Command"`로 고정되어 있어 한국어 설정에서도 영어로 보인다.

## 목표

- 한국어 설정에서 로컬 slash command notify 제목을 `슬래시 명령`으로 표시한다.
- 기존 영어 기본 제목은 `Slash Command`로 유지한다.
- 각 명령의 결과 제목/본문 동작은 변경하지 않는다.

## 설계

1. `presenters.py`에 slash command notification title helper를 추가한다.
2. `_present_local_command_result()`에서 helper를 사용한다.
3. Nexus 로컬 명령 실행 시 한국어 notify title을 검증한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "slash_command_notification or local_command_notify"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
