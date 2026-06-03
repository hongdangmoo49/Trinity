# Provider Readiness Troubleshooting

작성일: 2026-06-03

## 1. 개요

Trinity interactive mode는 Claude Code, Codex, Gemini CLI를 tmux pane에서 지속 실행한다.
이 provider들은 인증 화면, 모델 선택 화면, banner, trust prompt를 일반 출력으로 보여줄 수 있다.
v0.7.0의 `ProviderReadinessGate`는 이런 출력을 agent 답변으로 취급하지 않고,
deliberation 시작 전에 상태를 분류해 사용자 조치를 안내한다.

## 2. 증상별 빠른 판단

| 증상 | readiness state | 조치 |
|------|-----------------|------|
| OAuth URL, login code, invalid code가 보인다. | `auth_required` | provider CLI를 직접 실행해 로그인 완료 |
| auth picker 또는 API key/Vertex AI 선택 화면이 보인다. | `auth_required` | 인증 방식 선택 및 계정/API key 설정 |
| 모델 이름, loading, initializing, default model banner만 보인다. | `model_loading` 또는 `cli_banner_only` | 초기화 완료까지 대기 후 재시도 |
| workspace trust/confirm prompt가 보인다. | `workspace_trust_required` | 해당 workspace를 신뢰/승인 |
| pane/process가 죽었거나 capture가 비어 있다. | `process_dead` 또는 `unknown_not_ready` | provider 재시작 또는 tmux session 재생성 |

## 3. 공통 진단 순서

WSL repo 기준으로 실행한다.

```bash
cd /home/zaemi/workspace/Trinity
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
claude auth
claude doctor
claude --version
claude
```

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
codex doctor
codex login
codex --version
codex
```

확인 기준:

- WSL 내부에서 의도한 Codex CLI가 실행된다.
- login이 완료되어 시작 시 auth prompt가 뜨지 않는다.
- 모델 초기화 또는 default model 선택 화면이 사라진 뒤 입력 가능한 prompt가 뜬다.

## 6. Gemini CLI

### 흔한 문제

- auth picker가 pane에 남아 있다.
- Vertex AI env missing, API key missing 화면이 보인다.
- 인증 방식을 선택하지 못해 prompt가 반환되지 않는다.

### 조치

```bash
source ~/.nvm/nvm.sh
gemini --version
gemini
```

Gemini CLI 안에서 사용할 인증 방식을 완료한다.
Vertex AI를 쓸 경우 필요한 environment variable을 WSL shell에 설정한다.
API key 방식을 쓸 경우 CLI가 기대하는 설정 위치에 key를 등록한다.

확인 기준:

- `gemini` 시작 시 auth picker가 더 이상 나타나지 않는다.
- prompt 입력이 가능한 상태로 진입한다.

## 7. strict/degraded mode

기본값은 strict mode다.

```toml
[deliberation]
provider_readiness_mode = "strict"
provider_readiness_timeout_seconds = 5.0
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

- Claude/Codex/Gemini 모두 인증 완료 상태에서 설계 요청이 시작된다.
- Gemini만 auth required 상태에서는 strict mode가 중단 이유를 표시한다.
- degraded mode에서는 ready agent만으로 workflow가 진행된다.
- Pending question이 생기면 다음 사용자 입력이 decision으로 기록된다.
- Execution intent 요청에서 work package가 dispatch되고 Task Results가 기록된다.
