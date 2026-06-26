# 실행 재시도 모달 상태 값 한국어화

작성일: 2026-06-24

## 배경

`ExecutionRetryModal`은 한국어 UI에서 제목, 필터, 버튼 같은 chrome label을 번역한다.
하지만 각 WP row의 상태 셀은 여전히 `failed`, `blocked`, `running` 같은 raw token을 표시한다.
재시도 여부를 결정하는 화면에서 상태값은 사용자의 주요 판단 근거이므로 UI 언어와 맞춰 보여주는 편이 좋다.

기존 `2026-06-24-execution-retry-modal-i18n.md`는 modal chrome만 범위로 잡았고
work-package 데이터 값은 보존했다. 이번 작업은 그 후속으로, 원본 데이터는 그대로 두고 표시 계층에서만
status 값을 번역한다.

## 목표

- 한국어 UI에서 실행 재시도 모달의 WP status 셀을 한국어로 표시한다.
- 영어 UI는 기존 raw status 표기를 유지한다.
- selector, retry 후보 계산, snapshot/event 원본 값은 변경하지 않는다.
- WP 상세 모달과 동일한 status display helper를 공유해 화면별 번역 drift를 막는다.

## 구현 범위

- `status_label.py`에 긴 상태값 표시용 helper를 추가한다.
- `WorkPackageDetailModal`의 status display map을 공유 helper로 이동한다.
- `ExecutionRetryModal`의 row status cell에서 공유 helper를 사용한다.
- 기존 selector 비교는 계속 raw status 값으로 수행한다.

## 테스트

- 한국어 재시도 모달 row가 `실패`, `차단`, `실행중`을 표시하는지 검증한다.
- 영어 재시도 모달은 `failed` raw status 표시를 유지하는지 검증한다.
- WP 상세 모달 status 한국어화 테스트가 공유 helper 전환 후에도 통과하는지 확인한다.
