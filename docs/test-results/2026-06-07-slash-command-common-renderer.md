# Slash Command Common Renderer Validation

작성일: 2026-06-07

브랜치: `codex/slash-command-docs`

## 목적

`docs/plans/2026-06-07-trinity-slash-command-ux-contract.md`의 첫 구현 단위인
공통 local command result model과 Start/Nexus renderer를 적용했다.

## 구현 내용

- `src/trinity/textual_app/snapshot.py`
  - `LocalCommandSnapshot`에 `result_kind`, `empty`, `action_hint` 필드 추가
- `src/trinity/textual_app/widgets/local_command_modal.py`
  - Start 화면에서 generic local slash command 결과를 보여주는 modal 추가
  - Markdown 본문, read-only plain table, action hint 표시 지원
- `src/trinity/textual_app/app.py`
  - `_record_slash_command_result()`가 Start에서는 generic modal, Nexus에서는 central result로 렌더링되도록 공통화
  - `/history`, `/save`, `/target`의 toast-only 흐름을 local command result 기록으로 전환
- `src/trinity/textual_app/widgets/central_agent.py`
  - `LocalCommandSnapshot.action_hint`를 central result에 표시
- `tests/test_textual_app.py`
  - Start `/workflow`가 generic modal을 띄우는지 검증
  - Nexus `/save`, `/target`이 central result에 기록되는지 검증

## 검증

실행한 명령:

```bash
/home/zaemi/.local/bin/uvx ruff check src/trinity/textual_app/app.py src/trinity/textual_app/snapshot.py src/trinity/textual_app/widgets/central_agent.py src/trinity/textual_app/widgets/local_command_modal.py tests/test_textual_app.py
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py::test_start_slash_workflow_uses_generic_local_command_modal tests/test_textual_app.py::test_nexus_save_and_target_commands_record_local_results tests/test_textual_app.py::test_nexus_slash_workflow_does_not_submit_followup tests/test_textual_app.py::test_start_unknown_slash_does_not_start_workflow -q
/home/zaemi/.local/bin/uvx ruff check src/trinity/textual_app/app.py src/trinity/textual_app/snapshot.py src/trinity/textual_app/widgets/central_agent.py src/trinity/textual_app/widgets/local_command_modal.py tests/test_textual_app.py tests/test_slash_command_docs.py
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py tests/test_slash_command_docs.py -q
git diff --check
/home/zaemi/.local/bin/uv run pytest -q
```

결과:

- Ruff 대상 파일 검사 통과
- 공통 renderer 대상 회귀: `4 passed in 4.86s`
- Textual slash/docs 회귀: `68 passed in 52.43s`
- `git diff --check` 통과
- 전체 회귀: `1234 passed, 1 warning in 87.08s`

## 다음 구현 단위

1. 조회 명령(`/help`, `/questions`, `/decisions`, `/packages`, `/subtasks`, `/history`, `/report`)의 body/table/empty state를 UX 계약대로 보강
2. 설정 명령(`/rounds`, `/agent`, `/caveman`)의 no-arg modal과 arg 결과 표시를 표준화
3. `/target`, `/resume`, `/questions --select`, `/answer`의 picker/modal 흐름 정리
