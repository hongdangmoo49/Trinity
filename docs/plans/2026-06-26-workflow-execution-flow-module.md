# Workflow Execution Flow 모듈 분리

- 브랜치: `refactor/workflow-execution-flow-module`
- 버전: `1.0.297` -> `1.0.298`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/execution_flow.py`, `src/trinity/workflow/execution_review_flow.py`

## 배경

`WorkflowEngine`은 이미 execution, review, post-review 책임을 `WorkflowExecutionFlow`, `WorkflowReviewFlow`, `WorkflowPostReviewFlow`로 위임하고 있다. 하지만 세 flow 클래스가 모두 `execution_review_flow.py` 한 파일에 모여 있어, execution scheduling/result recording 변경과 review repair/post-review 변경이 같은 파일에서 충돌하기 쉽다.

후속 작업에서 review flow와 post-review flow를 더 세밀하게 분리하려면 먼저 execution flow를 독립 모듈로 떼어, 파일 단위 책임과 테스트 타깃을 명확히 하는 것이 좋다.

## 개선안

1. `WorkflowExecutionFlow`를 `execution_flow.py`로 이동한다.
2. `WorkflowEngine`은 execution flow를 새 모듈에서 직접 import한다.
3. 기존 `execution_review_flow.WorkflowExecutionFlow` import 경로는 re-export로 유지해 외부/테스트 호환성을 보존한다.
4. execution behavior는 변경하지 않고 focused/full pytest로 회귀를 확인한다.

## 범위

- 실행 스케줄링 로직 변경 없음
- execution result 기록/상태 전이 변경 없음
- review/post-review 동작 변경 없음
- public CLI/TUI 동작 변경 없음

## 기대 효과

- execution flow 변경이 review/post-review 변경과 파일 단위로 분리된다.
- 이후 review flow와 post-review flow를 순서대로 분리할 때 diff 충돌 가능성이 낮아진다.
- `WorkflowEngine`은 flow facade 역할을 유지하면서 import 경계가 더 분명해진다.
