# Execution Failure Hardening

작성일: 2026-06-06

브랜치: `codex/execution-matrix-hardening`

## 문제

Textual Execution Matrix에서 여러 work package가 `failed` 또는 `blocked`로 표시됐지만,
화면에는 직접 원인이 보이지 않았다.

실제 raw 결과 기준 원인은 다음과 같았다.

- Codex: target workspace가 trusted git directory가 아니어서
  `--skip-git-repo-check` 요구와 함께 종료.
- Claude: execution package가 300초 timeout에 걸림.
- Antigravity: 일부 package에서 exit code 0과 빈 stdout을 반환해 raw artifact가
  0바이트로 남음.
- Parser: `## Blockers 없음.`을 blocker로 오인해 실제 완료 결과를 blocked/failed
  fallback 집계에 포함.

## 수정

- `codex exec` 호출에 `--skip-git-repo-check`를 기본 포함했다. target workspace는
  Trinity preflight를 통과한 명시적 구현 대상이므로 Codex의 git trust check가
  execution을 막지 않게 했다.
- planning round timeout과 execution package timeout을 분리했다.
  `execution_timeout_seconds` 기본값은 1800초이며 설정 파일에서 조정할 수 있다.
- execution response parser가 한국어 non-blocker 표현(`없음`, `해당 없음`,
  `문제 없음`, `블로커 없음`, `차단 없음`)을 빈 blocker로 처리하도록 보강했다.
- Antigravity가 빈 stdout을 반환하면 raw artifact에
  `[Empty response from Antigravity CLI]`와 `empty_response` 진단을 남긴다.
- Textual Execution Matrix 로그가 failed/blocked result의 첫 blocker 또는 summary를
  함께 표시한다.

## 검증

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_provider_invoker_codex.py tests/test_provider_invoker_antigravity.py tests/test_execution_protocol.py tests/test_config.py tests/test_orchestrator.py tests/test_textual_snapshot.py -q
```

결과:

```text
97 passed in 0.91s
```

```bash
/home/zaemi/.local/bin/uvx ruff check src/trinity/config.py src/trinity/orchestrator.py src/trinity/providers/invoker.py src/trinity/workflow/execution.py src/trinity/textual_app/snapshot.py tests/test_provider_invoker_codex.py tests/test_provider_invoker_antigravity.py tests/test_execution_protocol.py tests/test_config.py tests/test_orchestrator.py tests/test_textual_snapshot.py
```

결과:

```text
All checks passed!
```

```bash
python3 -m py_compile src/trinity/config.py src/trinity/orchestrator.py src/trinity/providers/invoker.py src/trinity/workflow/execution.py src/trinity/textual_app/snapshot.py
```

결과: 통과.

```bash
/home/zaemi/.local/bin/uv run pytest -q
```

결과:

```text
1163 passed, 1 warning in 52.31s
```

남은 경고는 기존 AsyncMock runtime warning 계열이다.
