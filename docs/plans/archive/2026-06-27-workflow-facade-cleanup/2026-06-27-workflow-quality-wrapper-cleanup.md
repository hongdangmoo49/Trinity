# Workflow Quality Wrapper Cleanup

## 목적

`WorkflowEngine`을 얇은 facade로 유지하기 위해 실행/리뷰 품질 기록용 forwarding wrapper를 제거한다.

## 범위

- `WorkflowExecutionFlow`는 실행 결과 기록 시 `WorkflowQualityFlow.record_execution_quality()`를 직접 호출한다.
- `WorkflowReviewFlow`는 리뷰 결과 기록 시 `WorkflowQualityFlow.record_review_quality()`를 직접 호출한다.
- `WorkflowEngine._record_execution_quality()`와 `WorkflowEngine._record_review_quality()`를 제거한다.
- 패치 버전을 `1.0.404`로 올린다.

## 검증

- focused workflow/quality 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.404`를 출력해야 한다.
