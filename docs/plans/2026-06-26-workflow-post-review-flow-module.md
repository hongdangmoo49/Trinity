# Workflow Post-Review Flow 모듈 분리

- 브랜치: `refactor/workflow-post-review-flow-module`
- 버전: `1.0.299` -> `1.0.300`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/post_review_flow.py`, `src/trinity/workflow/execution_review_flow.py`

## 배경

execution flow와 review flow가 각각 독립 모듈로 분리되면서 `execution_review_flow.py`에는 post-review flow와 legacy re-export만 남았다. 이제 post-review flow까지 별도 모듈로 이동하면 execution/review/post-review 세 축이 파일 단위로 분리되고, 기존 통합 파일은 호환 shim 역할만 수행할 수 있다.

post-review flow는 final review 이후 action item 추출, 사용자 follow-up 선택, supplemental work package 생성, auto replan queueing을 담당하므로 review result 기록/repair loop와 독립적으로 변경되는 경우가 많다.

## 개선안

1. `WorkflowPostReviewFlow`를 `post_review_flow.py`로 이동한다.
2. `WorkflowEngine`은 post-review flow를 새 모듈에서 직접 import한다.
3. 기존 `execution_review_flow`는 execution/review/post-review flow를 re-export하는 legacy shim으로 축소한다.
4. post-review flow import compatibility 테스트를 추가하고, workflow/review/execution focused 테스트와 full pytest로 회귀를 확인한다.

## 범위

- post-review action item 추출/선택 로직 변경 없음
- supplemental work package 생성 로직 변경 없음
- final review auto replan 동작 변경 없음
- public CLI/TUI 동작 변경 없음

## 기대 효과

- execution/review/post-review flow가 모두 독립 모듈이 된다.
- 후속 flow 내부 리팩터링 시 파일 충돌과 review 부담이 줄어든다.
- `execution_review_flow.py`는 기존 import 경로 호환성만 담당하는 얇은 shim으로 남는다.
