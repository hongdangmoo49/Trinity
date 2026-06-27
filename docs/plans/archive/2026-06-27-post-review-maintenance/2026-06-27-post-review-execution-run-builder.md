# Post Review Execution Run Builder

## 목적

post-review supplemental work package queue 과정의 `execution_run` payload 구성 책임을 helper로 분리한다.

## 범위

- `post_review_assignment.py`에 supplemental execution run builder helper를 추가한다.
- 기존 run id 보존, 신규 run id 생성, state/kind/source/round/package/action item/target workspace 필드 설정을 helper에서 처리한다.
- `WorkflowPostReviewFlow`는 생성된 run payload를 session에 할당하고 state 전환만 수행한다.
- 기존 payload 필드와 값은 유지한다.
- 패치 버전을 `1.0.440`으로 올린다.

## 비목표

- supplemental WP 생성, owner selection, item status transition은 변경하지 않는다.
- final review auto replan에서 추가하는 `source=final_review_auto_replan` 보강 필드는 변경하지 않는다.
- execution retry/recovery run payload는 변경하지 않는다.

## 검증

- post-review execution run builder 단위 테스트를 통과해야 한다.
- 기존 post-review engine 회귀 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.440`을 출력해야 한다.
