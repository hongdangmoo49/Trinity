# Maintenance Followup Plan Archive

## 목적

root `docs/plans/`에 남은 완료된 2026-06-27 follow-up 계획서를 archive bundle로 이동해 현재 계획 목록과 완료 기록을 명확히 분리한다.

## 범위

- 완료된 maintenance refresh, Nexus event render window, required smoke runner, review repair metadata, Textual target command helper, 그리고 archive 정리 계획서 8개를 `docs/plans/archive/2026-06-27-maintenance-followups/`로 이동한다.
- 이번 archive 작업의 설계문서도 같은 archive bundle에 보관해 root 계획서가 다시 늘어나지 않게 한다.
- `docs/plans/completed-index.md`에 maintenance followups archive bundle과 PR 범위를 기록한다.
- `docs/plans/README.md`의 recent bundle map과 archive bundle 목록을 최신화한다.
- 패치 버전을 `1.0.447`로 올린다.

## 비목표

- Nexus snapshot, required smoke runner, review repair, Textual target workspace 동작은 변경하지 않는다.
- required smoke manifest나 GitHub Actions workflow는 변경하지 않는다.
- 오래된 2026-06-09, 2026-06-12, 2026-06-17 계획서 archive는 별도 PR에서 처리한다.

## 검증

- `git diff --check`가 통과해야 한다.
- root `docs/plans/`에 2026-06-27 계획서가 남지 않아야 한다.
- required smoke test가 통과해야 한다.
- `trinity --version`이 `1.0.447`을 출력해야 한다.
