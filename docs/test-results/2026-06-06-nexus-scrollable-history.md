# Nexus Scrollable History

작성일: 2026-06-06

브랜치: `codex/project-improvement-hardening`

## 문제

Nexus의 Central Agent 영역은 스크롤 가능한 컨테이너였지만 실제 내용은 현재 질문
1개 중심으로 렌더링됐다. 사용자가 이전 질문과 본인 답변을 계속 확인하기 어려웠다.

Provider 카드도 고정 높이의 `Vertical` 패널에 짧은 summary만 표시해 Claude, Codex,
Antigravity 응답이 길어지면 각 영역 안에서 내용을 계속 확인하기 어려웠다.

## 수정

- `WorkflowNexusSnapshot.questions`가 open question만이 아니라
  `session.pending_questions` 전체를 보존한다.
- `QuestionSnapshot`에 `status`와 `answer`를 추가해 답변 완료 질문과 사용자 답변을
  Central Agent 영역에 함께 표시한다.
- `CentralAgentView`가 모든 질문을 렌더링한다. 답변 완료 질문은 answer line을
  표시하고, 아직 열린 질문만 선택 버튼을 보여준다.
- Central Agent의 Decisions와 Work Packages 목록은 스크롤 영역에 맞춰 전체를
  표시한다.
- `ProviderPanel`을 `VerticalScroll` 기반으로 바꾸고, provider raw output을 카드
  내부에 담아 각 provider 영역에서 스크롤할 수 있게 했다.

## 효과

Nexus에서 사용자는 다음 내용을 계속 같은 화면에서 확인할 수 있다.

- Central Agent가 던진 모든 질문
- 각 질문의 현재 상태
- 사용자가 이미 답변한 내용
- Central Agent의 모든 decision/work package 목록
- Claude/Codex/Antigravity의 긴 provider output

따라서 후속 지시나 Execute 전 검토 중에도 이전 질의응답 맥락이 화면 밖으로 사라지지
않고, 각 영역 안에서 스크롤해 확인할 수 있다.

## 검증

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py::test_central_agent_view_renders_all_questions tests/test_textual_app.py::test_central_agent_view_keeps_answered_question_history tests/test_textual_app.py::test_provider_panel_renders_scrollable_raw_output tests/test_textual_snapshot.py::test_snapshot_keeps_answered_question_history -q
```

결과:

```text
4 passed in 4.75s
```

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_textual_workflow_controller.py tests/test_textual_smoke.py -q
```

결과:

```text
64 passed in 29.95s
```

```bash
/home/zaemi/.local/bin/uvx ruff check src/trinity/textual_app/snapshot.py src/trinity/textual_app/widgets/central_agent.py src/trinity/textual_app/widgets/provider_panel.py src/trinity/textual_app/screens/nexus.py src/trinity/textual_app/app.py tests/test_textual_app.py tests/test_textual_snapshot.py
```

결과:

```text
All checks passed!
```

```bash
python3 -m py_compile src/trinity/textual_app/snapshot.py src/trinity/textual_app/widgets/central_agent.py src/trinity/textual_app/widgets/provider_panel.py src/trinity/textual_app/screens/nexus.py src/trinity/textual_app/app.py
```

결과: 통과.

```bash
/home/zaemi/.local/bin/uv run pytest -q
```

결과:

```text
1173 passed, 1 warning in 61.24s
```

남은 경고는 기존 `AsyncMock` runtime warning 계열이다.
