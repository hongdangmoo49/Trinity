# shared context memory 구현 요약

작성일: 2026-06-09
브랜치: `feature/shared-context-headroom-design`
버전: `0.12.2`

## 작업 개요

`shared.md`가 실행/재시도 과정에서 과도하게 커지고, `resume` 이후 `/execute-retry` 같은 경로에서 큰 파일을 통째로 읽다가 종료될 수 있는 문제를 줄이기 위해 shared context 관리 계층을 보강했다.

이번 작업은 `docs/plans/2026-06-09-headroom-shared-context-memory-design.md` 설계를 기준으로 다음 범위를 구현했다.

## 구현 내용

### shared.md 폭증 방지

- `SharedContextEngine._parse_sections()`가 section body에 `## Heading`을 포함하지 않도록 수정했다.
- 반복 `append_to_section()` 호출 시 같은 heading이 body 안에 중복 삽입되던 문제를 막았다.
- `shared.md`가 `shared_max_bytes`를 넘으면 전체 파일을 읽지 않고 recovery notice를 반환한다.
- mutation이 필요한 시점에 oversized 파일은 `shared.md.oversized-<timestamp>`로 보존하고 작은 recovery projection을 만든다.
- task/subtask result의 긴 summary와 list item은 bounded text로 잘라 shared projection이 급격히 커지지 않게 했다.

### 메모리 인덱스

- `src/trinity/context/memory.py`를 추가했다.
- SQLite 기반 `MemoryStore`, `MemoryRecord`, `MemoryStats`, `ContentRouter`를 도입했다.
- work package 실행 결과와 subtask 결과는 기존 shared section에도 짧게 남기고, 동시에 `.trinity/memory/index.sqlite`에 record로 저장한다.
- JSON 문자열은 memory summary 단계에서 pretty format으로 정리된다.

### bounded projection과 prompt packing

- `SharedContextEngine.compact_projection_from_memory()`를 추가했다.
- pinned section과 최근 memory record를 이용해 `shared.md`를 bounded projection으로 재생성할 수 있다.
- `src/trinity/context/packing.py`에 `ContextPacker`를 추가했다.
- `SharedContextEngine.pack_context_for_prompt()`를 통해 provider prompt에 넣을 context bundle을 token budget 안에서 만들 수 있다.

### 명령과 UI 연결

- 새 slash command를 등록했다.
  - `/memory [stats|compact]`
  - `/artifact <memory-id>`
- Plain TUI와 Textual Workbench 모두에서 새 명령을 처리한다.
- CLI에서도 다음 명령을 사용할 수 있다.
  - `trinity memory stats`
  - `trinity memory compact`
  - `trinity artifact <memory-id>`
- `docs/slash-command-reference.md`와 slash command routing design 문서를 registry와 동기화했다.

### 설정

`[context]`에 다음 설정을 추가했다.

- `shared_max_bytes`
- `shared_compact_target_bytes`
- `shared_section_entry_max_chars`
- `auto_compact_on_start`
- `memory_index_enabled`
- `memory_prompt_budget_tokens`
- `memory_recent_records`
- `memory_retrieval_max_bytes`
- `compression_mode`
- `repair_max_attempts`

## 검증

전체 테스트를 통과했다.

```text
1332 passed, 1 warning in 75.61s
```

추가로 버전 출력도 확인했다.

```text
0.12.2
```

관련 부분 테스트:

- `tests/test_shared_context.py`
- `tests/test_context_memory.py`
- `tests/test_context_packing.py`
- `tests/test_context_commands.py`
- `tests/test_tui_prompt.py`
- `tests/test_slash_command_docs.py`
- `tests/test_config.py`
- `tests/test_cli.py`
- `tests/test_updater.py`

## 남은 고려사항

- `compression_mode = "headroom"`의 실제 외부 adapter 연결은 아직 기본값으로 넣지 않았다. 현재는 deterministic local compression과 memory index 기반 구조를 먼저 구현했다.
- `ContextPacker`는 provider prompt에 사용할 수 있는 API로 추가되었고, 향후 deliberation/execution prompt 생성 경로에서 더 적극적으로 적용할 수 있다.
- oversized 파일에서 원문 내용을 의미 단위로 복원하는 full repair는 `/memory compact`의 다음 단계로 확장할 수 있다.
