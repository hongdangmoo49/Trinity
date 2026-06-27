# Post Review Selection Helper

## 목적

`WorkflowPostReviewFlow`에 남아 있는 post-review action item 선택자 판정 로직을 별도 helper 모듈로 분리한다.

## 범위

- `post_review_selection.py` 모듈을 추가한다.
- `/improve all`, `/improve high`, `/improve critical`, `/improve AI-001` 계열 선택자를 helper 함수로 처리한다.
- `WorkflowPostReviewFlow`는 post-review item 목록을 helper에 넘기는 facade만 유지한다.
- selector 판정과 사용자 자유 입력 구분 규칙은 기존 동작을 유지한다.
- 패치 버전을 `1.0.437`로 올린다.

## 비목표

- post-review action item 생성, accept, supplemental WP 생성 정책은 변경하지 않는다.
- `/improve` UX 문구나 Textual presenter는 변경하지 않는다.
- final review auto replan 정책은 변경하지 않는다.

## 검증

- post-review selection helper 단위 테스트를 통과해야 한다.
- 기존 post-review engine 회귀 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.437`을 출력해야 한다.
