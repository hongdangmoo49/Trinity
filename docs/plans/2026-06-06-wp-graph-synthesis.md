# WP Graph Synthesis Hardening Plan

작성일: 2026-06-06

브랜치: `codex/wp-graph-synthesis`

## 목표

Central agent가 단순 blueprint만 만드는 구조에서 벗어나, 실행 가능한 WP graph를
함께 제안하도록 바꾼다. 로컬 Trinity runtime은 이 graph를 그대로 맹신하지 않고
dependency, 담당 agent, 파일 소유권, 병렬 실행 위험을 검증하고 보수화한다.

핵심 목표는 다음 문장이다.

> Central agent가 WP graph를 만들고 로컬 policy가 검증/보수화하는 구조.

## 현재 구조 요약

현재 workflow는 다음 순서로 동작한다.

1. Claude/Codex/Antigravity가 provider opinion을 낸다.
2. Central synthesis가 `recommended_blueprint`를 만든다.
3. `WorkflowEngine.mark_deliberation_result()`가 blueprint를 session에 저장한다.
4. `BlueprintDecomposer.decompose()`가 blueprint의 architecture/data_flow/risk 항목을
   기계적으로 WP seed로 바꾼다.
5. `ExecutionProtocol`과 `ParallelExecutionPolicy`가 dependency와 `expected_files`
   기반으로 병렬 batch를 만든다.

이 구조는 빠르게 동작하지만, 의미적 dependency와 hidden file collision을 central
reasoning 단계에서 충분히 다루지 못한다.

## 문제

| 문제 | 영향 |
| :--- | :--- |
| WP graph를 로컬 decomposer가 휴리스틱으로 생성 | central synthesis가 파악한 의미적 의존성이 WP에 반영되지 않음 |
| `expected_files`가 추정값 | 같은 config/lockfile/schema/shared type을 건드리는 충돌을 놓칠 수 있음 |
| dependency가 architecture name 기반 | 모델이 이미 알고 있는 순서/병렬성 판단을 잃음 |
| synthesis 기본 모델이 `fast` | WP graph처럼 중요한 구조화 판단에는 품질이 부족할 수 있음 |
| 병렬 policy가 최종 단계에서만 작동 | 실행 직전까지 위험한 graph를 사용자가 보기 어려움 |

## 설계 방향

### 1. Synthesis 모델 기본값 상향

`TrinityConfig.synthesis_model` 기본값을 `fast`에서 `strong`으로 바꾼다.
`TrinityOrchestrator._resolve_synthesis_model()`은 `strong`을 provider별 고성능 기본값으로
해석한다.

초기 provider별 strong map:

| Provider | strong 모델 |
| :--- | :--- |
| Codex | `gpt-5.4` |
| Claude Code | `opus` |
| Antigravity CLI | `default` |

기존 config에서 `synthesis_model = "fast"`를 명시한 사용자는 계속 fast를 쓸 수 있다.

### 2. Blueprint에 WP graph를 수용

`Blueprint` 모델에 `work_packages` 필드를 추가한다. Central synthesis output schema에도
`recommended_blueprint.work_packages`를 추가한다.

WP graph item 초안:

```json
{
  "id": "WP-001",
  "title": "string",
  "owner_agent": "codex|claude|antigravity",
  "objective": "string",
  "scope": ["string"],
  "out_of_scope": ["string"],
  "dependencies": ["WP-000 or package title"],
  "expected_files": ["path"],
  "acceptance_criteria": ["string"],
  "estimated_weight": 1,
  "parallel_group": 1,
  "parallelizable": true,
  "risk": "low|medium|high"
}
```

### 3. Decomposer를 WP graph 우선 구조로 변경

`BlueprintDecomposer.decompose()`는 blueprint에 central-proposed work packages가 있으면
그 graph를 우선 사용한다. 단, 다음 검증과 보수화를 적용한다.

- active agent가 아닌 owner는 active agent 중 적합한 agent로 재배정한다.
- 비어 있는 owner는 기존 focus/load-balance 로직으로 배정한다.
- id가 없거나 중복되면 `WP-001` 형식으로 재번호화한다.
- dependencies는 최종 package id로 정규화한다.
- 자기 자신 dependency와 존재하지 않는 dependency는 제거하고 `repair_notes`에 남긴다.
- `expected_files`가 비어 있는 workspace-write package는 보수적 placeholder를 붙여
  병렬 policy가 무분별하게 병렬화하지 못하게 한다.
- 위험도가 높은 package나 shared/global file을 건드리는 package는 더 보수적으로 직렬화한다.
- 중앙 원본 graph와 로컬 보수 graph는 Nexus/Report snapshot에서 분리해 보여준다.

### 4. 로컬 병렬 policy 강화

`ParallelExecutionPolicy`는 기존 file ownership overlap 검사에 다음 보수 규칙을 더한다.

- `pyproject.toml`, package lockfile, root config, shared schema/type 파일 등 global files는
  동일 workspace에서 다른 writer와 병렬 실행하지 않는다.
- `file_ownership`이 directory root처럼 너무 넓거나 비어 있으면 직렬화한다.
- central graph가 `parallelizable=false` 또는 high risk marker를 제공하면 같은 workspace
  writer와 병렬 실행하지 않는다.
- shared/broad path 목록은 `[execution]` config의
  `parallel_shared_write_paths`, `parallel_broad_write_paths`로 조정한다.

구현은 `WorkPackage`에 `parallel_group`, `parallelizable`, `risk`, `repair_notes`를 두고
실제 scheduling 단계에서는 `ExecutionScope`로 필요한 메타데이터를 전달하는 방식으로 정리한다.

## 작업 단위

1. 계획 문서 작성
2. synthesis 모델 기본값 상향
3. `Blueprint`/`WorkPackage` 모델에 central WP graph 필드 추가
4. `ModelBackedSynthesisAgent` output schema와 parser 확장
5. `BlueprintDecomposer`가 central WP graph를 우선 사용하고 로컬 검증/보수화
6. 병렬 policy에 global/shared file 보수 규칙 추가
7. 중앙 synthesis prompt에 WP graph 작성 지침과 예시 추가
8. smoke test로 request -> blueprint -> execute log 투영 경로 검증
9. 테스트와 운영 문서 갱신

## 검증 계획

- `tests/test_config.py`
- `tests/test_orchestrator.py`
- `tests/test_synthesis_agent.py`
- `tests/test_blueprint_decomposer.py`
- `tests/test_parallel_execution_policy.py`
- `tests/test_execution_protocol.py`
- 변경 파일 ruff check
- `git diff --check`

가능하면 마지막에 전체 `uv run pytest -q`를 실행한다.
