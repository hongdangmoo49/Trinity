# Post-Review Flow Helper 이관

- 브랜치: `refactor/post-review-flow-helpers`
- 버전: `1.0.300` -> `1.0.301`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/post_review_flow.py`

## 배경

`WorkflowPostReviewFlow`는 별도 모듈로 분리되었지만, action item 생성/선택, supplemental work package id/owner 계산, follow-up 기록 같은 post-review 세부 helper는 아직 `WorkflowEngine` private method로 남아 있다.

이 상태에서는 post-review flow 파일은 분리되었지만 실제 도메인 로직 변경 시 `WorkflowEngine`까지 함께 수정해야 한다. 엔진을 더 얇은 facade로 유지하려면 post-review 세부 helper를 flow 내부로 옮기는 것이 다음 단계다.

## 개선안

1. post-review item parsing/selection/creation helper를 `WorkflowPostReviewFlow`로 이동한다.
2. supplemental work package id/owner/objective helper를 `WorkflowPostReviewFlow`로 이동한다.
3. follow-up request 기록을 `WorkflowPostReviewFlow` 내부에서 처리한다.
4. `WorkflowEngine`은 기존 private method 호출 호환이 필요한 부분만 얇게 flow에 위임한다.

## 범위

- post-review action item 추출 결과 변경 없음
- `/improve` selector 동작 변경 없음
- supplemental work package 생성 규칙 변경 없음
- public CLI/TUI 동작 변경 없음

## 기대 효과

- post-review 로직 변경 시 `WorkflowEngine` 수정 필요성이 줄어든다.
- `WorkflowEngine`은 session state facade와 persistence facade 역할에 더 가까워진다.
- post-review flow 단위 테스트를 확장하기 쉬워진다.
