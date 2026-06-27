# Post Review Supplemental Builder

## 목적

`WorkflowPostReviewFlow.queue_supplemental_work_packages()`에 남아 있는 supplemental `WorkPackage` 객체 생성 책임을 helper로 분리한다.

## 범위

- `post_review_assignment.py`에 supplemental work package builder helper를 추가한다.
- title, objective, scope, dependencies, acceptance criteria, origin metadata, supplemental round 설정을 helper에서 처리한다.
- `WorkflowPostReviewFlow`는 package id, owner, related ids, round를 계산하고 helper를 호출한다.
- 기존 generated `WorkPackage` 필드 값과 post-review item 상태 전환은 유지한다.
- 패치 버전을 `1.0.439`로 올린다.

## 비목표

- execution run payload 생성과 workflow state 전환은 변경하지 않는다.
- supplemental package id 생성 정책은 변경하지 않는다.
- post-review item selection, owner selection, auto replan 정책은 변경하지 않는다.

## 검증

- post-review supplemental builder 단위 테스트를 통과해야 한다.
- 기존 post-review engine 회귀 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.439`를 출력해야 한다.
