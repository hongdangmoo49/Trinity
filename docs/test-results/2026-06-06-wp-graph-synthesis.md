# WP Graph Synthesis Hardening Result

작성일: 2026-06-06

브랜치: `codex/wp-graph-synthesis`

## 목표

Central agent가 실행 가능한 WP graph를 만들고, Trinity runtime이 이를 로컬 policy로
검증/보수화한 뒤 실행 batch를 구성하도록 변경했다.

## 변경 요약

1. Central synthesis 기본 모델을 `fast`에서 `strong`으로 올렸다.
   명시적으로 `synthesis_model = "fast"`를 설정한 기존 사용자는 기존 경량 경로를 유지한다.
2. `Blueprint`가 `work_packages` graph를 보존하도록 확장했다.
3. Model-backed synthesis output schema가 `recommended_blueprint.work_packages`를 요구하고,
   parser가 scope/dependency/expected_files/risk/parallel flag를 정규화한다.
4. `BlueprintDecomposer`가 central WP graph를 우선 사용하되, owner/id/dependency/file scope를
   로컬에서 검증하고 보수화한다.
5. `ParallelExecutionPolicy`가 `parallelizable=false`, `risk=high`, root config/lockfile 같은
   공유 workspace 파일 변경을 같은 worktree 병렬 실행에서 제외한다.
6. `ExecutionProtocol`과 `WorkflowEngine.plan_parallel_groups()`가 같은 scheduling metadata를
   사용하도록 맞췄다.
7. 후속 보강으로 부모/자식 경로 충돌, broad root write scope, `parallel_group` 순서,
   policy notice 로그를 추가했다.

## 기대 효과

- WP 생성 주체가 단순 로컬 휴리스틱에서 central synthesis 중심으로 이동한다.
- 병렬 가능 여부는 모델의 의미 판단을 반영하되, 최종 실행은 로컬 정책이 보수적으로 제한한다.
- `expected_files`가 비어 있거나 owner/dependency가 잘못된 graph도 실행 전에 안전한 형태로
  보정된다.
- TUI의 병렬 group preview와 실제 실행 batch의 판단 기준이 더 가까워진다.
- Execution Matrix log에 batch 계획과 직렬화 이유가 남아 병렬 실행 여부를 추적하기 쉽다.

## 검증

```bash
uv run pytest tests/test_config.py::TestTrinityConfig::test_synthesis_config_defaults tests/test_config.py::TestTrinityConfig::test_load_synthesis_config tests/test_orchestrator.py::TestSynthesisAgentWiring -q
```

결과: `9 passed in 0.34s`

```bash
uv run pytest tests/test_synthesis_agent.py -q
```

결과: `10 passed in 0.20s`

```bash
uv run pytest tests/test_blueprint_decomposer.py tests/test_parallel_execution_policy.py tests/test_execution_protocol.py::test_execution_protocol_allows_disjoint_expected_files_same_worktree tests/test_execution_protocol.py::test_execution_protocol_serializes_high_risk_same_worktree_package tests/test_workflow_engine.py::test_plan_parallel_groups_respects_dependencies_and_file_ownership tests/test_workflow_engine.py::test_plan_parallel_groups_serializes_high_risk_work -q
```

결과: `20 passed in 0.40s`

```bash
uv run pytest tests/test_parallel_execution_policy.py tests/test_execution_protocol.py tests/test_workflow_engine.py tests/test_tui_events.py tests/test_tui_session.py tests/test_textual_snapshot.py tests/test_textual_workflow_controller.py -q
```

결과: `158 passed in 2.00s`

```bash
git diff --check
```

결과: 통과

```bash
uv run pytest -q
```

결과: `1187 passed, 1 warning in 55.48s`

남은 경고는 기존 `tests/test_error_handling.py::TestCrashRecording::test_not_disabled_below_threshold`의
`AsyncMockMixin._execute_mock_call` runtime warning이다.
