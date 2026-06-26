# Review Package Planning Flow 이관

- 브랜치: `refactor/review-package-planning-flow`
- 버전: `1.0.302` -> `1.0.303`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/review_flow.py`

## 배경

`WorkflowReviewFlow`는 리뷰 패키지 조회, 리뷰 결과 기록, repair loop 진입을 담당하지만 리뷰 패키지를 계획하고 기존 리뷰 승인 여부를 판정하는 helper는 아직 `WorkflowEngine`에 남아 있다.

이 구조에서는 실행 완료 후 리뷰를 시작하는 흐름과 리뷰 상태 판정이 engine private helper에 의존한다. review flow가 리뷰 패키지 생명주기를 더 온전히 소유하도록 계획/승인 판정 helper를 flow 내부로 옮긴다.

## 개선안

1. `_plan_review_packages`, `_planned_review_packages`, `_latest_review_is_approved`, `_review_package_is_approved`를 `WorkflowReviewFlow`로 이동한다.
2. `WorkflowReviewFlow` 내부 호출은 engine private helper 대신 flow helper를 직접 사용한다.
3. `WorkflowEngine`의 기존 private helper 이름은 호환 wrapper로 유지한다.
4. review planning 관련 focused 테스트와 full pytest로 동작 변경이 없음을 확인한다.

## 범위

- 리뷰 패키지 생성 정책 변경 없음
- reviewer/target agent 선정 변경 없음
- final review 생성 조건 변경 없음
- public CLI/TUI 동작 변경 없음

## 기대 효과

- 리뷰 패키지 생명주기 변경 시 `WorkflowEngine` 수정 필요성이 줄어든다.
- `WorkflowReviewFlow`가 review planning과 review result 상태 판정을 함께 소유한다.
- 이후 `WorkflowEngine`은 상태/영속성 facade로 더 얇게 유지된다.
