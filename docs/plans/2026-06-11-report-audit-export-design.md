# Report Audit Export Design

**Status:** Design
**Date:** 2026-06-11
**Branch:** `codex/design-report-audit-export`
**Related plan:** `docs/plans/2026-06-05-deliberation-report.md`

## Goal

`/report`, `/report save`, Textual Report 화면, Report 화면 export가 같은 canonical report 모델을 사용하게 만든다. 이 report는 기존 협의 결과뿐 아니라 중앙 에이전트와의 채팅 내역, 실행 페이지의 로그, provider/model/session 정보, target workspace, review/repair/recovery 결과까지 감사 추적(audit trail) 가능한 형태로 내보내야 한다.

## Current State

현재 report 경로는 두 갈래다.

- Plain TUI는 `src/trinity/tui/report.py`의 `DeliberationReportBuilder`가 `WorkflowSession`과 선택적 `DeliberationResult`를 읽어 `DeliberationReport`를 만든다.
- Plain TUI `/report save`는 이 모델의 `to_markdown()`을 저장한다.
- Textual Report 화면은 `src/trinity/textual_app/screens/report.py`에서 `DeliberationReport`를 받을 수 있지만, export는 `src/trinity/textual_app/app.py`의 `_export_report_markdown()`이 처리한다.
- Textual export는 persisted session이 있으면 `DeliberationReportBuilder`를 사용하고, 없으면 `src/trinity/textual_app/report_export.py`의 `snapshot_report_markdown()`으로 fallback한다.
- `snapshot_report_markdown()`에는 providers, snapshot execution log, execution recovery, local command 일부가 들어가지만 canonical `DeliberationReport`에는 아직 반영되지 않는다.
- 실행 화면의 event tail은 `src/trinity/textual_app/snapshot.py`의 `_execution_log()`와 `_workflow_events()`에서 `WorkflowPersistence.load_events_for_workflow()` 결과를 화면용 문자열로 변환한다.
- 중앙 에이전트 화면은 `src/trinity/textual_app/widgets/central_agent.py`의 `_markdown()`에서 goal, synthesis, central response, work package graph, local command result, final review, post review, decisions, subtasks를 조립한다. 그러나 이것은 화면용 projection이고 대화 transcript로 영속화되지는 않는다.

이 구조 때문에 persisted session이 존재하는 정상 경로일수록 오히려 Textual snapshot에 있던 실행 로그와 중앙 화면 기록이 Markdown report에서 빠질 수 있다.

## Requirements

P0 우선순위 요구사항:

1. `DeliberationReportBuilder`를 report의 단일 canonical 모델 진입점으로 만든다.
2. Textual snapshot Markdown export는 session이 없는 상황의 fallback으로만 둔다.
3. canonical report에 provider/model/session, target workspace, review 결과, repair/retry/recovery 정보를 포함한다.
4. Markdown escaping과 fenced block 처리를 모든 사용자/agent 입력 섹션에 일관 적용한다.
5. `/report`, `/report save`, Report 화면, Report 화면 export가 같은 데이터 섹션을 보여준다.

이번 추가 요구사항:

6. 중앙 에이전트와의 채팅 내역을 report에 포함한다.
7. 실행 페이지의 로그를 report에 포함한다.

## Report Model

`src/trinity/tui/report.py`에 기존 DTO를 유지하면서 아래 DTO를 추가한다.

```python
@dataclass(frozen=True)
class ReportProvider:
    name: str
    provider: str
    configured_model: str
    actual_model: str
    context_window: int
    budget_source: str
    provider_session_id: str
    session_kind: str
    cwd: str


@dataclass(frozen=True)
class ReportConversationMessage:
    timestamp: float
    role: str              # user | central | system | tool
    channel: str           # start | nexus | report | local_command
    title: str
    body: str
    command: str = ""
    related_ids: tuple[str, ...] = ()
    truncated: bool = False


@dataclass(frozen=True)
class ReportExecutionEvent:
    timestamp: float
    event: str
    state: str
    run_id: str
    package_id: str
    agent: str
    status: str
    target_workspace: str
    summary: str
    raw_data: dict[str, object]
```

`DeliberationReport`에는 아래 필드를 추가한다.

- `target_workspace: str`
- `providers: tuple[ReportProvider, ...]`
- `conversation: tuple[ReportConversationMessage, ...]`
- `execution_events: tuple[ReportExecutionEvent, ...]`
- `reviews: tuple[ReportReview, ...]`
- `repairs: tuple[ReportRepair, ...]`
- `recovery: ReportRecovery | None`

`ReportReview`, `ReportRepair`, `ReportRecovery`는 이미 `WorkflowSession.review_results`, `WorkPackage.repair_notes`, `WorkflowSession.execution_run`, snapshot `ExecutionRecoverySnapshot`에 있는 정보를 lossless에 가깝게 옮기는 thin DTO로 둔다.

## Data Sources

