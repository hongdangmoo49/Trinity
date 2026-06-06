# Execution Matrix Hardening

작성일: 2026-06-05

브랜치: `codex/execution-matrix-hardening`

## 수정 범위

- Blueprint decomposition에서 markdown code fence, 표 header, 섹션 heading,
  `GameCore/` 같은 구조 표시가 work package로 생성되지 않도록 정제했다.
- 실행 package의 `expected_files`를 넓은 `src/`, `tests/` 대신
  package별 scoped ownership으로 생성해 같은 workspace에서도 병렬 batch가
  형성될 수 있게 했다.
- `acceptance_criteria`에 섞인 `VOTE: BLOCKED_BY_QUESTION`, 사용자 결정 질문,
  옵션 행을 실행 prompt에서 제거해 provider가 불필요하게 blocked로 응답하는
  경로를 줄였다.
- owner agent가 `BLOCKED`를 반환해도 다른 실행 agent가 있으면 fallback을
  시도하도록 `ExecutionProtocol`을 보강했다.
- `No blockers.` 같은 명시적 무차단 응답을 실제 blocker로 파싱하지 않도록 했다.
- Execution Matrix log가 `work_package_started: executing`만 반복하지 않고
  package id, agent, status, target workspace, package count를 표시하도록 했다.

## 재현 기준

스크린샷 기준 active workflow는 모바일 슈팅게임 blueprint에서 다음 문제가 있었다.

- 17개 work package 중 markdown artifact와 구조 heading이 package로 섞임
- 대부분의 package가 `expected_files = ["src/", "tests/"]`라서 병렬 정책이
  같은 workspace write collision으로 판단함
- acceptance criteria에 `VOTE: BLOCKED_BY_QUESTION`과 사용자 질문이 남아
  실행 prompt로 전달됨
- Execution Matrix log가 event data를 버려 동일한 started 메시지만 반복 표시함

수정 후 같은 blueprint를 새 decomposer로 재생성하면 `InputController`,
`EntityManager`, `WaveSpawner`, `CollisionSystem`, `PowerUpSystem`,
`ScoreManager`, `AudioManager`, `Data flow and integration` 중심 package로
정리되고, 각각 scoped `expected_files`를 갖는다.

## 검증

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_blueprint_decomposer.py tests/test_execution_protocol.py tests/test_textual_snapshot.py tests/test_workflow_engine.py::test_plan_parallel_groups_respects_dependencies_and_file_ownership -q
```

결과:

```text
31 passed in 0.28s
```

```bash
/home/zaemi/.local/bin/uv run --with ruff ruff check src/trinity/workflow/decomposer.py src/trinity/workflow/execution.py src/trinity/textual_app/snapshot.py tests/test_blueprint_decomposer.py tests/test_execution_protocol.py tests/test_textual_snapshot.py
```

결과:

```text
All checks passed!
```

```bash
/home/zaemi/.local/bin/uv run pytest -q
```

결과:

```text
1159 passed, 1 warning in 57.80s
```

남은 warning은 기존 `tests/test_e2e.py::TestE2EContext::test_context_shows_shared`
AsyncMock runtime warning이다.
