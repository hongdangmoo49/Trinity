# Central Agent Blueprint Response and Next Action UX

## 목적

Nexus 화면에서 중앙 에이전트가 설계한 workflow가 짧은 요약과 WP 목록으로만 보이면 사용자는 왜 해당 WP가 만들어졌는지 확인하기 어렵다. 중앙 에이전트가 만든 설계 본문을 함께 보여주고, blueprint가 준비된 직후에는 사용자가 다음 행동을 바로 선택할 수 있어야 한다.

## 현재 문제

현재 중앙 패널은 `WorkflowNexusSnapshot.synthesis.summary`와 WP 목록을 중심으로 렌더링한다. `WorkflowSession.blueprint`에는 title, summary, architecture, data_flow, dependencies, risks, acceptance_criteria, open_questions, work_packages가 남아 있지만, 화면에는 대부분 축약되어 나온다.

그 결과 사용자는 다음과 같은 화면만 보게 된다.

- Workflow 상태와 round
- 짧은 Synthesis 문장
- Work Packages 목록

중앙 에이전트가 어떤 근거로 설계했는지, 어떤 아키텍처와 검증 기준을 잡았는지, 어떤 위험을 봤는지 한눈에 보기 어렵다.

## 이번 브랜치 반영 범위

1. `WorkflowNexusSnapshot`에 중앙 blueprint 응답 Markdown을 추가한다.
2. `CentralAgentView`에서 `Central Agent Response` 섹션을 출력한다.
3. `blueprint_ready` 상태이고 WP가 존재할 때 중앙 패널에 다음 행동 버튼을 표시한다.
4. 버튼은 `실행/Execute`, `기능 보강/Refine features`, `리스크 보강/Refine risks`, `WP 재분배/Rebalance WPs`로 구성한다.
5. `실행`은 기존 execute preflight 흐름으로 연결한다.
6. 보강 버튼은 선택한 범위에 따라 서로 다른 follow-up으로 연결한다.
7. 중앙 에이전트의 Codex synthesis 모델은 Codex agent의 설정 모델을 따른다. Codex agent 모델이 비어 있으면 `default`를 사용한다.
8. Settings 화면에서 Claude, Codex, Antigravity, Central agent 모델을 직접 선택하고 프로젝트 `trinity.config`에 저장한다.

## 화면 동작

### Blueprint 준비 전

중앙 패널은 기존처럼 목표, 수집 중 상태, provider 진행 상태를 보여준다.

### Blueprint 준비 후

중앙 패널은 다음 순서로 표시한다.

1. Workflow 상태
2. Goal
3. Synthesis 요약
4. Central Agent Response
5. Central WP Graph 또는 Local WP Graph
6. 다음 작업 버튼

`Central Agent Response`는 중앙 blueprint의 구조화 필드를 Markdown으로 재구성한다.

- 제목과 요약
- Architecture
- Data Flow
- External Dependencies
- Risks
- Acceptance Criteria
- Open Questions

### 다음 작업 버튼

버튼은 `state == blueprint_ready`이고 WP가 있을 때만 표시한다. 이미 `executing`, `reviewing`, `post_review_ready` 등 다음 단계로 넘어간 상태에서는 다시 표시하지 않는다.

- `실행/Execute`: 기존 `request_execution()`으로 연결되어 workspace preflight 또는 실행으로 이어진다.
- `기능 보강/Refine features`: 핵심 기능, 게임 루프, 사용자 경험, 빠진 결정을 더 구체화한다.
- `리스크 보강/Refine risks`: 실행 리스크, 안티패턴 가능성, 성능 우려, 검증 기준을 더 구체화한다.
- `WP 재분배/Rebalance WPs`: WP 범위, 담당 에이전트, 의존성, 병렬 실행 가능성을 다시 검토한다.

## 중앙 에이전트 모델 정책

중앙 synthesis provider 우선순위는 현재와 같이 `codex -> claude -> antigravity`를 유지한다.

Codex가 중앙 synthesis provider로 선택되면 `synthesis_model = "fast"` 또는 `"strong"`이어도 더 이상 `gpt-5.4-mini`나 `gpt-5.4`로 강제 매핑하지 않는다. 대신 Codex agent의 `AgentSpec.model`을 그대로 사용하고, 값이 비어 있으면 `default`를 사용한다.

`synthesis_model = "agent-default"`는 provider와 관계없이 선택된 중앙 provider agent의 `AgentSpec.model`을 따른다. Settings 화면의 중앙 모델 기본 선택지는 이 값을 사용한다.

이 정책은 사용자가 보는 Codex agent 모델과 중앙 에이전트가 실제 호출하는 Codex 모델을 맞추기 위한 것이다.

## Settings 화면

Settings 화면에는 네 개의 모델 선택 영역을 분리한다.

- Claude agent provider/model
- Codex agent provider/model
- Antigravity agent provider/model
- Central agent provider/model

Central agent는 기본적으로 agent default를 따르되, 사용자가 직접 provider와 model을 지정하면 해당 override를 사용한다.

모델 선택 UI에는 다음 정보가 함께 표시되어야 한다.

- known model choices
- current central provider override
- current central model override
- 저장 대상 프로젝트 config

## 향후 확장

이후 Settings 화면은 모델 선택을 넘어 provider 활성화/비활성화, actual observed model, context window, budget source, session persistence 지원 여부를 함께 보여줄 수 있다.

## 테스트 기준

- 중앙 Markdown이 blueprint 상세 응답을 WP 목록보다 먼저 보여준다.
- 다음 작업 버튼은 `blueprint_ready`와 WP 존재 조건에서만 표시된다.
- Codex synthesis `fast/strong` 티어는 Codex agent model 또는 `default`로 해석된다.
- 기존 Claude/Antigravity synthesis tier 매핑은 유지된다.
