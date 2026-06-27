# Workflow Execution Intent Helper

## 목적

`WorkflowEngine`에 남아 있는 실행 의도 판단 로직을 helper 모듈로 분리해 엔진을 상태 전이 facade에 가깝게 유지한다.

## 범위

- `workflow.intent.requires_execution_for_deliberation()`을 추가한다.
- session goal, user prompt, consensus summary, task-level `requires_execution`을 조합하는 책임을 helper로 이동한다.
- `WorkflowEngine._requires_execution()`을 제거한다.
- 패치 버전을 `1.0.406`으로 올린다.

## 검증

- workflow engine focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.406`을 출력해야 한다.
