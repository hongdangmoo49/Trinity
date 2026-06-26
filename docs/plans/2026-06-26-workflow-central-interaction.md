# Workflow Central Interaction Helper 분리

- 브랜치: `refactor/workflow-central-interaction`
- 버전: `1.0.304` -> `1.0.305`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/central_flow.py`

## 배경

`WorkflowEngine`은 workflow 상태 전이와 flow 위임을 담당해야 하지만, 중앙 에이전트 응답 기록, blueprint markdown 본문 생성, structured open question 반영, continuation prompt 생성 로직까지 직접 포함하고 있다.

이 로직들은 중앙 에이전트와 사용자의 상호작용을 다루는 한 묶음이다. 별도 helper로 분리하면 `WorkflowEngine`은 상태 전이 orchestration에 집중하고, 중앙 interaction 정책 변경 범위가 명확해진다.

## 개선안

1. 중앙 conversation 기록과 blueprint body 생성 helper를 `WorkflowCentralFlow`로 이동한다.
2. structured question 반영과 question id 충돌 회피 helper를 `WorkflowCentralFlow`로 이동한다.
3. decision/blueprint continuation prompt 생성 helper를 `WorkflowCentralFlow`로 이동한다.
4. `WorkflowEngine`의 기존 private helper 이름은 호환 wrapper로 유지한다.

## 범위

- deliberation consensus 처리 조건 변경 없음
- open question 중복 판정 변경 없음
- continuation prompt 문구 변경 없음
- public CLI/TUI 동작 변경 없음

## 기대 효과

- 중앙 에이전트 interaction 정책 변경 시 수정 위치가 명확해진다.
- `WorkflowEngine`에서 prompt 생성/대화 기록 세부 구현을 제거한다.
- 이후 engine을 얇은 facade로 유지하기 쉬워진다.
