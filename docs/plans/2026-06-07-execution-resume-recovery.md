# Execution Resume Recovery Design

작성일: 2026-06-07

브랜치: `codex/execution-resume-recovery-design`

상태: 설계

## 목적

사용자가 `/execute` 이후 실수로 Trinity TUI를 종료했거나 터미널이 끊긴 상황에서,
`/resume`으로 돌아왔을 때 현재 실행 상태를 오해하지 않고 안전하게 복구할 수 있게 한다.

현재 Textual execution은 앱 프로세스 내부 background thread에서 provider one-shot 호출을
수집한다. 앱이 종료되면 session file은 남지만 background worker와 event bus는 사라진다.
provider child process가 OS에 남아 있을 수 있어도 Trinity가 그 결과를 안정적으로 reattach
할 수 있다는 보장은 없다. 따라서 기본 복구 정책은 "실행 worker 재연결"이 아니라
"stale running 상태 감지 후 사용자가 재시도/중단/검토를 선택"하는 구조여야 한다.

## 현재 관찰된 문제

| 증상 | 원인 | 영향 |
| :--- | :--- | :--- |
| resume 후 `executing` 상태가 남아 있음 | worker thread는 프로세스 내부 객체라 종료 후 복원 불가 | 사용자는 실행이 계속 중인지 멈췄는지 알 수 없음 |
| WP가 `running`으로 남을 수 있음 | `work_package_started`는 persisted event지만 완료 event는 수집 전 종료될 수 있음 | `/execute` 재시도 기준이 불명확 |
| provider child process가 남을 수 있음 | CLI one-shot 호출은 Trinity 외부 프로세스로 실행됨 | 동일 WP를 중복 실행할 위험 |
| target workspace에 일부 파일이 이미 생성됨 | provider가 종료 전 파일을 썼을 수 있음 | 재시도 시 덮어쓰기/충돌 가능 |
| fallback 실행이 같은 WP를 다른 agent에게 보낼 수 있음 | `blocked` 결과를 fallback 후보에게 전달하는 정책 | UI상 "여러 agent가 같은 WP running"처럼 보임 |

## 목표

1. `/resume` 또는 app startup 시 stale execution을 명확히 감지한다.
2. 실행 중단 상태를 UI에서 숨기지 않고 recovery surface로 노출한다.
3. 자동 재시도보다 사용자 선택을 우선한다.
4. 재시도 전 target workspace의 기존 산출물과 package 상태를 보여준다.
5. provider one-shot 결과 reattach는 지원하지 않는 것으로 명시한다.
6. 이미 완료된 package는 재실행하지 않고, 중단/실패/blocked package만 선택적으로 처리한다.

## 비목표

- 종료된 provider CLI process에 대한 완전한 reattach 구현
- target workspace의 semantic merge 자동화
- provider별 long-running job manager 구현
- 모든 OS에서 child process kill/restore를 완벽히 보장하는 기능
- 사용자의 target workspace 변경사항을 자동 revert하는 기능

## 상태 모델

### 기존 상태

현재 workflow state는 `executing`, `reviewing`, `needs_user_decision`, `failed` 등으로
표현된다. work package status는 `pending`, `running`, `done`, `blocked`, `failed`,
`waiting_on_decision` 등을 사용한다.

### 추가할 실행 복구 개념

새 enum을 즉시 추가하기보다, 1차 구현은 session metadata와 local command result를 통해
stale 여부를 표현한다. 이후 필요하면 `WorkStatus.INTERRUPTED`를 도입한다.

1차 metadata 초안:

```json
{
  "execution_run": {
    "run_id": "exec-run-20260607-001",
    "started_at": 1780834845.17,
    "heartbeat_at": 1780835017.96,
    "state": "running|interrupted|completed",
    "interrupted_reason": "app_exit|process_lost|unknown",
    "target_workspace": "/home/zaemi/workspace/hyper"
  }
}
```

### Stale 판단 기준

앱 시작 또는 `/resume` 직후 다음 조건을 모두 만족하면 stale execution으로 본다.

- workflow state가 `executing`
- 현재 `TextualWorkflowController.is_running`이 false
- `running` package가 하나 이상 있거나, `execution_run.state == running`
- 마지막 heartbeat가 현재 프로세스에서 갱신되지 않음

Plain TUI에서도 같은 persisted state를 사용하되, UI는 modal 대신 안내 panel과 command
prompt를 사용한다.

## Recovery UX

### `/resume` 성공 직후

