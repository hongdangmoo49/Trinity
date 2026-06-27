# Workflow Facade Plan Archive

## 목적

#493-#517에서 완료된 Workflow facade cleanup 단위 계획서를 root `docs/plans/`에서 archive bundle로 이동해 현재 계획 목록을 줄인다.

## 범위

- Workflow wrapper 제거, persistence 직접 호출, flow helper 이동, flow contract 최신화 계획서 25개를 `docs/plans/archive/2026-06-27-workflow-facade-cleanup/`로 이동한다.
- `docs/plans/completed-index.md`에 archive bundle과 PR 범위를 기록한다.
- `docs/plans/README.md`의 recent bundle map과 archive bundle 목록을 최신화한다.
- 패치 버전을 `1.0.446`으로 올린다.

## 비목표

- `WorkflowEngine`, flow module, persistence runtime 동작은 변경하지 않는다.
- required smoke manifest나 CI workflow는 변경하지 않는다.
- 남아 있는 Nexus/CI/review-repair 단위 계획서 archive는 별도 PR에서 처리한다.

## 검증

- `git diff --check`가 통과해야 한다.
- required smoke test가 통과해야 한다.
- `trinity --version`이 `1.0.446`을 출력해야 한다.
