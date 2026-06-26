# Review Repair Flow Helper 이관

- 브랜치: `refactor/review-repair-flow-helpers`
- 버전: `1.0.301` -> `1.0.302`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/review_flow.py`

## 배경

`WorkflowReviewFlow`는 review package 기록과 repair loop를 담당하지만, repair metadata 복구, repair signature 생성, required change 병합, target agent 정규화 같은 세부 helper는 아직 `WorkflowEngine`에 남아 있다.

이 구조에서는 review repair 정책을 수정할 때 flow와 engine을 함께 수정해야 하므로 `WorkflowEngine`이 다시 도메인 로직을 많이 알게 된다. post-review helper 이관과 같은 방향으로 review repair helper도 flow 내부로 옮겨 엔진을 더 얇은 facade로 유지한다.

## 개선안

1. review repair metadata/signature/change merge helper를 `WorkflowReviewFlow`로 이동한다.
2. `WorkflowReviewFlow` 내부 호출은 engine private helper 대신 flow helper를 직접 사용한다.
3. `WorkflowEngine`의 기존 private helper 이름은 호환 wrapper로 유지한다.
4. review repair 관련 focused 테스트와 full pytest로 동작 변경이 없음을 확인한다.

## 범위

- review repair retry 대상 선정 변경 없음
- duplicate/max-attempt guard 동작 변경 없음
- legacy repair metadata 복구 동작 변경 없음
- public CLI/TUI 동작 변경 없음

## 기대 효과

- review repair 로직 변경 시 `WorkflowEngine` 수정 필요성이 줄어든다.
- `WorkflowReviewFlow`가 review repair 도메인 로직을 더 온전히 소유한다.
- 이후 `WorkflowEngine`을 상태/영속성 facade로 더 얇게 만드는 후속 작업이 쉬워진다.
