# Provider Error Retry Gate Redesign

작성일: 2026-06-17
작업 브랜치: `feature/provider-error-retry-gate`
상태: implementation draft

## 목적

현재 Nexus 실행/기획 화면에서 provider가 `[Error: exit code 1]` 같은 실패 응답을 반환해도
provider 카드가 `완료`로 표시될 수 있다. 또한 deliberation 단계에서는 실패 응답이 consensus 입력에서
제외된 뒤, 남은 usable 응답만으로 중앙 에이전트가 즉시 집계할 수 있다.

이 문서는 provider 오류가 발생했을 때 Trinity가 성공처럼 보이지 않도록 만들고, 중앙 에이전트가
집계 전에 사용자에게 재시도/제외 후 계속/중단 결정을 요청하는 흐름을 설계한다.

## 현재 문제

### Provider 카드 상태

`NexusSnapshotAdapter._fold_recent_events()`는 `AGENT_RESPONDED` 이벤트를 받으면 응답 metadata의
`response_status`를 확인하지 않고 provider 상태를 `Ready`로 바꾼다.

`Ready`는 compact status에서 `done` 그룹으로 분류되고, 한국어 UI에서는 `완료`로 렌더링된다.
따라서 실패 내용이 summary에 남아도 카드 상태는 성공처럼 보인다.

### Deliberation 집계

`DeliberationProtocol`은 non-ok 응답을 `Response Diagnostics`에 남기고 consensus 입력에서는 제외한다.
이 정책 자체는 한 provider가 auth wait, timeout, CLI noise를 반환해도 나머지 agent로 계속 진행할 수 있어
유용하다.

문제는 이 동작이 사용자에게 명시되지 않는다는 점이다. agent 수가 1개 또는 2개뿐인 경우 하나의 실패는
결과 품질에 큰 영향을 주지만, UI는 즉시 중앙 집계 결과를 보여줄 수 있다.

### 실행 WP 경로

WP 실행 경로는 이미 `response_status != ok`를 `WorkStatus.FAILED`로 바꾼다. 다만 실행 run은 실패 시에도
내부 run state가 `completed`로 닫히기 때문에, 기존 recovery UI가 실패 직후 항상 자연스럽게 노출되지는 않는다.

## 설계 원칙

- provider 응답 도착과 성공을 분리한다.
- `response_status != ok`는 UI에서 `문제` 상태로 표시한다.
- 중앙 집계는 실패 provider가 있을 때 사용자의 명시적 결정을 기다릴 수 있어야 한다.
- 기존 retry/recovery 흐름을 재사용하고, 새 상태는 최소화한다.
- provider가 하나만 활성화된 경우 실패를 무시하고 계속 집계하는 선택은 제공하지 않는다.
- provider가 둘 이상이면 실패 agent만 재시도하거나, 실패를 제외하고 계속 집계하거나, 중단할 수 있다.

## 구현 단위

### 1. Provider panel non-ok 표시

변경 대상:

- `src/trinity/textual_app/snapshot.py`
- `src/trinity/textual_app/widgets/provider_panel.py`
- `tests/test_textual_snapshot.py`
- `tests/test_textual_app.py`

내용:

- `ProviderSnapshot`에 `response_status`를 추가한다.
- `AGENT_RESPONDED` 이벤트 metadata 또는 top-level `response_status`가 `ok`가 아니면 provider status를 `Error`로 투영한다.
- 최근 response artifact만 있는 경우에도 `agent_response.status` 또는 `response_status`를 읽어 non-ok면 `Error`로 표시한다.
- provider panel summary에는 실패 내용을 유지하되 상태 라벨은 `문제`로 표시한다.

### 2. Deliberation 실패 metadata 기록

변경 대상:

- `src/trinity/deliberation/protocol.py`
- `src/trinity/models.py`
- `tests/test_protocol.py`

내용:

