# Execution Log Modal Window

## 문제

Execution Matrix는 inline activity feed를 최근 몇 줄로 제한하지만, `Full Log` 모달은
전달받은 모든 log line을 mount 시점에 `RichLog.write()`로 렌더링한다.

긴 workflow에서는 log source가 수천 줄까지 커질 수 있고, 모달을 여는 순간 모든 줄을
widget에 쓰면 실행 페이지가 잠깐 무거워질 수 있다.

## 설계

- 원본 log source는 `ExecutionMatrixScreen._full_activity_lines()`에 그대로 둔다.
- `ExecutionLogModal` 내부 렌더링만 tail window로 제한한다.
- 기본 window는 최근 500줄이다.
- 숨겨진 이전 줄이 있으면 첫 줄에 숨김 카운트를 표시한다.
- 로그가 없으면 기존 empty state를 유지한다.
- 한국어 UI에는 기존 activity feed와 같은 톤의 숨김 카운트 문구를 사용한다.

## 기대 효과

- 긴 workflow에서도 full log modal mount 비용이 bounded 된다.
- 사용자는 최신 실행 맥락을 빠르게 볼 수 있다.
- 원본 snapshot/log 데이터는 잘리지 않으므로 추후 export/search 기능으로 확장할 수 있다.

## 테스트

- 500줄 이하 로그는 그대로 표시된다.
- 500줄 초과 로그는 숨김 카운트와 최근 500줄만 렌더링 대상이 된다.
- 한국어 모드에서도 숨김 카운트가 한국어로 표시된다.
- 빈 로그는 기존 empty state를 유지한다.
