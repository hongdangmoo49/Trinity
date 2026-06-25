# Provider Panel Class Update Cache

## 배경

ProviderPanel은 provider state가 바뀔 때마다 CSS class 문자열을 다시 적용한다. 이전 PR에서 field 단위 `Static.update()`는 줄였지만, summary/details만 바뀌어 status group이 그대로인 경우에도 `set_classes()` 호출은 남아 있었다.

Nexus 실행 중 provider summary가 갱신되는 빈도는 높을 수 있고, status group이 유지된다면 class 재적용은 화면 상태를 바꾸지 않는다.

## 개선 방향

- `ProviderPanel.update_state()`에서 이전 class 문자열과 새 class 문자열을 비교한다.
- class 문자열이 달라진 경우에만 `set_classes()`를 호출한다.
- status/summary/name/meta field 단위 갱신은 기존 동작을 유지한다.

## 범위

- `src/trinity/textual_app/widgets/provider_panel.py`
- `tests/test_provider_panel.py`

## 검증

- summary만 바뀌고 status group이 같은 경우 class 갱신이 생략되는지 확인한다.
- summary field는 정상 갱신되는지 확인한다.
- ProviderPanel 테스트와 전체 테스트를 통과시킨다.
