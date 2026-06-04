# One-shot Provider 전환 구현 결과

- 작성일: 2026-06-04
- 브랜치: `codex/one-shot-provider-redesign`
- 기준 문서: `docs/plans/2026-06-04-one-shot-provider-redesign.md`

## 구현 완료

1. 사용자 auth 재사용 기본화
   - `provider_state_mode = "user-home"`를 기본값으로 추가했다.
   - 기본 실행에서는 `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`을 덮어쓰지 않는다.
   - `provider_state_mode = "isolated"`일 때만 기존 `.trinity/agents/<agent>/provider-state` managed home을 사용한다.
   - `trinity bootstrap` 문구는 isolated mode 전용 보조 도구로 정리했다.

2. 실행 권한/병렬 정책 추가
   - `ExecutionAuthority`를 `provider-managed`와 `trinity-managed`로 분리했다.
   - `InvocationAccess`를 `read-only`와 `workspace-write`로 분리했다.
   - 같은 worktree에서 둘 이상의 provider-managed write 호출을 병렬 실행하지 않도록 `ParallelExecutionPolicy`를 추가했다.
   - 별도 worktree 또는 명시적 파일 소유권이 있으면 병렬 write를 허용할 수 있게 했다.

3. One-shot provider invoker 계약 추가
   - `PromptRequest`
   - `ProviderTurnResult`
   - `ProviderInvoker`
   - `ClaudePrintInvoker`
   - `CodexExecInvoker`
   - `parse_codex_jsonl`

4. Claude/Codex print 경로 전환
   - Claude print mode는 `ClaudePrintInvoker`를 통해 `claude -p --output-format json`을 호출한다.
   - Codex print mode는 오래된 `codex -q` 대신 `codex exec --json --ephemeral --sandbox read-only --cd <repo>`를 사용한다.
   - Claude/Codex agent에 남아 있던 직접 subprocess/parser 메서드를 제거했다.

5. Antigravity/Gemini 전환 준비
   - `Provider.ANTIGRAVITY_CLI = "antigravity-cli"`를 추가했다.
   - 기본 config의 reviewer provider를 `gemini`에서 `antigravity`로 전환했다.
   - CLI detector가 `agy`, `antigravity` binary를 탐지한다.
   - Gemini CLI는 legacy provider로 유지하되 deprecation/migration 안내를 표시한다.
   - `agy plugin import gemini` migration 안내를 readiness/setup 경로에 추가했다.
   - Antigravity one-shot/headless prompt mode는 공식/로컬 검증 전이라 factory guard로 막아두었다.

6. 기본 deliberation transport one-shot 전환
   - `transport_mode = "one-shot"`를 기본 설정으로 추가했다.
   - `uv run trinity` TUI 경로는 더 이상 `tmux` 설치 여부만으로 에이전트 tmux 세션을 만들지 않는다.
   - `transport_mode = "tmux"`를 명시한 경우에만 legacy tmux agent transport를 사용한다.
   - `trinity ask -i/--interactive`는 호환을 위해 tmux transport 강제 옵션으로 유지했다.
   - `trinity status`와 TUI `/status`에서 현재 transport를 표시한다.

7. 중앙 synthesis 계약 추가
   - `SynthesisInput`, `SynthesisResult`, `SynthesisAgent` 계약을 추가했다.
   - 기존 `StructuredConsensusSynthesizer`와 keyword consensus를 `HeuristicSynthesisAgent` 뒤로 이동했다.
   - provider-backed synthesizer가 실패할 때 deterministic fallback을 사용할 수 있도록 `FallbackSynthesisAgent`를 추가했다.
   - `DeliberationProtocol`은 round 응답 수집 직후 중앙 synthesis agent를 호출한다.
   - 각 라운드 합성 결과는 `shared.md`의 `Round N Synthesis` 섹션에 기록한다.
   - 기존 workflow 연동을 유지하기 위해 `metadata["structured_consensus"]`를 계속 제공하고, 신규 `metadata["synthesis"]`를 추가했다.

8. `shared.md` synthesis 중심 구조 전환
   - protocol 경로에서 clean 응답 본문 전체를 `Round N Opinions`에 누적하지 않도록 변경했다.
   - `Round N Responses`에는 agent별 `request_id`, status, token, confidence, raw/clean artifact path만 기록한다.
   - 다음 라운드 prompt context는 `Round N Synthesis`를 우선 사용하고, legacy `Round N Opinions`는 fallback으로만 사용한다.
   - 압축 비활성 경로에서는 기존 `Round N Summary` 압축 결과를 잘못 재사용하지 않도록 `include_compressed_summaries` 옵션을 추가했다.

## 제거/정리

- `PrintModeClaudeAgent._run_subprocess`
- `PrintModeClaudeAgent._parse_response`
- `PrintModeClaudeAgent._build_prompt`
- `CodexAgent._run_subprocess`
- `CodexAgent._parse_response`
- Codex의 오래된 `codex -q` 실행 경로

tmux, completion detector, Gemini legacy agent는 아직 제거하지 않았다. interactive/debug 호환과 legacy Gemini config 지원에 여전히 사용된다.

## 검증

전체 테스트:

```text
uv run pytest
951 passed, 1 warning in 19.67s
```

경고는 기존 테스트 mock coroutine 미await warning이며 이번 변경 실패는 아니다.

## 남은 작업

- Antigravity CLI가 공식적으로 one-shot/headless prompt와 machine-readable output을 제공하는지 확인 후 `AntigravityInvoker` 구현.
- provider-managed write execution을 실제 workflow execution scheduler에 연결.
