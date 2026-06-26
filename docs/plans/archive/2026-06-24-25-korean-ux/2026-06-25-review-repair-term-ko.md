# review-repair 한국어 용어 일관화

## 배경

review-repair 기능은 상세 패널과 액션 힌트에서 `리뷰 보정`으로 표시되지만, 일부 결과 메시지와 리포트 섹션에서는 `리뷰 복구`로 표시된다. 반면 Trinity에서는 execution recovery를 `실행 복구`로 쓰고 있어, `repair`와 `recovery`를 모두 `복구`로 표현하면 의미가 흐려진다.

## 목표

- review-repair 계열 사용자 문구를 `리뷰 보정`으로 통일한다.
- execution recovery 계열의 `복구` 표현은 유지한다.
- 영어 문구와 내부 상태 키는 변경하지 않는다.

## 작업 범위

1. review-repair 결과 메시지와 prefix 번역을 `리뷰 보정` 기준으로 수정한다.
2. repair guard 관련 fragment를 `보정 루프 가드`, `보정 재시작`으로 조정한다.
3. 리포트 화면의 `Review Repairs` 한국어 섹션명을 `리뷰 보정`으로 맞춘다.
4. 관련 workflow outcome 테스트를 갱신/보강한다.
5. 패치 버전을 갱신하고 테스트를 실행한다.

## 비범위

- execution recovery 상태/라벨 변경.
- review-repair 처리 로직 변경.
- 영어 문구 변경.
