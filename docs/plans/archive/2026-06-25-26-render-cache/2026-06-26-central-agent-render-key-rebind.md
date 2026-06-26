# CentralAgentView 렌더 키 재바인딩 보강

- 브랜치: `perf/central-agent-render-key-rebind`
- 버전: `1.0.290` -> `1.0.291`
- 대상: `src/trinity/textual_app/widgets/central_agent.py`

## 배경

`CentralAgentView`는 Nexus 중앙 패널의 목표, 중앙 응답, 로컬 명령 테이블, 다음 액션 버튼을 렌더한다. 반복 snapshot 갱신 비용을 줄이기 위해 `_markdown_key`, `_local_commands_key`, `_actions_key`, `_applied_snapshot_identity` 같은 렌더 키를 사용해 동일한 상태의 재렌더를 건너뛴다.

하지만 `refresh(recompose=True)` 이후에는 title/markdown/local command/action 컨테이너가 새로 만들어진다. 기존 compose 경로는 위젯 참조만 초기화하고 렌더 키는 유지했기 때문에, 같은 snapshot 객체가 다시 적용되면 이미 적용된 snapshot으로 판단해 로컬 명령 테이블과 액션 버튼 렌더가 생략될 수 있다.

## 개선안

1. compose 시작 시 고정 위젯 캐시와 함께 중앙 패널 렌더 캐시를 초기화한다.
2. `_button_actions`, title/markdown/action/local command 렌더 키, snapshot identity, running class key를 새 DOM 기준으로 리셋한다.
3. 리컴포즈 후 같은 snapshot 객체를 다시 적용해도 로컬 명령 테이블과 blueprint action 버튼이 복구되는지 테스트한다.

## 기대 효과

- Nexus 중앙 패널 리컴포즈 후 로컬 명령 테이블과 다음 액션 버튼이 빈 상태로 남는 상황을 방지한다.
- 같은 snapshot 객체 재적용 스킵 최적화는 유지하면서, DOM 재구성 시점에는 렌더 키를 새 위젯 생명주기에 맞춘다.
- 중앙 패널의 widget cache와 render cache 수명주기를 질문 패널 등 다른 Nexus 위젯 보강 방식과 일치시킨다.
