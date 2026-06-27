# Review Repair Metadata Helper

## 목적

`WorkflowReviewFlow.reconcile_review_repair_metadata()`에 포함된 review repair 이벤트 메타데이터 파싱 책임을 별도 helper 모듈로 분리한다.

## 범위

- `review_repair_metadata.py` 모듈을 추가해 repair request 이벤트 목록을 package별 메타데이터로 축약한다.
- `WorkflowReviewFlow`는 persistence에서 이벤트를 읽고 helper에 위임하는 facade만 유지한다.
- attempt count, repair signature, review package id 복원 규칙은 기존 동작을 유지한다.
- 새 helper 단위 테스트를 추가한다.
- 패치 버전을 `1.0.436`으로 올린다.

## 비목표

- repair loop 차단 정책, max attempts 기준, workflow state 전환은 변경하지 않는다.
- `work_package_repair_requested` 이벤트 payload schema는 변경하지 않는다.
- review repair 실행/재시도 UX는 변경하지 않는다.

## 검증

- review repair metadata helper 단위 테스트를 통과해야 한다.
- 기존 review repair metadata reconciliation 회귀 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.436`을 출력해야 한다.
