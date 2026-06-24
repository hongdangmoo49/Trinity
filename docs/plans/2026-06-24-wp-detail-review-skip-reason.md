# WP Detail Review Skip Reason

## 문제

선택형 리뷰 정책이 들어오면서 provider가 1개뿐이거나 peer reviewer가 없을 때
work package 리뷰가 `skipped`로 표시된다. Execution Matrix row와 Review 섹션에는
`review_summary`가 남지만, WP 상세 모달의 `Action Context`는 여전히
"Peer review was skipped" 수준의 일반 문구만 보여준다.

이 상태에서는 사용자가 "검토가 승인된 것인지", "정책상 생략된 것인지", "왜 생략됐는지"를
상세 화면 상단에서 바로 판단하기 어렵다.

## 설계

- 데이터 모델은 변경하지 않는다.
- `WorkPackageSnapshot.review_status == "skipped"`이고 `review_summary`가 있으면
  `Action Context`에 생략 사유로 표시한다.
- `review_summary`가 없으면 기존 낮은 신뢰도 안내 문구를 유지한다.
- 한국어 UI에서는 `리뷰 생략 사유` 라벨을 사용한다.
- Review 섹션의 원래 summary 표시는 유지해 상세 기록을 잃지 않는다.

## 기대 효과

- 단일 provider 환경에서 peer review 부재가 더 명확하게 보인다.
- skipped 상태가 approved처럼 오해되는 위험을 줄인다.
- 기존 snapshot/projection 경로를 그대로 사용하므로 provider 호출 비용은 늘지 않는다.

## 테스트

- 영어 모달에서 skipped review summary가 Action Context의 review skip reason으로 표시된다.
- 한국어 모달에서 같은 사유가 `리뷰 생략 사유` 라벨로 표시된다.
- summary가 없는 skipped review는 기존 fallback 문구를 유지한다.
