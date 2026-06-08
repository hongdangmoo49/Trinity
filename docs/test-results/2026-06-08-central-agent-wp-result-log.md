# Central Agent WP/result log visibility

날짜: 2026-06-08
브랜치: `codex/review-workflow-design`

## 문제

Nexus의 Central Agent 영역은 snapshot을 렌더링하고 있었지만, WP graph가 synthesis
바로 아래에 대화 로그처럼 강조되어 남는 구조는 아니었다. local slash command 결과,
final review, post-review 항목 등에 밀려 사용자가 합의 이후 WP 목록을 찾기 어려웠다.

또한 WP 실행이 끝난 뒤 package별 실행 결과 summary, 변경 파일, blocker를 한데 모은
결과 보고 섹션이 Central Agent 영역에 명시적으로 표시되지 않았다.

## 수정

- Central Agent markdown에서 `Central WP Graph`와 `Local WP Graph`를 synthesis 바로
  아래에 표시하도록 순서를 고정했다.
- `work_package_details`에 실행 결과가 있으면 `Execution Result Summary` 섹션을
  렌더링한다.
- summary에는 결과 status count, package id, executor, package status, result summary,
  변경 파일, blocker를 포함한다.

## 검증

```text
uv run pytest tests/test_central_agent_view.py tests/test_textual_snapshot.py tests/test_textual_app.py::test_nexus_slash_workflow_does_not_submit_followup -q
```

결과:

```text
22 passed in 1.70s
```

추가 확인:

```text
uv run python -m py_compile src/trinity/textual_app/widgets/central_agent.py tests/test_central_agent_view.py
git diff --check
```

결과: 통과.

전체 검증:

```text
uv run pytest -q
```

결과:

```text
1296 passed, 1 warning in 102.17s
```

경고:

- `tests/test_e2e.py::TestE2EContext::test_context_shows_shared`의 기존
  `AsyncMock` unawaited warning.
