# WP 상세 모달 상태 값 한국어화

작성일: 2026-06-24

## 배경

실행 페이지의 행, 요약, 리뷰 라벨은 한국어 UI에서 상당 부분 정리되었지만 WP 상세 모달에는 아직
`failed`, `changes_requested`, `needs_second_review`, `skipped` 같은 내부 status token이 그대로 노출된다.
라벨은 한국어인데 값이 영어 token이면 사용자는 현재 상태를 한 번 더 해석해야 한다.

## 목표

- WP 상세 모달의 한국어 UI에서 status/review/result status 값을 자연스러운 한국어로 표시한다.
- 영어 UI는 기존 raw status 표기를 유지해 호환성을 보존한다.
- snapshot, session, event log의 원본 status 값은 변경하지 않는다.
- provider summary, retry disabled reason, review summary 같은 자유 텍스트는 번역하지 않는다.

## 표시 정책

| 원본 값 | 한국어 표시 |
| :--- | :--- |
| `pending` | `대기` |
| `running` | `실행중` |
| `done` | `완료` |
| `failed` | `실패` |
| `blocked` | `차단` |
| `skipped` | `생략` |
| `changes_requested` | `변경 요청` |
| `needs_second_review` | `2차 리뷰 필요` |
| `approved` | `승인` |
| `queued` | `대기` |
| `reviewing` | `리뷰중` |

알 수 없는 값은 원본 문자열을 그대로 보여준다.

## 구현 범위

- `WorkPackageDetailModal`에 status display helper를 추가한다.
- 요약, 실행 결과, 리뷰 계획, 리뷰 섹션의 status 값을 helper로 렌더링한다.
- 리뷰 차단 안내 문구의 `{status}` 자리도 한국어 UI에서는 변환된 값을 사용한다.
- 기존 `retry`, `execution_lane`, `yes/no` 표시 helper와 동일하게 표시 계층에만 둔다.

## 테스트

- 한국어 상세 모달에서 `failed`, `changes_requested`, `needs_second_review`가 번역되어 보이는지 검증한다.
- 영어 상세 모달은 기존 status token을 유지하는지 검증한다.
- unknown status는 원문 fallback 되는지 검증한다.
