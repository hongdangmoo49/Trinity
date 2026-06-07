# Slash Command UX Hardening Test Results

작성일: 2026-06-07

대상 브랜치: `codex/slash-command-docs`

## 변경 범위

- Textual lookup slash command 결과를 body, empty state, action hint, read-only table로 표준화했다.
- `/subtasks`가 저장된 `WorkflowSession.subtask_results`와 execution result 내부 subtask를 표시하도록 snapshot을 확장했다.
- `/report` empty state와 `/report save` 저장 경로를 local command result로 남긴다.
- `/rounds`, `/agent`, `/caveman` no-arg/arg 결과를 현재 값 table과 세션 전용 안내로 통일했다.
- `/resume`, `/answer`, `/execute` 오류/준비 실패와 unknown slash를 toast-only가 아닌 local command result로 남긴다.
- Textual `/quit`, `/exit`, `/q`는 즉시 종료 대신 confirmation modal을 사용한다.

## 실행한 검증

```text
uvx ruff check src/trinity/textual_app/app.py src/trinity/textual_app/snapshot.py src/trinity/textual_app/report_export.py src/trinity/textual_app/widgets/central_agent.py src/trinity/textual_app/widgets/confirm_quit_modal.py tests/test_textual_app.py
```

결과: 통과

```text
uv run pytest tests/test_textual_app.py::test_start_slash_help_uses_registry_backed_local_modal tests/test_textual_app.py::test_nexus_lookup_commands_record_tables_from_current_snapshot tests/test_textual_app.py::test_nexus_empty_lookup_commands_record_empty_states tests/test_textual_app.py::test_nexus_report_without_data_records_empty_result tests/test_textual_app.py::test_nexus_report_save_records_export_path -q
```

결과: `5 passed`

```text
uv run pytest tests/test_textual_app.py::test_nexus_setting_commands_show_current_tables tests/test_textual_app.py::test_nexus_resume_answer_and_execute_errors_record_local_results tests/test_textual_app.py::test_nexus_unknown_slash_suggests_close_commands tests/test_textual_app.py::test_start_quit_slash_uses_confirmation_modal -q
```

결과: `4 passed`

## 남은 확인

```text
uv run pytest tests/test_textual_app.py tests/test_slash_command_docs.py -q
```

결과: `77 passed`

```text
git diff --check
```

결과: 통과

```text
uv run pytest -q
```

결과: `1243 passed, 1 warning`

경고: 기존 `tests/test_e2e.py::TestE2EContext::test_context_shows_shared`의
`AsyncMockMixin._execute_mock_call was never awaited` RuntimeWarning.
