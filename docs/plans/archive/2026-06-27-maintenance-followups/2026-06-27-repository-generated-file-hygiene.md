# Repository Generated File Hygiene

## 목적

Python cache, pytest/ruff cache 같은 생성물이 Git에 다시 추적되지 않도록 required smoke 수준의 저장소 위생 검사를 추가한다.

## 범위

- `.gitignore`에 Python bytecode와 ruff cache ignore 규칙을 보강한다.
- `git ls-files` 기준으로 추적 중인 cache/generated 파일을 검출하는 테스트를 추가한다.
- 새 hygiene 테스트를 required smoke manifest에 포함한다.
- 패치 버전을 `1.0.450`으로 올린다.

## 비목표

- 로컬에 이미 존재하는 무시된 cache 디렉터리는 삭제하지 않는다.
- 전체 dead code 분석이나 미사용 모듈 제거는 이번 PR에서 수행하지 않는다.
- CI matrix나 fast path 분류 정책은 변경하지 않는다.

## 검증

- repository hygiene 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.450`을 출력해야 한다.
