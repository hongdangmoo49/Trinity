# Textual Local Command Snapshot Refactor

## 배경

`TrinityTextualApp._local_command_snapshot`은 `textual_presenters.local_command_snapshot`에 동일한 인자를 전달하는 delegate였다. 로컬 slash command 결과 생성은 이미 presenter 계층에 순수 함수로 분리되어 있으므로 앱 내부 wrapper를 유지할 필요가 작다.

## 목표

- `_local_command_snapshot` wrapper를 제거한다.
- slash command result, status, context 결과 생성은 presenter 함수를 직접 호출하게 한다.
- local command 결과 기록, modal 표시, Nexus snapshot 갱신 동작은 변경하지 않는다.
- 패치 버전을 `1.0.326`으로 올린다.

## 변경 계획

1. `_record_slash_command_result`, `_show_textual_status`, `_handle_textual_context_command`의 snapshot 생성 호출을 presenter 직접 호출로 교체한다.
2. `_local_command_snapshot` method를 삭제한다.
3. 기존 local command snapshot presenter 테스트와 TextualApp focused 테스트로 회귀를 확인한다.

## 검증

- `git diff --check`
- `uv run trinity --version`
- `uv run pytest -q tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_textual_command_parsers.py tests/test_slash_commands.py`
- `uv run pytest -q`
