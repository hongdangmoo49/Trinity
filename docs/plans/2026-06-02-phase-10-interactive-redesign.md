# Phase 10: Interactive Provider Redesign and Reliability Plan

작성일: 2026-06-02

## 배경

실사용에서 `uv run trinity` 대화형 TUI가 5라운드까지 진행한 뒤 강제 결론을 만들었지만,
실제 agent 답변 대신 CLI 배너, prompt echo, 인증 대기, 모델 상태 UI, shared.md 요약이 결과로
표시되었다.

관찰된 대표 증상:

- Claude 결과에 `## Round 1 Summary`, `After completing your response`, `sandbox no sandbox` 같은 prompt/shared context echo가 섞임.
- Codex 결과에 `model: loading`, `/model to change`, `gpt-5.5 default` 같은 CLI 상태만 표시됨.
- Gemini 결과에 `Thinking...`, `Waiting for authentication`, `Shift+Tab to accept edits` 같은 UI 상태가 표시됨.
- 합의에 실패한 뒤 `Forced conclusion after 5 rounds`가 실제 결론처럼 표시됨.
- 토큰 사용량이 `0`으로 표시되어 context/rotation 판단 근거가 없음.

이 문제는 단순 TUI 렌더링 문제가 아니다. provider별 입출력 계약, 완료 감지, 응답 추출,
shared context 쓰기 전 검증이 모두 약해서 생긴 구조적 결함이다.

## 현재 구조 요약

현재 실행 흐름:

```text
InteractiveSession
  -> TrinityOrchestrator(interactive=True)
    -> TmuxSessionManager creates panes
    -> AgentFactory creates provider adapters
    -> DeliberationProtocol
      -> agent.send_and_wait(prompt)
      -> SharedContextEngine.append_opinion(raw response)
      -> ConsensusEngine keyword evaluation
      -> TaskDistributor creates task descriptions
```

핵심 파일:

- `src/trinity/orchestrator.py`: 전체 component 생성, agent 시작, protocol 실행.
- `src/trinity/deliberation/protocol.py`: 라운드 루프, shared.md 기록, 합의 판정, 작업 분배.
- `src/trinity/agents/claude_agent.py`: Claude print/interactive adapter.
- `src/trinity/agents/codex_agent.py`: Codex print/interactive adapter.
- `src/trinity/agents/gemini_agent.py`: Gemini print/interactive adapter.
- `src/trinity/completion/*`: Hook, prompt return, idle 기반 완료 감지.
- `src/trinity/context/shared.py`: shared.md section CRUD.
- `src/trinity/tui/*`: Rich Live TUI와 prompt_toolkit 입력.

## 우선순위 개선안

### P0. 테스트 기준선 복구

현재 `RetryConfig.get_delay()`는 `max_delay`로 cap한 뒤 jitter를 적용한다.
따라서 jitter 때문에 최종 delay가 `max_delay`를 초과할 수 있다.

수정 방향:

- jitter 적용 후 다시 `min(delay, max_delay)`를 적용한다.
- `uv run pytest tests/ -q` 기준선을 green으로 복구한다.

완료 기준:

- `tests/test_retry.py::TestGetDelay::test_capped_at_max_delay` 통과.
- 전체 테스트 통과.

### P0. Codex interactive prompt 전송 누락 수정

`CodexAgent.send_and_wait()` interactive branch는 `full_prompt`를 만들지만 pane에 전송하지 않고
바로 completion detector를 기다린다. 이 상태에서는 Codex가 실제 요청을 받지 못한다.

수정 방향:

- `self._pane.send_text_heredoc(full_prompt)`를 완료 감지 전에 호출한다.
- 전송 직전 pane line boundary 또는 request id를 기록한다.
- 전송된 prompt echo와 실제 답변을 분리할 수 있는 extraction boundary를 저장한다.

완료 기준:

- Codex interactive unit test가 prompt 전송을 검증한다.
- Codex TUI 결과에 CLI status banner가 아닌 실제 응답 본문이 표시된다.

### P0. 짧은 idle timeout을 완료 판정에서 제거

현재 Claude 10초, Codex 15초, Gemini 20초 idle detector가 completion chain에 포함되어 있다.
이 값은 단일 고품질 답변 생성 시간보다 짧고, provider가 도구 사용 또는 추론 중 잠시 출력하지 않는
상태를 "완료"로 오판한다.

정책 변경:

- idle은 completion signal이 아니라 progress/stall signal로만 사용한다.
- 정상 완료는 provider-specific done signal, prompt return, explicit sentinel, subprocess exit,
  또는 provider session state로 판정한다.
- 사용자가 원하면 무제한 대기한다.
- 단, 완전 무제한 blocking은 운영상 위험하므로 user cancel, provider process death, auth wait,
  no-prompt-sent, no-output-for-very-long watchdog은 유지한다.

권장 timeout 모델:

```text
completion_timeout: none by default
stall_warning_after: 120s
auth_wait_warning_after: 30s
hard_timeout: disabled by default, configurable
user_cancel: always available
```

