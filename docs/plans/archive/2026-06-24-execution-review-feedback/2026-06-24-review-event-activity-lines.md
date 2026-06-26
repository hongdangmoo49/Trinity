# 리뷰 이벤트 activity line 개선

작성일: 2026-06-24

## 배경

`ReviewExecutionProtocol`은 이미 `review_package_queued`, `review_package_started`,
`review_package_completed`, `review_package_skipped` 이벤트를 발행한다. `NexusSnapshotAdapter`도 이 이벤트를
runtime review projection에 반영한다.

하지만 execution activity/log 문자열 formatter가 review event를 별도로 다루지 않으면 사용자에게는
`review_package_started` 같은 이벤트 이름만 보일 수 있다. 실행 페이지에서 review가 실시간으로 진행 중인지
이해하려면 package, reviewer, status가 한 줄에 보여야 한다.

## 목표

- review package lifecycle event를 activity/log에서 읽기 쉬운 한 줄로 표시한다.
- event payload, snapshot projection, review policy는 변경하지 않는다.
- summary가 있는 completed/skipped event는 짧게 덧붙인다.
- final review event는 기존 final review surface와 충돌하지 않도록 이번 범위에서 제외한다.

## 표시 예시

```text
review_package_queued: WP-001 codex queued
review_package_started: WP-001 codex reviewing
review_package_completed: WP-001 codex changes_requested - Needs safer terminal handling.
review_package_skipped: WP-001 codex skipped - Review agent 'codex' is not available.
```

## 테스트

- snapshot `execution_log`와 `workflow_events`에서 review package event가 package/reviewer/status를 포함한다.
- completed/skipped event는 summary를 짧게 포함한다.
- 기존 work package execution event format은 유지된다.