- `DeliberationResult.metadata`에 `provider_failures`를 추가한다.
- 각 failure에는 agent, status, classification, reasons, retryable 여부를 기록한다.
- 기존 `invalid_response_diagnostics`와 중복되지 않게 같은 데이터를 재사용한다.
- `has_provider_failures` 성격의 helper는 metadata 기반으로 판단한다.

### 3. 중앙 집계 전 retry gate

변경 대상:

- `src/trinity/workflow/engine.py`
- `src/trinity/workflow/models.py`
- `tests/test_workflow_engine.py`

내용:

- deliberation result에 retryable provider failure가 있으면 즉시 blueprint 확정 전에 `NEEDS_USER_DECISION`으로 전환한다.
- `OpenQuestion`을 추가해 사용자가 선택하게 한다.
- 선택지:
  - failed providers retry
  - continue without failed providers
  - stop workflow
- provider가 1개만 활성화되어 있고 그 provider가 실패한 경우 `continue` 선택지는 만들지 않는다.
- pending result는 session에 보존해 사용자가 continue를 고르면 기존 result로 `mark_deliberation_result`를 이어갈 수 있게 한다.

### 4. 중앙 액션/명령 UX 연결

변경 대상:

- `src/trinity/textual_app/workflow_controller.py`
- `src/trinity/textual_app/widgets/central_agent.py`
- `src/trinity/textual_app/app.py`
- `tests/test_textual_workflow_controller.py`
- `tests/test_textual_app.py`

내용:

- retry gate 질문이 열려 있으면 중앙 에이전트 패널에 재시도/제외하고 계속/중단 액션을 노출한다.
- 재시도는 실패 provider를 대상으로 새 deliberation run을 시작한다.
- 제외하고 계속은 보존된 deliberation result를 적용한다.
- 중단은 workflow를 `FAILED`로 전환한다.
- slash command fallback은 `/answer`를 유지하되, 중앙 패널 action이 기본 UX가 된다.

### 5. 실행 실패 recovery 보강

변경 대상:

- `src/trinity/workflow/engine.py`
- `src/trinity/textual_app/snapshot.py`
- `tests/test_workflow_engine.py`
- `tests/test_textual_snapshot.py`

내용:

- execution run outcome이 failed인 경우에도 retry candidates가 있으면 recovery snapshot을 노출한다.
- 실행 실패 후 자동 리뷰/집계로 넘어가지 않고 retry modal/action을 유도한다.
- provider panel은 failed WP의 owner 또는 last_executor를 `문제`로 유지한다.

## UX 흐름

### 기획/중앙 집계 단계

1. provider 병렬 응답 수집
2. 하나 이상의 provider가 non-ok 응답 반환
3. usable 응답만으로 consensus가 가능하더라도 workflow는 `NEEDS_USER_DECISION`
4. 중앙 패널 표시:

```text
Provider 응답 문제 발생
Claude: auth_required / exit code 1

[실패 provider 재시도] [실패 제외하고 계속] [중단]
```

5. 사용자가 선택한 뒤 다음 단계 진행

### 실행 WP 단계

1. WP 실행 중 provider 실패
2. WP status는 `failed`
3. provider panel은 `문제`
4. 중앙 패널 또는 recovery modal에서 retry 후보 표시
5. 사용자가 retry/abort 선택

## 테스트 전략

- non-ok `AGENT_RESPONDED` 이벤트가 provider status `Error`로 투영되는지 검증
- artifact metadata non-ok 상태가 snapshot에 반영되는지 검증
- deliberation result metadata에 provider failures가 들어가는지 검증
- 실패 provider가 있으면 workflow가 blueprint 확정 전에 decision state로 멈추는지 검증
- continue 선택 시 기존 result가 적용되어 blueprint ready가 되는지 검증
- retry 선택 시 failed provider만 대상으로 새 run이 시작되는지 검증
- 실행 실패 후 recovery snapshot이 노출되는지 검증
- 전체 pytest와 `trinity --version` 검증

## 릴리스

구현 완료 후 패치 버전을 `0.13.4`로 올린다.
