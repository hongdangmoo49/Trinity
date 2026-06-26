# Workflow Workspace Flow 분리 설계

## 배경

`WorkflowEngine`은 workflow 상태 전이, 입력 라우팅, 실행, 리뷰, ledger 동기화까지 여러 책임을 facade 형태로 위임하도록 계속 얇아지고 있다. 아직 `target_workspace` 선택/해제 로직은 엔진 본문에 남아 있어 Nexus 실행 UX와 실행 workspace 안정성 보강을 이어갈 때 변경 지점이 다시 엔진으로 모이는 문제가 있다.

## 목표

- `target_workspace` 선택/해제 상태 변경을 `WorkflowWorkspaceFlow`로 분리한다.
- 기존 public API인 `WorkflowEngine.set_target_workspace()`와 `clear_target_workspace()`는 유지한다.
- session 저장 이벤트 이름과 payload는 그대로 유지해 기존 UI, 테스트, ledger 흐름을 깨지 않는다.
- 이후 workspace preflight, 실행 경로 검증, provider launch cwd 동기화 개선을 같은 축에서 이어갈 수 있게 한다.

## 범위

- 신규 모듈: `src/trinity/workflow/workspace_flow.py`
- `WorkflowEngine`에 `_workspace_flow()` helper 추가
- `set_target_workspace()`, `clear_target_workspace()`는 flow 위임 wrapper로 변경
- 패치 버전 업데이트

## 비목표

- target workspace carry-over 정책 변경
- Nexus workspace picker UI 변경
- 실행 protocol의 target workspace guard 변경

## 검증

- focused: workflow engine, TUI session, Textual workflow controller, workspace picker, WP graph smoke
- full: 전체 pytest
- smoke: `trinity --version`
