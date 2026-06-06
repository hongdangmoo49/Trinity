# Slash Command Routing Implementation

작성일: 2026-06-06

갱신일: 2026-06-07

브랜치: `codex/slash-command-docs`

## 목적

[Trinity Slash Command Routing Design](../plans/2026-06-06-trinity-slash-command-routing-design.md)을
바탕으로 Textual Start/Nexus에서 slash command가 일반 workflow prompt 또는 follow-up으로
넘어가 에이전트를 호출하는 문제를 1차로 차단했다.

## 구현 범위

- `src/trinity/slash_commands.py`
  - Trinity 앱 자체 top-level slash command registry 추가
  - command category, agent call policy, usage, localized summary 정의
  - plain TUI와 호환되는 `shlex.split()` 기반 parser 추가
- `src/trinity/tui/prompt.py`
  - `TRINITY_COMMANDS`를 공통 registry에서 가져오도록 변경
- `src/trinity/textual_app/i18n.py`
  - Textual slash palette 설명을 공통 registry에서 가져오도록 변경
- `src/trinity/textual_app/screens/start.py`
  - Start prompt가 slash command이면 `StartScreen.Submitted` 대신
    `StartScreen.SlashCommandSubmitted`를 발생시킴
- `src/trinity/textual_app/screens/nexus.py`
  - Nexus composer가 slash command이면 `FollowUpSubmitted`로 기록하지 않고
    `NexusScreen.SlashCommandSubmitted`를 발생시킴
- `src/trinity/textual_app/app.py`
  - Start/Nexus slash command handler 추가
  - 조회/unknown command가 `start_prompt()` 또는 `submit_follow_up()`으로 넘어가지 않게 처리
  - `/execute`는 기존 `TextualWorkflowController.request_execution()` 경로로 연결
  - `/answer`, `/target`, `/resume`, `/rounds`, `/agent`, `/caveman`, `/report`의 Textual 1차 처리 추가
  - `/questions --select`는 Textual 중앙 질문 영역의 option button과 `/answer` 안내로 처리
- `src/trinity/textual_app/snapshot.py`
  - `LocalCommandSnapshot`과 `WorkflowNexusSnapshot.local_commands` 추가
- `src/trinity/textual_app/widgets/central_agent.py`
  - 로컬 slash command 결과를 Nexus 중앙 영역의 `Local Command Results` 섹션에 표시
- `src/trinity/textual_app/workflow_controller.py`
  - `/answer` option/replace, `/target clear`, `/resume`을 앱이 private method에 기대지 않도록
    public Textual controller API로 제공

## 에이전트 호출 정책 반영

| 명령 분류 | 이번 구현 상태 |
| :--- | :--- |
| 로컬/UI 조회 | Nexus 중앙 영역의 `Local Command Results`에 누적 표시하고 에이전트 호출 금지 |
| 로컬 파일 기록 | `/report save`는 Markdown export, `/save`는 Textual 자동 persistence 안내 |
| 세션 설정 변경 | `/rounds`, `/agent`, `/caveman`은 현재 프로세스 config를 변경 |
| workflow 로컬 변경 | `/target`, `/resume`은 `TextualWorkflowController` public API를 통해 workflow/session을 갱신 |
| 조건부 재협의 | `/answer`는 workflow action 결과가 요구할 때만 deliberation으로 연결 |
| 명시 실행 | `/execute`만 execution request 경로로 연결 |
| unknown slash | notification 오류 후 입력 폐기, workflow prompt/follow-up 전달 금지 |

## 검증

실행한 명령:

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_tui_prompt.py tests/test_textual_app.py::test_start_slash_status_does_not_start_workflow tests/test_textual_app.py::test_start_unknown_slash_does_not_start_workflow tests/test_textual_app.py::test_nexus_slash_workflow_does_not_submit_followup tests/test_textual_app.py::test_nexus_unknown_slash_does_not_submit_followup tests/test_textual_app.py::test_prompt_composer_shows_slash_command_palette tests/test_textual_app.py::test_prompt_composer_localizes_slash_command_palette_in_korean tests/test_textual_app.py::test_nexus_composer_uses_configured_slash_command_language -q
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py tests/test_tui_prompt.py -q
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py tests/test_tui_prompt.py tests/test_textual_snapshot.py -q
/home/zaemi/.local/bin/uvx ruff check src/trinity/slash_commands.py src/trinity/tui/prompt.py src/trinity/textual_app/i18n.py src/trinity/textual_app/app.py src/trinity/textual_app/screens/start.py src/trinity/textual_app/screens/nexus.py tests/test_tui_prompt.py tests/test_textual_app.py
/home/zaemi/.local/bin/uvx ruff check src/trinity/textual_app/app.py src/trinity/textual_app/snapshot.py src/trinity/textual_app/widgets/central_agent.py tests/test_textual_app.py
/home/zaemi/.local/bin/uvx ruff check src/trinity/textual_app/app.py src/trinity/textual_app/workflow_controller.py tests/test_textual_app.py tests/test_textual_workflow_controller.py
/home/zaemi/.local/bin/uv run pytest tests/test_textual_workflow_controller.py tests/test_textual_app.py -q
git diff --check
/home/zaemi/.local/bin/uv run pytest -q
```

결과:

- Slash command 대상 테스트: `23 passed in 4.51s`
- Textual/prompt 관련 전체 테스트: `63 passed in 27.58s`
- Textual/prompt/plain command 관련 테스트: `77 passed in 29.58s`
- Textual/prompt/snapshot 관련 테스트: `77 passed in 28.70s`
- Central local command result 회귀: `4 passed in 3.00s`
- Textual controller/slash routing 보강: `60 passed in 30.89s`
- Textual/controller/prompt 대상 회귀: `76 passed in 32.59s`
- Ruff 대상 파일 검사 통과
- `git diff --check` 통과
- 전체 회귀: `1211 passed, 1 warning in 63.76s`

## 남은 작업

- Textual 조회 명령의 표현을 notification에서 central/inspector/report 영역의 구조화된
  panel/table로 확장
- `/resume` archive 목록을 Textual-native selector/modal로 표시
- command registry 기반 문서 table 자동 검증 추가
