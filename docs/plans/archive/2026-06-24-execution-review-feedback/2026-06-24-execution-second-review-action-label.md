# Execution Second Review Action Label

## 문제

Execution Matrix는 `needs_second_review` review 상태를 `needs 2nd` 또는 `2차필요`로
표시하지만, row action button은 여전히 기본 `Spec`/`상세` 라벨을 사용한다.

사용자는 2차 리뷰가 필요한 상태에서 어떤 버튼을 눌러 상세 맥락을 확인해야 하는지
즉시 알기 어렵다.

## 설계

- workflow mutation은 추가하지 않는다.
- `needs_second_review` 상태의 row detail button label만 바꾼다.
  - 영어: `2nd Review`
  - 한국어: `2차리뷰`
- 버튼 동작은 기존처럼 WP 상세 모달을 연다.
- 상세 모달의 `Review Plan` 섹션에서 2차 리뷰 대기 안내를 확인하게 한다.

## 기대 효과

- escalation 대기 상태가 row action 영역에서도 드러난다.
- 사용자가 `Spec` 버튼이 아니라 리뷰 맥락 확인 버튼으로 인식할 수 있다.
- 실제 2차 리뷰 요청 액션은 별도 workflow command/handler 설계로 분리할 수 있다.

## 테스트

- `needs_second_review` package의 detail button label이 영어/한국어에서 바뀐다.
- blocked package button label 우선순위는 기존처럼 `Blocked`/`차단됨`을 유지한다.
- 기본 package는 기존 `Spec`/`상세` 라벨을 유지한다.
