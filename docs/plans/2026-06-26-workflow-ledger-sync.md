# Workflow Ledger Sync Helper 분리

- 브랜치: `refactor/workflow-ledger-sync`
- 버전: `1.0.303` -> `1.0.304`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/ledger_sync.py`

## 배경

`WorkflowEngine`은 workflow 상태 전이를 조율하는 역할을 맡고 있지만, 현재 `shared.md` 렌더링과 기존 자유 작성 섹션 보존 로직까지 직접 포함하고 있다.

이 로직은 workflow 실행/리뷰 상태 전이와 독립적이며, shared ledger 파일을 읽고 다시 쓰는 I/O 경계에 가깝다. 별도 helper로 분리하면 engine이 도메인 orchestration facade에 더 가까워지고 ledger 동기화 변경 범위도 명확해진다.

## 개선안

1. `WorkflowLedgerSync` helper를 추가해 `render_shared_ledger`, `sync_shared_ledger`, preserved section parsing을 소유하게 한다.
2. `WorkflowEngine`의 기존 public/private 메서드는 호환 wrapper로 유지한다.
3. ledger sync 관련 테스트와 full pytest로 동작 변경이 없음을 확인한다.

## 범위

- `shared.md` 출력 형식 변경 없음
- 보존되는 자유 작성 섹션 변경 없음
- public CLI/TUI 동작 변경 없음
- persistence 이벤트 변경 없음

## 기대 효과

- `WorkflowEngine`에서 파일 렌더/동기화 책임을 제거한다.
- ledger 포맷 변경 시 수정 위치가 명확해진다.
- 이후 engine을 얇은 workflow facade로 유지하기 쉬워진다.