Canonical builder는 다음 순서로 데이터를 모은다.

1. `WorkflowSession`
   - goal, state, active agents, current round, target workspace
   - blueprint, work packages, execution results, subtasks
   - decisions, pending questions
   - review packages/results, post review items, follow-up requests
   - execution run/recovery metadata
   - provider sessions, runtime models
2. `WorkflowPersistence.load_events_for_workflow(session.id)`
   - workflow timeline
   - execution matrix log
   - central conversation transcript
3. 선택적 `WorkflowNexusSnapshot`
   - session이 아직 저장되지 않았거나, 화면에서만 존재하는 local command result를 보강할 때 사용한다.
   - snapshot 문자열이 canonical session/event 데이터를 덮어쓰면 안 된다.

이를 위해 `DeliberationReportBuilder.build()`는 다음 형태로 확장한다.

```python
def build(
    self,
    session: WorkflowSession,
    result: DeliberationResult | None = None,
    *,
    events: Sequence[Mapping[str, object]] = (),
    snapshot: WorkflowNexusSnapshot | None = None,
) -> DeliberationReport:
    ...
```

Textual app은 export 시 `WorkflowPersistence.load_events_for_workflow(session.id)`를 읽어 builder에 넘긴다.

## Central Agent Conversation

현재 중앙 에이전트 화면은 `WorkflowNexusSnapshot`을 Markdown으로 조립해 보여줄 뿐, "채팅 내역"을 독립된 데이터로 저장하지 않는다. report에서 신뢰 가능한 내역을 만들려면 append-only event가 필요하다.

새 event:

```json
{
  "event": "central_conversation_recorded",
  "workflow_id": "wf-...",
  "timestamp": 1781136000.0,
  "state": "blueprint_ready",
  "data": {
    "message_id": "cc-...",
    "role": "central",
    "channel": "nexus",
    "title": "Central Agent Response",
    "body": "...",
    "command": "",
    "related_ids": ["WP-001"],
    "truncated": false
  }
}
```

기록 대상:

- 사용자가 Start/Nexus 입력창에 보낸 workflow 목표와 후속 지시
- 중앙 synthesis summary와 central blueprint response
- 중앙 에이전트가 던진 질문과 사용자의 답변
- local slash command 결과 중 중앙 화면에 표시된 항목
- blueprint-ready action 선택
- review/post-review follow-up 제안과 사용자의 선택

중앙 대화 report 섹션:

````markdown
## Central Agent Conversation

### 2026-06-11 20:42:38 - central - Central Agent Response

```text
...
```
````

대화 본문은 table cell에 넣지 않고 fenced block으로 렌더링한다. Markdown 특수문자 escaping으로 의미가 깨지지 않게 하기 위해 본문은 `_md_block()` 계열 helper를 사용한다.

## Execution Page Logs

실행 페이지의 현재 로그는 session events를 tail 80개로 제한해 화면 문자열로 보여준다. report는 화면 tail이 아니라 event 원본을 `ReportExecutionEvent`로 정규화한다.

포함할 event:

- `target_workspace_selected`
- `execution_enabled`
- `implementation_requested`
- `execution_run_started`
- `execution_batch_planned`
- `work_package_started`
- `work_package_completed`
- `execution_result_recorded`
- `execution_interrupted_detected`
- `work_package_retry_requested`
- `work_package_retry_skipped`
- `execution_recovery_action`
- `review_result_recorded`
- `review_repair_requested`
- `state_changed`
- `workflow_continued`

Markdown report에는 요약 테이블과 상세 로그를 모두 둔다.

````markdown
## Execution Timeline

| Time | Event | Package | Agent | Status | Summary |
| --- | --- | --- | --- | --- | --- |

## Execution Event Details

### execution_run_started

```json
{ ... redacted data ... }
```
````

Report 화면은 기본적으로 요약 테이블과 마지막 80개 이벤트를 보여주고, saved Markdown은 전체 이벤트를 포함한다. 이벤트가 너무 많으면 기본 cap을 500개로 두고 `truncated: true` 및 생략 개수를 명시한다. 구현 중 config가 필요하다고 판단되면 `report_event_limit`을 추가하되, 초기 구현은 상수로 시작한다.

## Rendering Rules

- Inline 값은 `_md_inline()` 스타일 escaping을 적용한다.
- 긴 본문, 중앙 대화, raw event data, agent output summary는 fenced block으로 렌더링한다.
- Rich 화면은 표와 panel을 유지하되, 중앙 대화와 execution timeline은 너무 길어질 수 있으므로 summary-first로 렌더링한다.
- saved Markdown은 감사를 위한 artifact이므로 UI보다 상세해야 한다.
- secret-looking 값은 report 직전에 redaction helper를 거친다.
- raw provider output 전체를 무조건 포함하지 않는다. 사용자가 중앙 에이전트 화면에서 실제로 본 central response/local command/result와 workflow event만 기본 report 대상이다.

