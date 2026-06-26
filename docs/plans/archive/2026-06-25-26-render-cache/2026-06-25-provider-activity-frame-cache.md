# Provider Panel Activity Frame Cache

## 배경

ProviderPanel은 실행 중인 provider의 상태 label에 activity frame 문자를 붙인다. Nexus 화면의 activity tick이나 snapshot refresh 이후 `_apply_activity_frame()`이 호출되면 각 ProviderPanel에 frame 값이 전달된다.

현재 `set_activity_frame()`은 같은 frame 값이 다시 들어와도 running 상태이면 status label을 다시 update한다. frame이 변하지 않은 경우 화면에 표시될 문자열도 변하지 않으므로 no-op 처리할 수 있다.

## 개선 방향

- `set_activity_frame()`에서 modulo 적용 후 다음 frame 값을 계산한다.
- 다음 frame 값이 현재 frame과 같으면 바로 반환한다.
- frame이 바뀐 경우에만 `_activity_frame`을 갱신하고 running status label을 update한다.
- Ready/Done 등 non-running panel은 기존처럼 status update를 하지 않는다.

## 범위

- `src/trinity/textual_app/widgets/provider_panel.py`
- `tests/test_provider_panel.py`

## 검증

- running provider가 새 frame을 받으면 status label이 갱신되는지 확인한다.
- 같은 frame을 다시 받으면 status label update가 생략되는지 확인한다.
- non-running provider는 frame 변경에도 status update가 없는 기존 동작을 유지한다.
- Focused test와 전체 테스트를 통과시킨다.
