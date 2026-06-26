# 중앙 패널 상태 값 한국어화

작성일: 2026-06-24

## 배경

실행 매트릭스, WP 상세 모달, 재시도 모달은 한국어 UI에서 status 값을 점진적으로 한국어화했다.
하지만 Nexus 중앙 패널의 최종 리뷰와 후속 보강 작업 섹션은 아직 `approved`, `pending`, `done` 같은
raw status token을 그대로 표시할 수 있다.

중앙 패널은 사용자가 현재 진행 상황을 가장 먼저 읽는 곳이므로, 라벨뿐 아니라 상태값도 UI 언어와 맞아야 한다.

## 목표

- 한국어 UI에서 중앙 패널의 최종 리뷰 status를 한국어로 표시한다.
- 한국어 UI에서 후속 보강 작업 item status를 한국어로 표시한다.
- 영어 UI는 기존 raw status 표기를 유지한다.
- snapshot/session/event 원본 값은 변경하지 않는다.
- 기존 `display_status_value` helper를 재사용해 화면별 status 번역 drift를 막는다.

## 구현 범위

- `CentralAgentView`에서 final review status와 post-review item status를 표시 helper로 렌더링한다.
- severity, reviewer, title, summary 같은 값은 기존 표시를 유지한다.
- unknown status는 원문 fallback을 유지한다.

## 테스트

- 한국어 중앙 패널 markdown에서 `approved`, `pending`, `done`이 각각 한국어로 표시되는지 검증한다.
- 영어 중앙 패널 markdown은 기존 raw status를 유지하는지 검증한다.