## Command and Screen Flow

Plain TUI:

1. `/report`가 `WorkflowSession`, optional `DeliberationResult`, workflow events를 builder에 전달한다.
2. console render는 canonical report의 Rich render를 사용한다.
3. `/report save`는 같은 report 인스턴스의 Markdown을 저장한다.

Textual:

1. `switch_to("report")`는 snapshot fallback을 먼저 보여줄 수 있지만, persisted session이 있으면 events를 포함해 canonical report를 다시 적용한다.
2. Report 화면 export는 snapshot Markdown을 직접 만들지 않고 canonical report export를 호출한다.
3. session이 없는 preflight/new snapshot만 `snapshot_report_markdown()` fallback을 사용한다.
4. fallback Markdown도 canonical 섹션명과 escaping 규칙을 맞춘다.

## Implementation Plan

P0 - Canonical report 확장:

- `ReportProvider`, `ReportExecutionEvent`, review/repair/recovery DTO 추가
- `DeliberationReportBuilder.build(..., events=(), snapshot=None)` 확장
- provider/session/model/target workspace/review/repair/recovery Markdown 섹션 추가
- `/report`, `/report save`, Textual export가 같은 builder를 쓰도록 정리

P1 - 중앙 에이전트 transcript:

- `central_conversation_recorded` event 도입
- user prompt, central response, question/answer, local command result, action selection 기록 지점 연결
- builder가 event를 `ReportConversationMessage`로 정규화
- Report 화면과 Markdown에 `Central Agent Conversation` 섹션 추가

P2 - 실행 페이지 로그 export:

- workflow events를 `ReportExecutionEvent`로 정규화
- 실행 timeline 요약 테이블과 raw detail appendix 추가
- Textual execution screen tail과 report export full/capped log의 차이를 테스트로 고정

P3 - fallback 정리:

- `snapshot_report_markdown()`은 session 없는 경우만 담당하도록 문서/테스트 정리
- duplicate formatting helper를 `report.py` 또는 별도 `report_markdown.py`로 모아 escaping 차이를 제거

## Test Plan

Unit tests:

- `tests/test_report.py`
  - provider/session/model metadata가 Markdown에 포함된다.
  - target workspace가 포함된다.
  - central conversation event가 fenced block으로 렌더링된다.
  - execution events가 timeline과 detail section에 포함된다.
  - review/repair/recovery 정보가 누락되지 않는다.
  - Markdown 특수문자와 table pipe가 escape된다.
  - long conversation/event body는 truncation 표시가 남는다.

Textual tests:

- `tests/test_textual_app.py`
  - persisted session export가 snapshot-only export보다 우선하되, events를 포함한다.
  - Report 화면 apply/export가 같은 canonical report 내용을 사용한다.
  - session 없는 snapshot fallback은 기존처럼 파일을 만든다.
  - local command result가 central conversation 또는 fallback report에 포함된다.

Persistence tests:

- `tests/test_workflow_persistence.py`
  - `central_conversation_recorded` event가 JSONL에 append/load round-trip된다.
  - workflow id filter와 tail filter가 central/execution event에 동일하게 작동한다.

Regression tests:

- `/report` empty state는 기존 안내를 유지한다.
- `/report save` 파일명 충돌 방지는 유지한다.
- Textual `/report save` local command 결과에는 저장 경로가 기록된다.

## Acceptance Criteria

- 같은 workflow에서 `/report`, `/report save`, Report 화면 export의 주요 섹션이 일치한다.
- saved Markdown에는 중앙 에이전트와의 채팅 내역이 포함된다.
- saved Markdown에는 실행 페이지의 execution log가 포함된다.
- persisted session이 있는 경우에도 Textual snapshot에만 있던 실행/중앙 화면 정보가 누락되지 않는다.
- session이 없는 snapshot fallback은 계속 동작한다.
- report에 target workspace와 provider runtime model/session 정보가 들어간다.
- review, repair, retry, recovery 흐름이 report에서 추적 가능하다.
- Markdown injection, table breakage, secret-looking 값 노출 위험이 테스트로 방어된다.

## Risks and Open Questions

- 중앙 에이전트 transcript의 정확한 기록 지점은 UI event handler와 workflow engine 양쪽에 걸쳐 있다. 첫 구현에서는 workflow/session에 영향을 주는 사용자 입력과 central response부터 기록하고, 화면-only local command는 후속으로 보강한다.
- report가 너무 커질 수 있다. saved Markdown은 상세성을 우선하되 event cap과 truncation marker를 둔다.
- raw event data는 디버깅에 유용하지만 민감 정보가 섞일 수 있다. redaction helper 없이는 raw detail section을 기본 활성화하지 않는다.
- provider-native session 전체 대화 로그는 provider별 저장 위치와 권한이 다르다. 이번 범위의 "중앙 에이전트 채팅"은 Trinity가 중앙 화면에서 생성/표시한 conversation event로 한정한다.
