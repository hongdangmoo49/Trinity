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
   - Antigravity one-shot/headless prompt mode는 로컬 `agy 1.0.5` help와 smoke test로 검증했다.

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

9. Workflow execution scheduler 병렬 정책 연결
   - `ExecutionProtocol`이 dependency-ready work package를 바로 전체 병렬 실행하지 않고 `ParallelExecutionPolicy` batch 단위로 실행한다.
   - 실행 work package는 provider-managed `workspace-write` invocation으로 분류한다.
   - 같은 `launch_cwd`의 provider-managed write package는 순차 실행한다.
   - 별도 worktree이거나 `expected_files`가 disjoint file ownership을 제공하면 병렬 실행을 허용한다.

10. Antigravity one-shot provider 구현
   - `AntigravityPrintInvoker`가 `agy --print-timeout=<N>s --sandbox --print <prompt>`를 호출한다.
   - print mode는 plain stdout만 제공하므로 `metadata["output_format"] = "plain-text"`로 기록하고 token usage는 비워둔다.
   - `--dangerously-skip-permissions`는 자동 부여하지 않고 사용자가 agent `extra_args`로 명시한 경우에만 전달한다.
   - `AntigravityPrintAgent`를 추가하고 factory print mode에서 `antigravity-cli` provider를 생성할 수 있게 했다.
   - setup detector의 Antigravity experimental warning을 제거하고, readiness 안내를 `agy --print` one-shot 기준으로 갱신했다.

11. tmux legacy/debug cleanup audit
   - 실제 legacy tmux transport는 `TmuxSessionManager`, `TmuxPane`, completion detector chain, provider bootstrap 경로에서 계속 사용되므로 유지했다.
   - current runtime에서 import되지 않고 테스트만 붙잡고 있던 `trinity.tmux.layout.TUILayout`을 고아 컴포넌트로 판단해 제거했다.
   - `tests/test_tmux_layout.py`도 해당 고아 모듈 전용 테스트라 함께 제거했다.

12. tmux legacy transport 명시화
   - CLI/TUI transport label을 `interactive (tmux)`에서 `legacy tmux`로 바꿔 기본 one-shot 경로와 구분했다.
   - `trinity ask -i` 또는 `transport_mode = "tmux"` 사용 시 legacy tmux transport notice를 출력한다.
   - `trinity attach`는 더 이상 기본 one-shot config에서 tmux attach를 시도하지 않고, `transport_mode = "tmux"`일 때만 legacy session attach를 실행한다.

13. tmux legacy namespace 분리
   - 실제 tmux 구현을 `trinity.legacy.tmux`로 이동했다.
   - runtime import는 `trinity.legacy.tmux.pane.TmuxPane`과 `trinity.legacy.tmux.session.TmuxSessionManager`를 직접 참조한다.
   - 기존 `trinity.tmux.*` import는 외부 호환을 위해 얇은 shim으로 유지했다.
   - `tests/test_tmux.py`는 legacy namespace 구현을 직접 검증하고, shim re-export 호환도 확인한다.

## 제거/정리

- `PrintModeClaudeAgent._run_subprocess`
- `PrintModeClaudeAgent._parse_response`
- `PrintModeClaudeAgent._build_prompt`
- `CodexAgent._run_subprocess`
- `CodexAgent._parse_response`
- Codex의 오래된 `codex -q` 실행 경로
- Antigravity print-mode factory guard
- Antigravity experimental setup warning
- `src/trinity/tmux/layout.py`
- `tests/test_tmux_layout.py`

`TmuxSessionManager`, `TmuxPane`, completion detector, Gemini legacy agent는 제거하지 않았다. `TmuxSessionManager`와 `TmuxPane`의 실제 구현은 `trinity.legacy.tmux`로 이동했고, interactive/debug 호환, provider bootstrap, legacy Gemini config 지원에 여전히 사용된다.

## 검증

Antigravity 로컬 smoke:

```text
agy --version
1.0.5

agy --print-timeout=10s --print "Return exactly: TRINITY_AGY_SMOKE"
TRINITY_AGY_SMOKE

agy --print-timeout=10s --sandbox --print "Return exactly: TRINITY_AGY_SANDBOX_SMOKE"
TRINITY_AGY_SANDBOX_SMOKE
```

관련 테스트:

```text
uv run pytest tests/test_provider_invoker_antigravity.py tests/test_antigravity_agent.py tests/test_agent_factory.py tests/test_cli_detector.py tests/test_provider_readiness.py tests/test_config.py
90 passed in 0.15s

uv run pytest tests/test_cli.py tests/test_cli_v2.py tests/test_tui_session.py tests/test_config.py
124 passed in 0.81s

uv run pytest tests/test_tmux.py tests/test_completion.py tests/test_interactive_claude.py tests/test_tmux_integration.py tests/test_provider_bootstrap.py tests/test_orchestrator.py tests/test_agent_factory.py
135 passed in 3.87s
```

전체 테스트:

```text
uv run pytest
951 passed, 1 warning in 19.71s
```

경고는 기존 테스트 mock coroutine 미await warning이며 이번 변경 실패는 아니다.

## 남은 작업

- Antigravity CLI 공식 웹 문서에 `--print`/`--prompt` 플래그와 machine-readable output이 추가되는지 지속 확인한다. 현재 구현은 로컬 CLI help/smoke로 검증한 plain stdout path다.
- Gemini legacy agent를 deprecated/optional namespace로 분리할지 결정한다.
