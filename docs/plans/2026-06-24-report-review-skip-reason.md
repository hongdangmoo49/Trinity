# Report Review Skip Reason

## 문제

Execution Matrix와 WP 상세 모달은 `skipped` 리뷰의 사유를 보여주지만,
Report/Markdown export의 work package routing 요약은 review status와 reviewer만 표시한다.

단일 provider 환경에서 peer review가 생략된 경우, 나중에 보고서를 읽는 사용자는
왜 review가 `skipped`인지 알기 어렵다.

## 설계

- `WorkPackageSnapshot.review_status == "skipped"`이고 `review_summary`가 있으면
  work package routing 요약에 사유를 추가한다.
- Markdown export는 `; reason ...` 형태로 덧붙인다.
- Textual Report 화면은 `; reason ...`을 escape해서 표시한다.
- approved/queued/reviewing 등 다른 review status에는 기존 출력을 유지한다.
- 데이터 모델과 snapshot projection은 변경하지 않는다.

## 기대 효과

- 보고서만 봐도 peer review 생략 이유를 추적할 수 있다.
- UI 상세 모달과 export 결과의 의미가 맞춰진다.
- provider 호출이나 workflow 비용은 증가하지 않는다.

## 테스트

- Markdown report가 skipped review reason을 포함한다.
- approved review report 문구는 기존 형태를 유지한다.
