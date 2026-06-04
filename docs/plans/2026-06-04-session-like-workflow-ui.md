# 세션형 Workflow UI 재설계

## 문제

현재 TUI는 일반 텍스트 입력을 대부분 새 workflow 시작으로 해석한다. 그래서 설계 합의 후 `blueprint_ready` 상태에서 사용자가 "위 설계를 구현해줘"처럼 자연스럽게 이어 말하면, 기존 blueprint를 실행하거나 보완하지 않고 새 workflow를 시작할 수 있다.

또한 중앙 synthesis가 사용자 질문을 만들더라도 사용자는 `/questions`와 `/answer` 명령을 알아야 한다. Codex, Claude, Gemini 같은 세션형 도구를 기대하는 사용자는 질문을 보고 선택하거나 직접 답하는 흐름을 원한다.

## 목표

- `needs_user_decision` 상태에서 일반 텍스트를 다음 open question의 직접 답변으로 처리한다.
- `blueprint_ready` 상태에서 일반 텍스트가 기존 workflow 문맥을 잃지 않게 한다.
- 중앙 synthesis 질문은 자동으로 질문 패널과 선택 UI를 표시한다.
- 현재 blueprint를 명시 실행하는 `/execute` 명령을 제공한다.
- 실행 전용 work package는 `requires_execution=true`로 재생성해서 `planning only` 패키지와 구분한다.

## 동작 설계

1. 새 goal 입력
   - `idle`, `failed`, `done` 등 일반 상태에서는 기존처럼 새 workflow를 시작한다.

2. 사용자 질문 대기
   - `needs_user_decision` 상태에서 일반 텍스트 입력은 `answer_pending_question()`으로 라우팅한다.
   - 옵션 질문은 기존 `/questions --select` 또는 자동 선택 UI로 처리한다.
   - 답변 후 남은 질문이 없으면 continuation prompt로 기존 workflow를 계속 deliberation한다.

3. Blueprint 준비 상태
   - TTY 환경에서 일반 텍스트 입력 시 선택지를 보여준다.
     - 현재 설계 실행
     - 현재 설계 수정
     - 새 workflow 시작
   - 비TTY 환경에서는 기존 workflow를 보존하기 위해 "현재 설계 수정"을 기본값으로 둔다.
   - 명시 실행은 `/execute [지시문]`로 처리한다.

4. 직접 실행
   - 현재 blueprint가 있으면 work package를 `requires_execution=true`로 재생성한다.
   - 사용자가 입력한 실행 지시문은 decision ledger에 남겨 execution prompt에 포함한다.
   - 새 orchestrator로 실행만 시작해도 agent wrapper가 start되지 않는 문제가 없도록 `execute_work_packages()`에서 agent start를 보장한다.

## 범위

이번 변경은 TUI와 workflow 상태 전환만 다룬다. Provider one-shot 호출 구조, synthesis 알고리즘, blueprint 파서 품질 개선은 별도 작업으로 둔다.
