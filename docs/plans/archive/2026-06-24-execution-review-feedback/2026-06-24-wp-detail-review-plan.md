# WP Detail Review Plan

## 문제

WP 상세 모달은 실행 결과와 리뷰 결과를 보여주지만, 선택형 리뷰 정책 이후 중요해진
"리뷰가 계획됐는지", "몇 명이 리뷰하는지", "2차 리뷰가 필요한지", "왜 생략됐는지"를
별도 계획 섹션으로 분리하지 않는다.

그 결과 `Review` 섹션의 summary를 읽기 전까지는 skipped 리뷰와 approved 리뷰,
primary review와 escalation 대기를 빠르게 구분하기 어렵다.

## 설계

- `WorkPackageSnapshot`에 이미 있는 필드만 사용한다.
- `Result`와 `Review` 사이에 `Review Plan` 섹션을 추가한다.
- review 정보가 전혀 없으면 섹션을 생략한다.
- 섹션에는 다음 정보를 표시한다.
  - review status
  - reviewer list
  - reviewer count
  - skipped reason
  - second review pending hint
- 기존 `Review` 섹션은 결과/summary 영역으로 유지한다.

## 기대 효과

- provider 1개 환경에서 peer review 생략 사유를 더 빨리 확인할 수 있다.
- provider 2개/3개 환경에서 reviewer 수를 바로 확인할 수 있다.
- escalation 상태인 `needs_second_review`가 상세 모달에서 더 명확하게 보인다.
- schema 변경 없이 UI projection만 보강한다.

## 테스트

- Review Plan 섹션이 Result와 Review 사이에 배치된다.
- reviewer가 여러 명이면 reviewer count가 표시된다.
- skipped review summary는 Review Plan에도 생략 사유로 표시된다.
- `needs_second_review` 상태는 2차 리뷰 대기 안내를 표시한다.
- 한국어 UI에서는 Review Plan 라벨이 한국어로 표시된다.