`/resume`이 workflow를 복원했을 때 stale execution이 감지되면 Nexus로 이동한 뒤
`Execution Recovery` modal 또는 central result를 표시한다.

표시 내용:

- workflow id
- target workspace
- 실행 시작 시각, 마지막 event 시각
- package별 상태
- running으로 남은 package 목록
- 완료된 package 목록
- 사용 가능한 action

Action:

| Action | 동작 |
| :--- | :--- |
| `Inspect` | 상태만 보고 닫는다. target workspace와 event log 경로를 보여준다. |
| `Retry interrupted` | `running`, `failed`, `blocked` package만 재시도 후보로 둔다. |
| `Mark interrupted` | `running` package를 `blocked` 또는 future `interrupted`로 바꾸고 사용자 결정을 요구한다. |
| `Abort execution` | 실행을 중단 상태로 고정하고 더 이상 자동 실행하지 않는다. |

### `/execute` 입력 시

현재 workflow가 stale execution이면 `/execute`는 즉시 새 실행을 시작하지 않는다.
먼저 recovery preflight를 띄운다.

안내 문구:

```text
Previous execution was interrupted. Review running packages before retrying.
```

사용자가 `Retry interrupted`를 명시적으로 선택한 경우에만 재실행한다.

### `/status`

`/status`는 workflow state와 별도로 execution recovery 상태를 표시한다.

예:

```text
Execution: interrupted
Target: /home/zaemi/workspace/hyper
Running packages at exit: WP-001
Next: /execute recovery 또는 /report
```

### `/report`

report에는 stale execution section을 추가한다.

- 마지막 known event
- incomplete packages
- raw response artifact path
- target workspace path
- retry/abort decision history

## 복구 정책

### 1. Reattach 금지

one-shot provider 호출은 request id와 raw response artifact를 남기지만, 앱 종료 후
live process와 event bus를 안정적으로 다시 연결하지 않는다. 따라서 resume 후 reattach를
시도하지 않는다.

### 2. Retry 후보 제한

재시도 대상은 다음 package만 포함한다.

- `running`으로 남았지만 completed event가 없는 package
- `failed` package
- `blocked` package 중 사용자가 retry를 선택한 package

`done` package는 기본적으로 재시도하지 않는다.

### 3. Target workspace guard

재시도 전 target workspace diff preview를 제공한다.

1차 구현은 git repo 여부에 따라 다르게 동작한다.

| target 상태 | preview |
| :--- | :--- |
| git repo | `git status --short` 요약 |
| 비 git repo | 최근 수정 파일 목록, expected_files 존재 여부 |

Trinity는 preview를 보여주되 자동 revert는 하지 않는다.

### 4. Fallback 실행 정책

기존 `ExecutionProtocol.dispatch_package()`는 `failed` 또는 `blocked` 결과면 fallback
agent를 시도한다. execution recovery에서는 이 정책을 더 보수적으로 바꾼다.

- 환경 검증 blocker: fallback하지 않고 `needs_review` 또는 `blocked`로 남긴다.
- provider timeout/error: fallback 허용
- 작업 산출물이 있으나 검증만 실패: fallback 전 사용자 확인
- fallback 시작 시 기존 attempt 완료/blocked event를 먼저 남긴다.

## 데이터/이벤트 설계

추가 event 초안:

| Event | 시점 | Payload |
| :--- | :--- | :--- |
| `execution_run_started` | `/execute` 시작 | `run_id`, `target_workspace`, `packages` |
| `execution_heartbeat` | event poll 또는 package event 처리 | `run_id`, `running_packages` |
| `execution_interrupted_detected` | startup/resume stale 감지 | `run_id`, `running_packages`, `last_event_at` |
| `execution_recovery_action` | 사용자가 action 선택 | `action`, `packages`, `target_workspace` |
| `work_package_retry_requested` | package 재시도 전 | `package_id`, `previous_status`, `agent` |

1차 구현에서는 `WorkflowPersistence.append_event()`와 `WorkflowSession` metadata를 같이
사용한다. event log만으로도 복구 판단이 가능하게 하되, UI snapshot은 session metadata를
우선 읽는다.

## 컴포넌트 변경안

