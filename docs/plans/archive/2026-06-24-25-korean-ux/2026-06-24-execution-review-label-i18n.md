# Execution Review Label I18n

## 문제

Execution Matrix의 행 prefix와 버튼은 한국어 UI에서 번역되지만, review 상태 값은
`agy queued`, `skip`, `needs 2nd`처럼 영어 compact label로 남아 있다.

실행 페이지는 좁은 터미널에서도 한눈에 상태를 읽는 화면이므로, 한국어 모드에서는
review 상태 값도 같은 언어로 맞추는 편이 자연스럽다.

## 설계

- `_review_label()`에 `lang` 인자를 추가한다.
- 영어 기본 label은 기존 값을 유지한다.
- 한국어 label은 compact 폭을 유지하기 위해 짧은 상태어를 사용한다.
  - `queued` -> `대기`
  - `reviewing` -> `검토`
  - `changes_requested` -> `변경요청`
  - `approved` -> `승인`
  - `blocked`/`failed` -> `문제`
  - `skipped` -> `생략`
  - `needs_second_review` -> `2차필요`
- reviewer가 있는 queued/reviewing 상태는 `agy 대기`, `claude 검토`처럼 표시한다.
- reviewer가 여러 명이면 `2명 검토`, `3명 대기`처럼 표시한다.

## 기대 효과

- 한국어 실행 화면에서 review row가 언어 혼합 없이 읽힌다.
- provider 1개 환경의 `skipped` 상태가 `생략`으로 더 명확하게 보인다.
- 영어 UI와 기존 테스트 계약은 유지된다.

## 테스트

- 기존 영어 `_review_label()` 결과가 유지된다.
- 한국어 `_review_label()`이 queued/reviewing/skipped/needs second review를 번역한다.
- 한국어 Execution Matrix viewport 테스트가 번역된 review label을 확인한다.
