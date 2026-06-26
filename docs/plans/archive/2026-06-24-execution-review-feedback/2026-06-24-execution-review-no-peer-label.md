# 실행 매트릭스 peer review 생략 라벨 개선

작성일: 2026-06-24

## 배경

실행 매트릭스는 review cell에 `queued`, `reviewing`, `approved`, `needs 2nd` 같은 짧은 상태를 표시한다.
provider가 1개뿐이라 non-owner peer reviewer가 없을 때는 snapshot이 `review_status=skipped`와
skip reason을 제공하지만, 행에는 `skip` 또는 `생략`만 표시된다.

이 표시는 너무 작아서 사용자가 “리뷰가 성공적으로 필요 없어진 것인지” 또는 “검토할 peer가 없어서 생략된 것인지”
구분하기 어렵다.

## 목표

- no-peer 사유로 생략된 review는 실행 매트릭스에서 명시적으로 `no peer` 또는 `peer 없음`으로 표시한다.
- 일반적인 `skipped` 상태는 기존 `skip` 또는 `생략` 표시를 유지한다.
- review planning, retry, second review 정책은 변경하지 않는다.
- WP 상세 모달과 report에 보존된 skip reason은 그대로 유지한다.

## 판별 기준

다음 조건을 만족하면 no-peer 생략으로 본다.

- `review_status == skipped`
- `reviewer_agent`가 비어 있음
- `review_summary` 또는 `review_skipped_reason` 계열 텍스트에 `no non-owner peer reviewer`, `no peer reviewer`,
  `only ... active` 중 하나가 포함됨

알 수 없는 skip reason은 기존처럼 `skip` 또는 `생략`으로 표시한다.

## 테스트

- 영어 실행 매트릭스 review label에서 no-peer skip은 `no peer`로 표시된다.
- 한국어 실행 매트릭스 review label에서 no-peer skip은 `peer 없음`으로 표시된다.
- generic skipped review는 기존 `skip` 또는 `생략`을 유지한다.
