# WorkflowInspector 렌더 키 재바인딩 보강

- 브랜치: `perf/workflow-inspector-render-key-rebind`
- 버전: `1.0.291` -> `1.0.292`
- 대상: `src/trinity/textual_app/widgets/inspector.py`

## 배경

`WorkflowInspector`는 Nexus 우측 인스펙터의 진행 요약, 현재/다음 작업, 차단 항목, 워크플로우 메타, 프로바이더, 질문, 결정, 사후 리뷰, 실행 로그를 섹션별 Static 위젯으로 렌더한다. 반복 snapshot 갱신 비용을 줄이기 위해 `_snapshot_render_key`로 동일 projection을 건너뛰고, `_section_text`로 섹션별 동일 텍스트 업데이트를 생략한다.

하지만 `refresh(recompose=True)` 이후에는 섹션 Static 위젯들이 새로 만들어진다. 기존 compose 경로는 `_section_widgets`만 비우고 `_snapshot_render_key`와 `_section_text`는 유지했기 때문에, 같은 snapshot 객체나 같은 projection이 다시 적용되면 새 위젯이 빈 상태인데도 렌더가 스킵될 수 있다.

## 개선안

1. compose 시작 시 섹션 위젯 캐시와 렌더 캐시를 명시적으로 분리해 초기화한다.
2. `_section_text`와 `_snapshot_render_key`를 새 DOM 기준으로 리셋한다.
3. 리컴포즈 후 같은 snapshot 객체를 다시 적용해도 workflow/current 섹션이 복구되는지 테스트한다.

## 기대 효과

- Nexus 인스펙터가 재구성된 뒤 섹션 내용이 빈 상태로 남는 문제를 방지한다.
- 동일 snapshot projection 스킵 최적화는 유지하면서 DOM 재구성 시점에는 섹션 텍스트 캐시를 새 위젯 생명주기에 맞춘다.
- 중앙 패널, 질문 패널 등 다른 Nexus 위젯과 render cache 수명주기를 일관되게 맞춘다.
