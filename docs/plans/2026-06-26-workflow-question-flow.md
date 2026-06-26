# Workflow Question Flow 분리

- 브랜치: `refactor/workflow-question-flow`
- 버전: `1.0.306` -> `1.0.307`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/question_flow.py`

## 배경

`WorkflowEngine`은 사용자 입력을 workflow 상태에 맞춰 라우팅하지만, open question 추가, 질문 selector 해석, 답변 기록/교체, 선택지 답변 처리까지 직접 포함하고 있다.

질문/결정 흐름은 중앙 deliberation을 계속하기 위한 interaction layer이며, 실행/리뷰 상태 전이와는 독립적인 정책이다. 별도 helper로 분리하면 질문 처리 변경 범위가 명확해지고 engine은 더 얇은 facade로 남는다.

## 개선안

1. `answer_pending_question`, `answer_question`, `answer_question_option`, `resolve_question`, `add_open_question`을 `WorkflowQuestionFlow`로 이동한다.
2. question decision 조회와 decision id 생성 helper를 `WorkflowQuestionFlow`로 이동한다.
3. `WorkflowEngine`의 기존 public/private 메서드는 호환 wrapper로 유지한다.
4. provider error gate 답변 흐름과 일반 decision continuation 흐름은 기존 동작을 유지한다.

## 범위

- question selector 규칙 변경 없음
- decision event payload 변경 없음
- provider error gate answer 처리 변경 없음
- public CLI/TUI 동작 변경 없음

## 기대 효과

- 질문/결정 interaction 정책 변경 시 수정 위치가 명확해진다.
- `WorkflowEngine`의 사용자 입력 처리 책임이 더 작아진다.
- 이후 input routing flow를 별도 분리하기 쉬워진다.
