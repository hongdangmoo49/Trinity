# Workflow Collection Flow 분리 설계

## 배경

`WorkflowEngine`은 대부분의 실행, 리뷰, 복구 흐름을 별도 flow로 위임하고 있지만, work package 조회와 subtask result upsert 같은 session collection 조작 helper가 아직 엔진 본문에 남아 있다. 이 helper들은 execution, review, post-review flow가 공통으로 사용하므로 위치를 명확히 하면 엔진을 더 facade에 가깝게 유지할 수 있다.

## 목표

- work package id 조회와 subtask result upsert를 `WorkflowCollectionFlow`로 분리한다.
- 기존 내부 wrapper인 `_work_package_by_id()`와 `_upsert_subtask_result()`는 유지한다.
- execution/review/post-review flow의 호출부 동작은 변경하지 않는다.

## 범위

- 신규 모듈: `src/trinity/workflow/collection_flow.py`
- `WorkflowEngine`에 `_collection_flow()` helper 추가
- `_work_package_by_id()`, `_upsert_subtask_result()`는 collection flow 위임으로 변경
- 패치 버전 업데이트

## 비목표

- work package 상태 전이 변경
- subtask result schema 변경
- execution/review/post-review flow 호출부 변경

## 검증

- focused: workflow engine, TUI session, Textual workflow controller, WP graph smoke
- full: 전체 pytest
- smoke: `trinity --version`
