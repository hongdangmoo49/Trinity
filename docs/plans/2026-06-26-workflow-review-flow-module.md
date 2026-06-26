# Workflow Review Flow 모듈 분리

- 브랜치: `refactor/workflow-review-flow-module`
- 버전: `1.0.298` -> `1.0.299`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/review_flow.py`, `src/trinity/workflow/execution_review_flow.py`

## 배경

execution flow가 `execution_flow.py`로 분리되면서 `execution_review_flow.py`에는 review flow와 post-review flow만 남았다. 하지만 review repair, review result recording, final review state transition은 post-review follow-up 생성/선택과 변경 이유가 다르다.

후속 post-review flow 분리를 더 작고 안전하게 만들려면 `WorkflowReviewFlow`를 먼저 독립 모듈로 이동해 review 단계의 책임을 별도 파일로 고정하는 것이 좋다.

## 개선안

1. `WorkflowReviewFlow`를 `review_flow.py`로 이동한다.
2. `WorkflowEngine`은 review flow를 새 모듈에서 직접 import한다.
3. 기존 `execution_review_flow.WorkflowReviewFlow` import 경로는 re-export로 유지한다.
4. review flow import compatibility 테스트를 추가하고, 기존 workflow/review focused 테스트로 회귀를 확인한다.

## 범위

- review package 선택/기록 로직 변경 없음
- review repair loop guard 동작 변경 없음
- final review -> post-review 전이 변경 없음
- public CLI/TUI 동작 변경 없음

## 기대 효과

- execution, review, post-review가 파일 단위로 한 단계 더 분리된다.
- review repair 변경과 post-review follow-up 변경이 서로 충돌할 가능성이 낮아진다.
- `WorkflowEngine`은 flow facade 역할을 유지하면서 모듈 경계가 더 명확해진다.
