# Post Review Owner Helper

## 목적

post-review supplemental work package 생성 중 owner agent를 고르는 정책을 별도 helper로 분리한다.

## 범위

- `post_review_assignment.py` 모듈을 추가한다.
- suggested owner, related work package owner, active agents round-robin, fallback 순서를 helper에서 처리한다.
- `WorkflowPostReviewFlow`는 related package owner 조회 callback만 제공한다.
- 기존 owner 배정 순서와 fallback 값은 유지한다.
- 패치 버전을 `1.0.438`로 올린다.

## 비목표

- supplemental WP 생성 구조, execution run payload, post-review item 상태 전환은 변경하지 않는다.
- active agent routing 정책은 변경하지 않는다.
- post-review selector나 auto replan 정책은 변경하지 않는다.

## 검증

- post-review owner helper 단위 테스트를 통과해야 한다.
- 기존 post-review engine 회귀 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.438`을 출력해야 한다.