| 컴포넌트 | 변경 |
| :--- | :--- |
| `WorkflowSession` | execution run metadata 추가 |
| `WorkflowEngine.begin_execution()` | `execution_run_started` 기록 |
| `WorkflowEngine.record_work_package_started()` | heartbeat/run id 갱신 |
| `WorkflowEngine.record_work_package_completed()` | package 완료와 heartbeat 갱신 |
| `WorkflowEngine.detect_interrupted_execution()` | persisted state 기준 stale 판단 |
| `TextualWorkflowController.resume_workflow()` | resume 후 interrupted outcome flag 전달 |
| `TrinityTextualApp._resume_textual_workflow()` | recovery modal/central result 표시 |
| `ExecutionMatrixScreen` | interrupted/retry 상태와 current executor 분리 표시 |
| `ExecutionProtocol` | blocker classification과 fallback confirmation hook 추가 |

## UI 설계

### Execution Recovery Modal

```text
Execution Recovery

Workflow: wf-...
Target: /home/zaemi/workspace/hyper
Last event: 21:23:37 work_package_started WP-001 claude

Package              Owner        Last executor     Status
WP-001               codex        claude fallback   running
WP-002               codex        -                 pending

[Inspect] [Retry interrupted] [Mark interrupted] [Abort execution]
```

### Execution Matrix 보강

현재 matrix는 `Assignee`만 있어 fallback executor와 owner가 섞인다. 다음 컬럼으로 분리한다.

| 컬럼 | 의미 |
| :--- | :--- |
| Assignee | WP owner |
| Executor | 현재 실행 agent 또는 fallback agent |
| Status | package status |
| Risk | local policy risk |

Fallback이면 `Executor`에 `claude (fallback)`처럼 표시한다.

## Command 계약

| Command | stale execution에서 동작 |
| :--- | :--- |
| `/resume` | 복원 후 recovery modal 표시 |
| `/status` | interrupted/running package 요약 |
| `/workflow` | execution run metadata 표시 |
| `/execute` | 바로 실행하지 않고 recovery preflight |
| `/report` | stale execution section 포함 |
| `/quit` | running worker가 있으면 강한 확인 문구와 중단 영향 표시 |

## 구현 단계

1. 설계 문서 작성
2. `WorkflowSession` execution run metadata 추가
3. `WorkflowEngine` stale execution detector 추가
4. execution run started/heartbeat/interrupted event 기록
5. Textual resume 후 recovery result/modal 표시
6. `/execute` stale guard와 retry action 추가
7. Execution Matrix owner/executor 분리
8. fallback blocker classification 1차 적용
9. report/status/workflow 문서와 UI 갱신
10. tests와 smoke 문서 추가

## 테스트 계획

| 테스트 | 검증 |
| :--- | :--- |
| `test_detect_interrupted_execution_when_running_without_worker` | persisted executing + running package 감지 |
| `test_resume_surfaces_execution_recovery` | `/resume` 후 recovery result 표시 |
| `test_execute_requires_recovery_choice_for_stale_execution` | stale 상태에서 즉시 재실행 금지 |
| `test_retry_interrupted_packages_excludes_done_packages` | done package 제외 |
| `test_status_reports_interrupted_execution` | `/status`에 interrupted 요약 |
| `test_execution_matrix_separates_owner_and_executor` | fallback executor 표시 |
| `test_environment_blocker_does_not_auto_fallback` | cargo/rustc 없음 같은 검증 blocker는 자동 fallback 금지 |

수동 smoke:

1. `/execute` 시작
2. 첫 WP `running` event 기록 확인
3. TUI 강제 종료
4. `uv run trinity` 재실행
5. `/resume latest`
6. recovery modal 표시 확인
7. `Inspect`, `Mark interrupted`, `Retry interrupted` 동작 확인

## 수용 기준

- 사용자가 execute 중 종료 후 resume했을 때 현재 실행이 계속 중인지 중단됐는지 명확히 보인다.
- stale 상태에서 `/execute`가 같은 WP를 조용히 중복 실행하지 않는다.
- 완료된 WP는 기본 재시도 대상에서 제외된다.
- target workspace에 이미 생성된 파일이 있다는 사실을 재시도 전에 보여준다.
- fallback executor가 owner와 분리되어 UI에 표시된다.
- provider process reattach를 지원하지 않는다는 한계가 문서와 UI 문구에 드러난다.

## 남은 결정

1. `WorkStatus.INTERRUPTED`를 새 enum으로 추가할지, 1차는 `blocked`와 metadata로 표현할지.
2. retry action을 `/execute retry` 같은 slash command로 노출할지, modal button으로만 둘지.
3. fallback confirmation을 모든 fallback에 요구할지, 검증 blocker에만 요구할지.
4. target workspace diff preview를 non-git workspace에서 어느 깊이까지 보여줄지.
