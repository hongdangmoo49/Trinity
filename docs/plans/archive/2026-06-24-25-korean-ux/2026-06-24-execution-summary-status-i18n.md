# Execution Summary Status I18n

## 문제

Execution Matrix의 한국어 UI는 버튼, prefix, retry/workflow/run label을 번역하지만
summary bar의 status count는 `RUN`, `REVIEW`, `WAIT`, `DONE`, `ISSUE`로 고정되어 있다.

row 내부 status badge는 폭이 매우 제한된 badge 역할이므로 영문 compact token을 유지할 수 있지만,
summary bar는 문장형 정보에 가까워 한국어 UI에서는 언어 혼합이 눈에 띈다.

## 설계

- summary bar의 count label만 i18n label로 분리한다.
- 영어 UI는 기존 `RUN`, `REVIEW`, `WAIT`, `DONE`, `ISSUE`를 유지한다.
- 한국어 UI는 짧은 한국어 label을 사용한다.
  - `실행중`
  - `리뷰`
  - `대기`
  - `완료`
  - `문제`
- row status badge와 `compact_status_label()` 계약은 변경하지 않는다.

## 기대 효과

- 한국어 실행 화면의 summary bar 언어 혼합을 줄인다.
- 기존 row width와 compact status badge 안정성은 유지된다.
- summary count 계산 방식은 그대로라 동작 위험이 낮다.

## 테스트

- 영어 summary bar는 기존 `RUN 1` 형태를 유지한다.
- 한국어 summary bar는 `실행중`, `리뷰`, `대기`, `완료`, `문제` label을 사용한다.
- 기존 retry/workflow/run/target 라벨은 유지된다.
