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
  - 세션 전용 설정 명령의 공통 안내 문구 추가
- `src/trinity/tui/prompt.py`
  - `TRINITY_COMMANDS`를 공통 registry에서 가져오도록 변경
- `src/trinity/tui/session.py`
  - plain TUI `_handle_command()`가 `parse_slash_command()`와 registry 기반 dispatch table을
    사용하도록 변경
  - registry alias(`/exit`, `/q`)가 `/quit` canonical command로 정규화된 뒤 실행됨
  - `/rounds`, `/agent`, `/caveman` 결과 출력에 세션 전용 적용과 config 파일 미저장 안내 추가
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
  - `/rounds`, `/agent`, `/caveman` 결과를 notification에만 띄우지 않고 중앙 `Local Command Results`에 기록
  - Start 화면의 `/status`는 toast 대신 status modal로 표시하고 workflow/Nexus 이동은 하지 않음
  - Status readiness `unknown`은 사용자에게 `not checked`로 표시
- `src/trinity/textual_app/snapshot.py`
  - `LocalCommandSnapshot`과 `WorkflowNexusSnapshot.local_commands` 추가
  - 조회 명령 결과의 구조화 렌더링을 위한 optional table column/row data 추가
  - active workflow가 없는 idle snapshot에서는 이전 `shared.md`의 `Agreed Conclusion`을
    현재 synthesis로 투영하지 않음
- `src/trinity/textual_app/widgets/central_agent.py`
  - 로컬 slash command 결과를 Nexus 중앙 영역의 `Local Command Results` 섹션에 표시
  - table data가 포함된 로컬 명령 결과를 중앙 영역의 `DataTable` 위젯으로 렌더링
  - `/status`처럼 같은 table command를 반복 실행해도 동적 table id가 충돌하지 않도록
    테이블 위젯은 class 기반으로 렌더링
  - 같은 로컬 slash command는 이전 결과를 교체해 반복 `/status`가 동일한 표를 계속
    쌓지 않게 처리
  - 로컬 command 제목은 inline-code 스타일을 제거해 클릭 가능한 버튼처럼 보이지 않게 렌더링
- `src/trinity/textual_app/widgets/status_modal.py`
  - Start 화면에서 쓰는 Textual-native status modal 추가
- `src/trinity/textual_app/workflow_controller.py`
  - `/answer` option/replace, `/target clear`, `/resume`을 앱이 private method에 기대지 않도록
    public Textual controller API로 제공
  - Textual `/resume` modal을 위한 archive option projection 제공
- `src/trinity/textual_app/widgets/resume_picker.py`
  - Textual-native workflow archive selector modal 추가

## 에이전트 호출 정책 반영

| 명령 분류 | 이번 구현 상태 |
| :--- | :--- |
| 로컬/UI 조회 | Nexus 중앙 영역의 `Local Command Results`에 누적 표시하고 에이전트 호출 금지 |
| 로컬 파일 기록 | `/report save`는 Markdown export, `/save`는 Textual 자동 persistence 안내 |
| 세션 설정 변경 | `/rounds`, `/agent`, `/caveman`은 현재 프로세스 config만 변경하고 config 파일 미저장을 표시 |
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
/home/zaemi/.local/bin/uvx ruff check src/trinity/tui/session.py tests/test_tui_prompt.py
/home/zaemi/.local/bin/uv run pytest tests/test_tui_prompt.py tests/test_tui_session.py -q
/home/zaemi/.local/bin/uvx ruff check tests/test_slash_command_docs.py
/home/zaemi/.local/bin/uv run pytest tests/test_slash_command_docs.py -q
/home/zaemi/.local/bin/uvx ruff check src/trinity/textual_app/app.py src/trinity/textual_app/workflow_controller.py src/trinity/textual_app/widgets/resume_picker.py tests/test_textual_app.py tests/test_textual_workflow_controller.py
/home/zaemi/.local/bin/uv run pytest tests/test_textual_workflow_controller.py tests/test_textual_app.py -q
/home/zaemi/.local/bin/uvx ruff check src/trinity/textual_app/app.py src/trinity/textual_app/snapshot.py src/trinity/textual_app/widgets/central_agent.py tests/test_textual_app.py
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py -q
/home/zaemi/.local/bin/uvx ruff check src/trinity/slash_commands.py src/trinity/tui/session.py src/trinity/textual_app/app.py tests/test_tui_session.py tests/test_textual_app.py
/home/zaemi/.local/bin/uv run pytest tests/test_tui_session.py::TestSessionCommands::test_session_setting_commands_show_session_only_notice tests/test_textual_app.py::test_textual_session_setting_commands_are_local_session_only_results -q
/home/zaemi/.local/bin/uv run pytest tests/test_tui_session.py tests/test_textual_app.py tests/test_slash_command_docs.py -q
/home/zaemi/.local/bin/uvx ruff check src/trinity/textual_app/widgets/central_agent.py tests/test_textual_app.py
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py::test_central_agent_view_renders_local_command_tables tests/test_textual_app.py::test_textual_status_refresh_replaces_existing_local_command_table -q
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py -q
/home/zaemi/.local/bin/uvx ruff check src/trinity/textual_app/app.py src/trinity/textual_app/snapshot.py src/trinity/textual_app/widgets/central_agent.py src/trinity/textual_app/widgets/status_modal.py tests/test_textual_app.py tests/test_textual_snapshot.py
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py::test_start_slash_status_does_not_start_workflow tests/test_textual_app.py::test_nexus_slash_workflow_does_not_submit_followup tests/test_textual_app.py::test_nexus_unknown_slash_does_not_submit_followup tests/test_textual_app.py::test_textual_status_refresh_replaces_existing_local_command_table tests/test_textual_snapshot.py::test_snapshot_does_not_project_stale_agreed_conclusion_without_workflow -q
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py -q
/home/zaemi/.local/bin/uvx ruff check src/trinity/textual_app/app.py src/trinity/textual_app/snapshot.py src/trinity/textual_app/widgets/central_agent.py src/trinity/textual_app/widgets/status_modal.py tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_slash_command_docs.py
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_slash_command_docs.py -q
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
- Plain TUI registry dispatch 대상 회귀: `95 passed in 2.17s`
- Slash command 문서 정합성 검증: `4 passed in 0.03s`
- Textual resume modal/controller 회귀: `62 passed in 30.98s`
- Textual local command table 렌더링 회귀: `52 passed in 24.32s`
- 세션 전용 설정 명령 안내 회귀: `2 passed in 1.19s`
- Plain/Textual/docs 대상 회귀: `136 passed in 26.22s`
- Local command table 반복 렌더링 회귀: `2 passed in 2.06s`
- Textual 전체 회귀: `54 passed in 26.02s`
- Status UX/stale synthesis 대상 회귀: `5 passed in 2.53s`
- Textual app/snapshot 회귀: `69 passed in 32.80s`
- Textual/docs 회귀: `73 passed in 26.25s`
- Ruff 대상 파일 검사 통과
- `git diff --check` 통과
- 전체 회귀: `1223 passed, 1 warning in 54.41s`

## 남은 작업

- Textual 조회 명령의 표현을 notification에서 central/inspector/report 영역의 구조화된
  panel/table로 확장
- `/resume` archive 목록을 Textual-native selector/modal로 표시
- command registry 기반 문서 table 자동 검증 추가
