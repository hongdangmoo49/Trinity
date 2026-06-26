# Provider Inspector Truncation Korean Display

## Context

Provider Inspector는 긴 inline raw output 또는 큰 raw artifact 파일을 표시할 때
출력을 잘라서 보여준다. 이때 한국어 UI에서도 truncation 안내가 영어 고정 문구로
표시되어, 나머지 한국어 라벨과 어색하게 섞인다.

## Scope

- Provider Inspector 출력 포맷 경로에 언어 인자를 전달한다.
- 긴 inline raw output truncation marker를 한국어로 표시한다.
- 큰 raw artifact 파일의 bounded read marker를 한국어로 표시한다.
- 기존 영어 marker는 그대로 유지한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- 한국어 UI에서 긴 provider 출력은 `자 생략됨` 안내를 표시한다.
- 한국어 UI에서 큰 raw artifact는 마지막 표시 범위와 원본 확인 안내를 한국어로
  표시한다.
- 영어 UI 기존 truncation marker 테스트는 계속 통과한다.
