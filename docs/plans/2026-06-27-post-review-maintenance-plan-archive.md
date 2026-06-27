# Post Review Maintenance Plan Archive

## 목적

완료된 post-review maintenance helper 단위 계획서를 root `docs/plans/`에서 archive bundle로 이동해 현재 진행 중인 계획과 완료된 기록을 구분한다.

## 범위

- #534-#537에서 완료된 post-review helper 계획서 4개를 `docs/plans/archive/2026-06-27-post-review-maintenance/`로 이동한다.
- `docs/plans/completed-index.md`에 post-review maintenance archive bundle과 PR 범위를 기록한다.
- `docs/plans/README.md`의 archive bundle 목록을 최신화한다.
- 패치 버전을 `1.0.443`으로 올린다.

## 비목표

- post-review selection, owner assignment, supplemental WorkPackage 생성, execution run payload 생성 동작은 변경하지 않는다.
- workflow runtime, Textual/Nexus UI, required smoke manifest 범위는 변경하지 않는다.
- 다른 2026-06-27 계획서는 이번 PR에서 archive하지 않는다.

## 검증

- `git diff --check`가 통과해야 한다.
- required smoke test가 통과해야 한다.
- `trinity --version`이 `1.0.443`을 출력해야 한다.
