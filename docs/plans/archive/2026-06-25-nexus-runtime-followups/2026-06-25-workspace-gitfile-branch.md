# Workspace Gitfile Branch Detection

## Context

Git worktree나 일부 checkout 형태에서는 `.git`이 디렉터리가 아니라
`gitdir: ...`를 담은 파일이다. Workspace preflight는 `.git` 존재 여부로 git
저장소를 감지하지만 branch는 `.git/HEAD`만 읽어, worktree에서는 branch가
`unknown`으로 표시될 수 있다.

## Scope

- `.git` 디렉터리의 `HEAD` 읽기 동작은 유지한다.
- `.git` 파일의 `gitdir:` 값을 읽어 실제 git dir의 `HEAD`를 확인한다.
- 상대 `gitdir:` 경로는 worktree 경로 기준으로 해석한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- 일반 git 저장소 branch 감지는 기존처럼 동작한다.
- git worktree 형태의 `.git` 파일에서도 branch 이름을 표시한다.
- branch를 읽지 못하는 경우에는 기존 fallback인 `unknown`을 유지한다.
