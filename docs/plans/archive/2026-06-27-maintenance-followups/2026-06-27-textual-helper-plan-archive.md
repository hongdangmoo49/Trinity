# Textual Helper Plan Archive

## 목적

#488-#492와 #518-#532에서 완료된 Textual helper 단위 계획서를 root `docs/plans/`에서 archive bundle로 이동해 현재 계획 목록을 줄인다.

## 범위

- Textual command helper, route snapshot, recovery/review repair presenter, target workspace helper, execution state helper 계획서 20개를 `docs/plans/archive/2026-06-27-textual-helper-continuation/`로 이동한다.
- `docs/plans/completed-index.md`에 archive bundle과 PR 범위를 기록한다.
- `docs/plans/README.md`의 recent bundle map과 archive bundle 목록을 최신화한다.
- 패치 버전을 `1.0.445`로 올린다.

## 비목표

- Textual runtime, command parser, route switching, target workspace 동작은 변경하지 않는다.
- required smoke manifest나 CI workflow는 변경하지 않는다.
- Workflow facade wrapper 계획서 archive는 별도 PR에서 처리한다.

## 검증

- `git diff --check`가 통과해야 한다.
- required smoke test가 통과해야 한다.
- `trinity --version`이 `1.0.445`를 출력해야 한다.
