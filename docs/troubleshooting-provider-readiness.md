# Provider Readiness Troubleshooting

작성일: 2026-06-03

## 1. 개요

Trinity의 기본 transport는 one-shot이다. Claude Code, Codex, Antigravity CLI를
사용자 PC에 설치된 CLI와 기존 auth 상태로 호출한다. tmux transport를 사용할 때는
provider들이 인증 화면, 모델 선택 화면, banner, trust prompt를 일반 출력으로
보여줄 수 있다. `ProviderReadinessGate`는 이런 출력을 agent 답변으로 취급하지 않고,
deliberation 시작 전에 상태를 분류해 사용자 조치를 안내한다.

## 2. 증상별 빠른 판단

| 증상 | readiness state | 조치 |
|------|-----------------|------|
| OAuth URL, login code, invalid code가 보인다. | `auth_required` | `trinity bootstrap`에서 격리 provider-state 로그인 완료 |
| auth picker 또는 API key 선택 화면이 보인다. | `auth_required` | provider CLI에서 인증 방식 선택 및 계정/API key 설정 |
| 모델 이름, loading, initializing, default model banner만 보인다. | `model_loading` 또는 `cli_banner_only` | 초기화 완료까지 대기 후 재시도 |
| workspace trust/confirm prompt가 보인다. | `workspace_trust_required` | `trinity bootstrap`에서 해당 workspace를 신뢰/승인 |
| pane/process가 죽었거나 capture가 비어 있다. | `process_dead` 또는 `unknown_not_ready` | provider 재시작 또는 tmux session 재생성 |

## 3. 공통 진단 순서

WSL repo 기준으로 실행한다.

```bash
cd /home/zaemi/workspace/Trinity
uv run trinity bootstrap
uv run trinity status
uv run trinity
```

대화형 TUI 안에서는 다음을 확인한다.

```text
/status
/workflow
```

`/status`의 Readiness 열에 state, reason, action hint가 표시된다.

## 4. Claude Code

### 흔한 문제

- OAuth URL이 pane에 남아 있다.
- `Invalid code` 또는 browser login 안내가 반복된다.
- CLI가 prompt로 돌아오지 않고 auth flow에 머문다.

### 조치

```bash
uv run trinity bootstrap --agents claude
```

bootstrap tmux pane에서 Claude Code의 theme/auth/workspace prompt를 완료한다.

확인 기준:

- `claude` 실행 후 바로 입력 가능한 prompt가 나타난다.
- OAuth URL이나 login code 요청이 더 이상 뜨지 않는다.
- 프로젝트 workspace 권한 확인이 필요하면 완료한다.

## 5. Codex CLI

### 흔한 문제

- default model/banner 화면만 capture된다.
- 모델 초기화 문구가 agent 응답처럼 들어온다.
- WindowsApps 경로의 `codex`가 WSL에서 섞여 잡힌다.

### 조치

```bash
source ~/.nvm/nvm.sh
which codex
codex --version
uv run trinity bootstrap --agents codex
```

bootstrap tmux pane에서 Codex CLI의 login/trust prompt를 완료한다.

확인 기준:

- WSL 내부에서 의도한 Codex CLI가 실행된다.
- login이 완료되어 시작 시 auth prompt가 뜨지 않는다.
- 모델 초기화 또는 default model 선택 화면이 사라진 뒤 입력 가능한 prompt가 뜬다.

## 6. Antigravity CLI

### 흔한 문제

- `agy --print`가 auth/workspace trust 오류를 반환한다.
- Antigravity CLI 첫 실행의 브라우저/SSH OAuth 흐름이 완료되지 않았다.
- workspace trust prompt가 완료되지 않아 one-shot 호출이 실패한다.

### 조치

```bash
source ~/.nvm/nvm.sh
agy --version
agy
```

Antigravity CLI의 auth/workspace trust를 사용자 shell에서 먼저 완료한다.
Trinity는 `agy --print`를 통해 기존 사용자의 인증 상태를 그대로 사용한다.
기존 Gemini CLI 플러그인/설정을 옮겨야 하면 다음 명령으로 migration을 수행한다.

```bash
agy plugin import gemini
```

확인 기준:

- `agy --print "hello"`가 auth prompt 없이 응답한다.
- `uv run trinity status`에서 세 번째 agent가 `antigravity / antigravity-cli`로 표시된다.

## 7. strict/degraded mode

기본값은 strict mode다.

```toml
[deliberation]
provider_readiness_mode = "strict"
provider_readiness_timeout_seconds = 20.0
```

strict mode:

- 하나라도 not ready이면 deliberation을 시작하지 않는다.
- 사용자에게 provider별 reason과 action hint를 보여준다.

degraded mode:

```toml
[deliberation]
provider_readiness_mode = "degraded"
```

- ready agent가 하나 이상 있으면 ready agent만으로 진행한다.
- unavailable agent는 이번 deliberation에서 제외된다.

## 8. tmux/session 문제

tmux가 없거나 provider pane이 죽으면 interactive smoke는 신뢰할 수 없다.

```bash
tmux -V
tmux ls
```

필요하면 Trinity session을 종료한 뒤 다시 시작한다.

```bash
uv run trinity
```

## 9. shared.md가 오염된 경우

Provider banner/auth 화면이 예전 shared.md에 남아 있으면, v0.7.0 이후에는 source of truth를 `session.json`으로 본다.
workflow state 기준으로 shared ledger를 다시 렌더링할 수 있다.

관련 API:

```python
engine.sync_shared_ledger(shared, provider_readiness=readiness_results)
```

운영 원칙:

- `shared.md`는 사람이 읽는 요약이다.
- workflow 복구 기준은 `.trinity/workflow/session.json`과 `.trinity/workflow/events.jsonl`이다.

## 10. Smoke checklist

WSL native repo에서 확인한다.

```bash
cd /home/zaemi/workspace/Trinity
uv run trinity
```

필수 확인:

- Claude/Codex/Antigravity 모두 인증 완료 상태에서 설계 요청이 시작된다.
- Antigravity만 auth required 상태에서는 strict mode가 중단 이유를 표시한다.
- degraded mode에서는 ready agent만으로 workflow가 진행된다.
- Pending question이 생기면 다음 사용자 입력이 decision으로 기록된다.
- Execution intent 요청에서 work package가 dispatch되고 Task Results가 기록된다.