완료 기준:

- `Thinking...` 중인 Gemini를 완료로 간주하지 않는다.
- Claude가 도구 사용 중 10초간 조용해도 응답을 캡처하지 않는다.
- TUI는 "대기 중"과 "완료"를 분리해서 표시한다.

### P0. shared.md 쓰기 전 응답 검증 추가

현재 protocol은 agent 응답을 그대로 shared.md에 기록한다. 한번 오염된 shared.md는 다음 라운드
prompt에 들어가고, 다시 echo되어 오염이 증폭된다.

수정 방향:

- provider adapter가 `AgentResponse` 형태로 `content`, `raw_output`, `status`, `confidence`,
  `noise_flags`를 반환하도록 확장한다.
- `SharedContextEngine.append_opinion()` 호출 전 response validator를 통과시킨다.
- CLI banner/auth/model-loading/prompt echo 비율이 높으면 shared.md에 opinion으로 기록하지 않는다.
- invalid response는 별도 `## Round N Diagnostics` 또는 log에 기록한다.

완료 기준:

- shared.md의 `Round N Opinions`에는 agent의 실제 의견만 들어간다.
- CLI UI noise는 diagnostics/log로 분리된다.

### P1. language detection bug 수정

config loader는 role prompt에서 한국어를 감지하지만, return 시 감지된 `lang`이 아니라
`general.get("lang", "en")`을 사용한다.

수정 방향:

- return field를 `lang=lang`으로 바꾼다.
- 기존 `.trinity/trinity.config`에 `lang`이 없어도 한국어 role prompt면 Korean round prompt를 사용한다.

완료 기준:

- 기존 Korean config 로드 시 `TrinityConfig.lang == "ko"`.

### P1. task distribution과 execution 분리

현재 TaskDistributor는 agent별 task description만 만든다. 실제로 agent에게 후속 작업을 주입해
실행시키는 단계가 없다.

수정 방향:

- `TaskPlan` 생성 단계와 `TaskExecution` 단계를 분리한다.
- 사용자가 "설계만" 요청한 경우에는 실행하지 않는다.
- 사용자가 "구현/수정"을 요청한 경우에는 합의 후 agent별 실행 prompt를 전송한다.
- 실행 결과도 shared.md에 opinion이 아니라 `Task Results`로 기록한다.

완료 기준:

- consensus 이후 task가 실제 agent call로 이어지는지 테스트한다.
- "설계 요청"은 문서/설계 결과로 끝나고, "구현 요청"만 실행으로 이어진다.

### P1. context rotation을 round loop 내부로 이동

현재 rotation check는 protocol 종료 뒤 한 번만 실행된다. 긴 deliberation 중 context가 초과되어도
중간 보호가 없다.

수정 방향:

- 각 agent response 수신 후 usage를 갱신한다.
- 다음 prompt 전송 전 `TokenBudgetChecker`를 실행한다.
- 위험하면 해당 agent를 먼저 summarize/rotate한 뒤 다음 라운드를 진행한다.

완료 기준:

- round 중간 또는 다음 round 시작 전에 rotation이 발생할 수 있다.
- rotation broadcast가 실제 다음 prompt에 포함된다.

### P2. analytics persistence 구현

`trinity analytics`는 새 orchestrator를 만들고 memory-only analytics를 조회한다.
따라서 이전 deliberation 결과를 볼 수 없다.

수정 방향:

- analytics history를 `.trinity/history/analytics.jsonl`에 저장한다.
- CLI `analytics`는 파일에서 최근 session 또는 전체 summary를 읽는다.

완료 기준:

- TUI 종료 후에도 `trinity analytics`가 직전 deliberation token/round 정보를 표시한다.

### P2. ManagedHome, WorkspaceIsolation, ErrorHandler 연결

관련 모듈은 있지만 orchestrator 기본 실행 경로에 연결되어 있지 않다.

수정 방향:

- agent 생성 시 workspace_mode에 따라 worktree를 선택한다.
- managed home env를 subprocess/tmux launch에 적용한다.
- health/error monitoring을 interactive session lifecycle에 연결한다.

완료 기준:

- `workspace_mode = "git-worktree"`가 실제 agent cwd로 반영된다.
- provider state가 `.trinity/agents/<name>/provider-state` 아래에 생성된다.
- agent process death가 TUI status와 recovery path로 이어진다.

## Phase 10 재설계 원칙

### 1. tmux는 transport, protocol은 provider adapter가 소유

tmux pane text를 "답변"으로 직접 해석하면 provider UI 변화에 취약하다.
tmux는 입출력 transport로만 보고, 완료 판정과 응답 추출은 provider adapter가 책임져야 한다.

### 2. 완료 판정은 idle이 아니라 명시적 상태 전이

완료 상태는 다음 중 하나로만 판정한다.

