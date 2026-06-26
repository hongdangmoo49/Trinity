# 중앙 패널 실행 진행 카운트 한국어화

작성일: 2026-06-24

## 배경

중앙 패널의 진행 라인은 한국어 UI에서 `실행 중` 같은 라벨은 한국어로 표시하지만,
실행 중 workflow의 상세 카운트는 `1 done / 1 running / 2 waiting / 1 blocked`처럼 영어 bucket 이름을
그대로 사용한다.

사용자가 Nexus 첫 화면에서 현재 실행 상태를 빠르게 읽는 영역이므로, 카운트 라벨도 UI 언어와 맞춰야 한다.

## 목표

- 한국어 UI에서 중앙 패널 실행 진행 카운트를 `완료`, `실행중`, `대기`, `막힘`으로 표시한다.
- 영어 UI는 기존 `done`, `running`, `waiting`, `blocked` 표시를 유지한다.
- `work_package_counts()`의 bucket key나 snapshot 원본 값은 변경하지 않는다.

## 구현 범위

- `CentralAgentView._execution_progress()`에서 카운트 label을 `_label()` 기반으로 렌더링한다.
- 기존 `blocked` label을 재사용하고, `done/running/waiting` 진행 카운트 전용 label을 추가한다.
- 실행 진행 문자열만 변경하며, progress summary widget이나 inspector는 변경하지 않는다.

## 테스트

- 한국어 중앙 패널 progress line에서 영어 bucket 이름이 사라지고 한국어 카운트 라벨이 표시되는지 검증한다.
- 영어 중앙 패널 progress line은 기존 문구를 유지하는지 검증한다.
