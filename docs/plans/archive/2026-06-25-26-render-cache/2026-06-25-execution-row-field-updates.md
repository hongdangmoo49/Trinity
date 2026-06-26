# Execution Package Row Field-Level Updates

## 배경

실행 페이지의 `ExecutionPackageRow.update_projection()`은 row projection이 바뀔 때 task, executor, status, owner, review, risk 필드를 모두 갱신한다. 실제 실행 중에는 status나 review처럼 일부 값만 바뀌는 경우가 많아, 변경되지 않은 field까지 `Static.update()`를 호출하는 비용이 남아 있었다.

## 개선 방향

- row에 표시되는 field 문자열을 `_field_texts()`로 계산한다.
- 이전 field 문자열과 새 field 문자열을 비교해 실제로 바뀐 static field만 갱신한다.
- detail/retry/review 버튼 라벨과 disabled 상태도 값이 바뀐 경우에만 대입한다.

## 범위

- `src/trinity/textual_app/screens/execution_matrix.py`
- `tests/test_execution_package_row.py`

## 검증

- status만 바뀌는 projection 적용 시 status field만 update되는지 확인한다.
- 실행 페이지 관련 테스트와 전체 테스트를 통과시킨다.
