# Report no-peer review 라벨 정렬

작성일: 2026-06-24

## 배경

실행 매트릭스는 provider가 1개뿐이라 peer review가 불가능한 경우 `no peer` 또는 `peer 없음`으로 표시한다.
하지만 Report 화면과 Markdown export의 Work Package Routing 섹션은 같은 상태를 여전히 `skipped`로 표시한다.

보고서는 실행 결과를 나중에 되짚어보는 화면이므로, peer review가 정책상 생략된 이유를 matrix와 같은 의미로
보여주는 편이 좋다.

## 목표

- Report 화면의 Work Package Routing review label에서 no-peer skip을 `no peer`로 표시한다.
- Markdown export의 Work Package Routing review label도 `no peer`로 표시한다.
- 일반 `skipped` review는 기존 `skipped` 표기를 유지한다.
- 실행 매트릭스와 Report가 같은 no-peer 판별 helper를 사용한다.
- review status 원본 값과 skip reason 텍스트는 보존한다.

## 구현 범위

- `status_label.py`에 no-peer review skip 판별 및 표시 helper를 추가한다.
- 실행 매트릭스의 private no-peer 판별을 공유 helper로 대체한다.
- Report 화면과 Markdown export의 review status 표시에서 공유 helper를 사용한다.

## 테스트

- execution matrix의 기존 no-peer label 테스트가 통과한다.
- snapshot Markdown export에서 no-peer skip이 `no peer`로 표시되고 reason은 보존된다.
- Report 화면 Work Package Routing에서도 no-peer skip이 `no peer`로 표시된다.
