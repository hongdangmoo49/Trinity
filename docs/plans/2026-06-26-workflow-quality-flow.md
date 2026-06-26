# Workflow Quality Flow 분리 설계

## 배경

agent quality signal은 실행 결과와 리뷰 결과 양쪽에서 기록되고, Nexus snapshot과 provider inspector에서 후속 라우팅 힌트로 사용된다. 현재 품질 기록은 `execution_flow.py`와 `review_flow.py`에 각각 흩어져 있고, 요약은 `WorkflowEngine`에 남아 있어 품질 정책을 조정할 때 변경 지점이 세 군데로 나뉜다.

## 목표

- 품질 요약과 실행/리뷰 품질 신호 기록을 `WorkflowQualityFlow`로 모은다.
- `WorkflowEngine.quality_summaries()`, `_record_execution_quality()`, `_record_review_quality()` public/internal wrapper는 유지한다.
- `execution_flow.py`와 `review_flow.py`는 ledger 구현을 직접 알지 않게 한다.
- 기존 event 이름과 payload는 유지해 UI snapshot과 provider inspector 표시를 깨지 않는다.

## 범위

- 신규 모듈: `src/trinity/workflow/quality_flow.py`
- `WorkflowEngine`에 `_quality_flow()` helper 추가
- 실행/리뷰 flow의 `QualityLedger` 직접 import 및 기록 메서드 제거
- 패치 버전 업데이트

## 비목표

- 품질 점수 계산식 변경
- provider routing 정책 변경
- Nexus provider inspector UI 변경

## 검증

- focused: quality ledger, workflow engine, textual snapshot, TUI session
- full: 전체 pytest
- smoke: `trinity --version`
