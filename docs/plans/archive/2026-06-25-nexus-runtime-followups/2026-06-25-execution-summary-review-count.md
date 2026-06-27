# Execution Summary Review Count

## Context

Nexus 실행 페이지 summary는 work package 상태를 compact bucket으로 먼저 분류한다.
`needs_review`가 waiting bucket에 포함되면, 리뷰 대기 작업이 summary에서 `REVIEW`
가 아니라 `WAIT`로 집계될 수 있다. 또한 행의 review column도 review status가
아직 기록되기 전에는 `-`로 보여 리뷰 대기 상태가 눈에 잘 드러나지 않는다.

## Scope

- summary count에서 실행 중/문제 상태를 우선 유지하고, 그다음
  pending/queued/reviewing/needs-second-review 상태를 REVIEW로 집계한다.
- `status=needs_review`이고 별도 review status가 없을 때 review column을
  `queued`/`대기`로 표시한다.
- approved review는 완료 집계로 유지한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- `needs_review` 작업은 summary에서 REVIEW로 집계된다.
- queued/reviewing/needs-second-review review status도 REVIEW로 집계된다.
- 실행 중인 작업은 review status가 미리 있어도 RUN 집계로 유지된다.
- approved review가 완료된 작업은 DONE 집계로 유지된다.
