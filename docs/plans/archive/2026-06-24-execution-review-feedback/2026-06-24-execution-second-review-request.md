# Execution Second Review Request

## 문제

Execution Matrix는 `needs_second_review` 상태를 표시하고 row detail button도 `2nd Review`로
바꿨지만, 사용자가 실행 페이지에서 바로 pending 2차 리뷰를 요청할 수는 없다.

현재 실제 리뷰 실행 경로는 `TextualWorkflowController.request_review(("wp", package_id))`
로 이미 존재한다. 따라서 row action에서 이 경로를 호출하면 사용자가 slash command를 기억하지
않아도 2차 리뷰를 시작할 수 있다.

## 설계

- `needs_second_review` WP row에 별도 compact action button을 추가한다.
  - 영어: `Run 2nd`
  - 한국어: `2차실행`
- 기존 detail button은 계속 WP 상세 모달을 연다.
- 새 버튼은 `ExecutionMatrixScreen.ReviewRequested` message를 발생시킨다.
- `TrinityTextualApp`은 해당 message를 받아 `workflow_controller.request_review(("wp", package_id))`
  를 호출한다.
- controller가 target workspace 필요, pending review 없음, running 상태 등을 판단하는 기존 정책을 재사용한다.

## 기대 효과

- `needs_second_review` 상태에서 사용자가 실행 페이지에서 바로 다음 행동을 수행할 수 있다.
- slash command를 기억하지 않아도 pending escalation review를 시작할 수 있다.
- 기존 review planner/controller 정책을 재사용하므로 workflow semantics 중복을 피한다.

## 테스트

- `needs_second_review` row에 `Run 2nd` 버튼이 표시된다.
- 버튼을 누르면 app이 controller의 `request_review(("wp", package_id))`를 호출한다.
- normal row에는 2차 리뷰 실행 버튼이 표시되지 않는다.
