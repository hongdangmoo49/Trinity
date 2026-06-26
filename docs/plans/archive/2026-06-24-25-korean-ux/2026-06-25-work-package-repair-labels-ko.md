# 작업 상세 review-repair 용어 일관화

## 배경

review-repair 흐름은 Nexus 중앙 패널과 outcome 메시지에서 `리뷰 보정`, `보정 루프`, `보정 메모`로 표시된다. 그러나 작업 패키지 상세 모달의 WP 단위 repair 라벨은 `복구 시도`, `복구 루프`, `복구 메모`로 남아 있어 같은 review-repair 상태를 다른 용어로 보여준다.

## 목표

- 작업 패키지 상세 모달의 repair 관련 한국어 라벨을 `보정` 기준으로 맞춘다.
- execution recovery에서 사용하는 `복구` 표현은 변경하지 않는다.
- 영어 상세 모달 문구와 데이터 렌더링 구조는 유지한다.

## 작업 범위

1. `WorkPackageDetailModal` 한국어 `repair_attempts`, `repair_loop_blocked`, `repair_notes` 라벨을 수정한다.
2. 한국어 상세 모달 테스트에 보정 시도/루프/메모 라벨 검증을 추가한다.
3. 패치 버전을 갱신하고 테스트를 실행한다.

## 비범위

- execution retry note 또는 execution recovery 라벨 변경.
- repair/recovery 데이터 구조 변경.
- 영어 상세 모달 문구 변경.
