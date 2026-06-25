# Workspace Branch Fallback Korean Display

## Context

Workspace preflight는 git branch를 읽지 못하면 내부 sentinel인 `unknown`을
사용한다. 한국어 UI의 다른 preflight fallback은 `알 수 없음`으로 표시되지만,
branch 값은 그대로 렌더링될 수 있어 `브랜치: unknown`처럼 언어가 섞인다.

## Scope

- WorkspacePreflight 렌더링에서 `(none)`, 빈 값, `unknown` branch fallback을
  언어별 라벨로 표시한다.
- 영어 출력의 기존 `Branch: unknown` 동작은 유지한다.
- 한국어 출력은 `브랜치: 알 수 없음`으로 표시한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- 한국어 preflight에서 branch fallback이 `알 수 없음`으로 보인다.
- 영어 preflight에서는 기존 `unknown` 표시가 유지된다.
- 실제 branch 이름은 변환하지 않고 그대로 표시한다.
