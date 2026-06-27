# Maintenance Strategy Refresh 540

## 목적

`docs/development/ci-and-maintenance-strategy.md`가 #486, `1.0.389` 기준에 머물러 있어 #487-#540 병합 내용을 최신 유지보수 기준에 반영한다.

## 범위

- Current Evidence의 검토 PR 범위와 패키지 버전을 최신화한다.
- #487-#540 변경사항을 Textual helper, Workflow facade cleanup, Nexus/Textual route helper, post-review/CI/archive bundle로 묶어 기록한다.
- cleanup 후보의 archive bundle, facade line snapshot, 다음 릴리즈 목표를 현재 main 구조에 맞게 갱신한다.
- 패치 버전을 `1.0.444`로 올린다.

## 비목표

- CI workflow, required smoke manifest, 테스트 범위는 변경하지 않는다.
- 코드 구조나 런타임 동작은 변경하지 않는다.
- 남아 있는 2026-06-27 계획서 archive는 별도 PR에서 처리한다.

## 검증

- `git diff --check`가 통과해야 한다.
- required smoke test가 통과해야 한다.
- `trinity --version`이 `1.0.444`를 출력해야 한다.