- print/subprocess mode: process exit.
- Claude interactive: hook signal 또는 prompt return with request boundary.
- Codex interactive: session state/event file 또는 prompt return with request boundary.
- Gemini interactive: explicit sentinel detection 또는 prompt return after sentinel.

idle은 "출력이 잠시 없음"일 뿐 "완료"가 아니다.

### 3. prompt echo와 response를 분리하는 request boundary 필수

모든 interactive request에는 request id를 부여한다.

예시:

```text
[TRINITY_REQUEST_START id=...]
...
[TRINITY_REQUEST_END id=...]
```

adapter는 pane output에서 request id 주변의 echo를 제거하고, sentinel 이후 또는 prompt return 이전의
본문만 추출해야 한다.

주의:

- provider가 sentinel을 그대로 출력하지 않을 수 있다.
- provider UI가 줄바꿈/자동완성/queued text를 삽입할 수 있다.
- 따라서 line-count boundary, sentinel, prompt return, cleaner를 조합해야 한다.

### 4. raw output과 clean response를 분리 저장

디버깅 가능성을 위해 raw output은 보존하되, shared context에는 clean response만 기록한다.

권장 구조:

```text
.trinity/logs/provider/<agent>/<request-id>.raw.txt
.trinity/logs/provider/<agent>/<request-id>.clean.txt
.trinity/shared.md
```

### 5. TUI timeout은 completion timeout이 아니다

사용자가 지적한 대로 10초/20초는 단일 요청 답변 시간으로 너무 짧다.
기본 동작은 provider가 계속 작업 중이면 기다리는 것이 맞다.

다만 다음 safety guard는 필요하다.

- 사용자가 언제든 취소할 수 있어야 한다.
- auth 대기, model loading, crashed pane은 답변 대기와 다르게 표시해야 한다.
- 매우 긴 무출력은 "완료"가 아니라 "stalled?"로 표시하고 계속 기다릴지 사용자에게 맡긴다.

즉, timeout은 품질 좋은 답변을 자르는 장치가 아니라 장애 상태를 드러내는 관측 장치여야 한다.

## 다른 에이전트 제안 검토

### 동의하는 부분

- Claude prompt echo가 응답으로 섞인다는 진단은 타당하다.
- shared.md 내용이 다음 prompt에 들어가고 다시 echo되어 오염이 증폭된다는 진단도 맞다.
- Gemini가 아직 thinking 중인데 idle로 완료 감지되는 문제는 실제 증상과 일치한다.
- idle timeout이 completion detector로 쓰이기에는 너무 짧다는 지적은 맞다.
- TaskDistributor가 보일러플레이트 task를 만드는 문제도 맞다.

### 보완해야 할 부분

- "tmux paste-buffer 방식이라 패치로 어렵다"는 결론은 과하다. tmux를 유지하더라도 provider별
  request boundary, sentinel, prompt return, raw/clean 분리, response validation을 도입하면
  안정성을 크게 개선할 수 있다.
- Codex 문제의 가장 직접적인 원인은 interactive branch가 prompt를 전송하지 않는 코드 결함이다.
  completion detector만의 문제가 아니다.
- Gemini marker는 prompt에 추가되지만 detector가 검사하지 않는다는 지적은 맞다. 해결은
  marker-aware detector 또는 prompt-return-after-marker 정책이다.
- "타임아웃이 필요 없다"는 방향은 품질 면에서 맞지만, 운영상 watchdog은 필요하다. 핵심은
  짧은 timeout으로 완료 처리하지 않는 것이지, 장애 감지를 모두 제거하는 것이 아니다.
- 문서/버전/테스트 불일치, language detection bug, analytics persistence 부재는 해당 제안에
  빠져 있으나 실제 프로젝트 신뢰도에 영향을 주는 별도 핵심 이슈다.

## 권장 작업 순서

1. 테스트 기준선 복구: retry jitter cap 수정.
2. Codex interactive prompt 전송 누락 수정.
3. idle detector를 completion chain에서 제거하거나 completion이 아닌 stall warning으로 변경.
4. Gemini marker-aware completion detector 추가.
5. Claude/Codex/Gemini response extraction에 request boundary와 validator 추가.
6. shared.md 오염 방지: invalid response를 diagnostics로 분리.
7. config language detection bug 수정.
8. context rotation을 round loop 내부로 이동.
9. analytics persistence 추가.
10. task plan과 task execution 단계를 분리.

## 성공 기준

Phase 10은 다음 조건을 만족해야 완료로 본다.

- `uv run trinity` interactive mode에서 세 provider 모두 실제 답변 본문만 표시한다.
- provider가 아직 thinking/auth/model-loading 상태이면 완료로 처리하지 않는다.
- shared.md에 CLI UI noise가 기록되지 않는다.
- forced conclusion이 실제 consensus처럼 과장 표시되지 않는다.
- token usage가 0으로 고정되지 않는다.
- 전체 테스트가 통과한다.
- 최소 하나의 실제 interactive smoke test 결과를 `docs/test-results/phase-10-T.md`에 기록한다.
