# Succeeded Status Done Bucket

## Context

상세 상태 표시에는 `succeeded`가 `성공`으로 번역되지만 compact UI와 progress
summary의 상태 집합에는 `succeeded`가 없어 완료 상태가 `?` 또는 unknown으로
분류될 수 있다.

## Scope

- 공용 compact status helper에서 `succeeded`를 done bucket으로 분류한다.
- progress summary에서 package status와 last result status의 `succeeded`를 done으로
  집계한다.
- provider panel, execution matrix, progress summary 회귀 테스트를 보강한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- `succeeded` provider/work-package 상태는 compact UI에서 `DONE`/`완료`로 표시된다.
- `last_result_status=succeeded`는 progress summary에서 done으로 집계된다.
- 기존 `failed`/`blocked` 우선순위는 유지된다.
