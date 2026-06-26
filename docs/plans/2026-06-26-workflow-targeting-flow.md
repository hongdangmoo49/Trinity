# Workflow Targeting Flow 분리 설계

## 배경

workflow 시작, blueprint continuation, 질문 답변 continuation, provider error retry gate는 모두 "어떤 agent에게 다시 보낼지"와 "어떤 model override를 허용할지"를 같은 규칙으로 계산한다. 이 규칙은 순수 함수에 가깝지만 `WorkflowEngine` 본문에 남아 있어 입력/라이프사이클/질문/retry 흐름이 엔진 static helper에 계속 의존하고 있다.

## 목표

- target agent 선택과 model override 정규화를 `WorkflowTargetingFlow`로 분리한다.
- 기존 `WorkflowEngine._effective_target_agents()`와 `_normalized_model_overrides()` wrapper는 유지한다.
- provider error gate와 lifecycle/question flow의 동작은 그대로 유지한다.
- 이후 provider 수가 1개 또는 2개인 UI/UX 정책을 보강할 때 targeting 규칙의 위치를 명확히 한다.

## 범위

- 신규 모듈: `src/trinity/workflow/targeting_flow.py`
- `WorkflowEngine` static wrapper가 새 helper로 위임
- 패치 버전 업데이트

## 비목표

- agent 선택 정책 변경
- model override UI 변경
- provider error retry 정책 변경

## 검증

- focused: workflow engine, TUI session, Textual workflow controller, provider error gate
- full: 전체 pytest
- smoke: `trinity --version`
