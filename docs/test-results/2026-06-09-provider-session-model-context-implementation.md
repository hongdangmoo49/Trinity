# Provider Session and Model Context Implementation

- 작성일: 2026-06-09
- 브랜치: `feature/provider-session-model-context-design`
- 기준 설계: `docs/plans/2026-06-09-provider-session-model-context-design.md`

## 작업 범위

이번 작업은 provider CLI가 반환하거나 로그에 남기는 native session id와 runtime model 정보를 Trinity workflow에 연결하는 기반을 구현했다.

핵심 목표:

1. Claude, Codex, Antigravity의 provider-native session id를 관측한다.
2. 실제 모델명과 context window 근거를 `configured_model`과 분리한다.
3. 관측값을 `WorkflowSession`에 저장하고 `/resume` 이후에도 복원한다.
4. 다음 read-only deliberation/review 호출에서 저장된 provider session id를 명시적으로 이어간다.
5. UI inspector와 report export에 provider model/session 정보를 표시한다.

## 구현 내용

### Provider metadata model

`WorkflowSession`에 다음 필드를 추가했다.

- `provider_sessions: dict[str, ProviderSessionRef]`
- `runtime_models: dict[str, AgentRuntimeModel]`

`ProviderSessionRef`는 provider-native id를 저장한다.

- Claude: `session_id`
- Codex: JSONL `thread.started.thread_id`
- Antigravity: per-call log의 `conversation=<uuid>`

`AgentRuntimeModel`은 model 관측값과 context budget 근거를 저장한다.

- `configured_model`
- `actual_model`
- `model_label`
- `context_window`
- `budget_source`
- `confidence`

### Provider parser

Claude:

- print JSON의 `session_id`를 `provider_session` metadata로 저장한다.
- `modelUsage`에서 actual model, `contextWindow`, `maxOutputTokens`를 읽는다.

Codex:

- JSONL `thread.started.thread_id`를 파싱한다.
- JSONL에 model field가 없으면 `~/.codex/config.toml`과 `~/.codex/models_cache.json`를 사용해 default model과 context window를 해석한다.
- `codex exec` prompt는 argv 대신 stdin으로 전달한다. command의 prompt 위치에는 `-`를 둔다.

Antigravity:

- stdout은 plain text로 유지한다.
- `--log-file`을 통해 per-call log를 지정한다.
- log에서 `conversation=<uuid>`, `label="..."`, `backend=...`를 파싱한다.
- stdin prompt 계약은 확인되지 않아 positional argv 전달을 유지한다.

### Provider continuation

Agent wrapper는 provider 응답에서 관측한 session id를 기억하고 다음 request에 싣는다.

Textual workflow는 저장된 `WorkflowSession.provider_sessions`를 deliberation/review orchestrator에 주입한다.

Continuation command 정책:

```bash
claude --resume <session_id> -p --output-format json ...
codex exec resume <thread_id> --json --skip-git-repo-check -
agy --conversation <conversation_id> --log-file <path> --print ...
```

Codex execution lane은 아직 `exec resume`을 사용하지 않는다. `workspace-write` 호출은 cwd/sandbox contract가 더 필요하므로 stateless command로 유지한다.

### UI and report

Nexus snapshot은 provider별 다음 정보를 포함한다.

- configured model
- actual model 또는 model label
- context window
- budget source
- provider session id
- session kind

Workflow inspector는 `Providers` 섹션을 추가해 model/context/session short id를 표시한다.

Markdown report export도 `## Providers` 섹션을 추가한다.

## 검증

실행한 테스트:

```bash
uv run pytest tests/test_provider_invoker_claude.py \
  tests/test_provider_invoker_codex.py \
  tests/test_provider_invoker_antigravity.py \
  tests/test_workflow_persistence.py \
  tests/test_workflow_engine.py

uv run pytest tests/test_provider_invoker_claude.py \
  tests/test_provider_invoker_codex.py \
  tests/test_provider_invoker_antigravity.py \
  tests/test_claude_agent.py \
  tests/test_codex_agent.py \
  tests/test_antigravity_agent.py \
  tests/test_orchestrator.py \
  tests/test_textual_workflow_controller.py

uv run pytest tests/test_platform_process.py \
  tests/test_provider_invoker_codex.py \
  tests/test_codex_agent.py

uv run pytest tests/test_textual_snapshot.py \
  tests/test_textual_app.py \
  tests/test_textual_smoke.py \
  tests/test_report.py
```

모든 테스트가 통과했다.

## 제한 사항

- Antigravity context window는 provider가 machine-readable하게 노출하지 않아 unknown으로 둔다.
- Antigravity stdin prompt 전달은 공식 문서와 로컬 help에서 확인되지 않아 적용하지 않았다.
- Codex execution lane resume은 cwd/sandbox 적용 방식이 더 검증되기 전까지 비활성화한다.
- Synthesis provider 호출은 별도 provider-native continuation을 쓰지 않는다.
