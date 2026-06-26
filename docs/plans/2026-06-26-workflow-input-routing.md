# Workflow Input Routing Helper 분리

- 브랜치: `refactor/workflow-input-routing`
- 버전: `1.0.307` -> `1.0.308`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/input_flow.py`

## 배경

`WorkflowEngine.handle_user_input`은 사용자의 일반 입력을 현재 workflow state에 맞춰 질문 답변, post-review 입력, 기존 blueprint continuation, 신규 workflow 시작으로 라우팅한다.

이 판단은 workflow 상태 전이 구현보다 앞단의 input routing 정책에 가깝다. 별도 helper로 분리하면 engine은 각 상태별 public operation을 제공하는 facade로 남고, 이후 start/continue flow 분리도 더 쉬워진다.

## 개선안

1. `handle_user_input` 라우팅 판단을 `WorkflowInputFlow`로 이동한다.
2. 기존 blueprint를 이어갈 수 있는지 판단하는 `_can_continue_existing_blueprint`도 input flow로 이동한다.
3. `WorkflowEngine`의 기존 public/private 메서드는 호환 wrapper로 유지한다.
4. 라우팅 대상인 질문 답변, post-review 입력, blueprint continuation, 신규 workflow 시작 동작은 변경하지 않는다.

## 범위

- workflow state별 라우팅 순서 변경 없음
- target agent/model override 전달 방식 변경 없음
- public CLI/TUI 동작 변경 없음
- persistence 이벤트 변경 없음

## 기대 효과

- input routing 정책 변경 시 수정 위치가 명확해진다.
- `WorkflowEngine`에서 사용자 입력 분기 로직을 제거한다.
- 이후 start/continue/execution enable flow를 별도 helper로 분리하기 쉬워진다.
