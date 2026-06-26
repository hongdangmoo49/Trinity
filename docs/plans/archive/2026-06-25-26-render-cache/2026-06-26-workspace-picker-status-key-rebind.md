# WorkspacePicker 상태 키 재바인딩 보강

- 브랜치: `perf/workspace-picker-status-key-rebind`
- 버전: `1.0.293` -> `1.0.294`
- 대상: `src/trinity/textual_app/widgets/workspace_picker.py`

## 배경

`WorkspacePicker`는 실행/선택 대상 workspace를 확인하면서 preflight 결과와 하단 status 메시지를 렌더한다. 반복 업데이트 비용을 줄이기 위해 preflight text와 status text를 각각 `_preflight_render_key`, `_status_key`로 기억하고 같은 텍스트 업데이트를 건너뛴다.

하지만 `refresh(recompose=True)` 이후에는 `#workspace-preflight`와 `#workspace-picker-status` Static 위젯이 새로 만들어진다. 기존 compose 경로는 위젯 참조만 초기화했기 때문에, 특히 status 영역은 새 Static이 빈 상태인데 `_status_key`가 이전 메시지로 남아 같은 메시지 재표시가 스킵될 수 있다.

## 개선안

1. compose 시작 시 고정 위젯 캐시와 함께 preflight/status render key를 초기화한다.
2. compose에서 preflight Static과 status Static을 만든 직후 현재 DOM 기준의 render key를 다시 묶는다.
3. 리컴포즈 후 같은 status 메시지를 다시 설정해도 하단 status 영역이 복구되는지 테스트한다.

## 기대 효과

- WorkspacePicker 재구성 후 동일 status 메시지가 빈 상태로 남는 문제를 방지한다.
- 기존 같은 텍스트 업데이트 스킵 최적화는 유지하면서 새 DOM 생명주기와 render key를 맞춘다.
- 실행 전 workspace 선택 UX의 오류/안내 메시지 표시 안정성을 높인다.
