# Fake Provider 테스트 환경

Trinity의 provider 연동 테스트는 실제 Claude/Codex/Antigravity 계정이나 토큰을 쓰지 않는다. 계정, 쿠키, API 키를 테스트 환경에 제공하지 말고, 이 문서의 fake CLI harness로 provider 동작을 재현한다.

## 목적

- `claude`, `codex`, `agy` 바이너리가 설치된 것처럼 보이는 격리된 테스트 환경을 만든다.
- `--version`, 모델 탐색, one-shot 호출, provider 로그 파일 생성을 실제 Trinity 경로와 같은 방식으로 검증한다.
- 인증 실패, probe 실패, 빈 응답, 모델 탐색 실패 같은 오류 상태를 환경 변수로 재현한다.
- 호출 인자, stdin, cwd, fake 시나리오를 JSONL 로그로 남겨 UI/preflight/orchestrator 테스트에서 검증할 수 있게 한다.

## 위치

- Harness: `tests/harness/fake_providers.py`
- 기본 검증 테스트: `tests/test_fake_provider_harness.py`

테스트에서 `install_fake_provider_clis(tmp_path / "fake-providers")`를 호출하면 임시 `bin` 디렉터리에 다음 실행 파일이 생성된다.

- `claude`
- `codex`
- `agy`

반환되는 `FakeProviderCLIs` 객체는 실행 파일 경로, fake `PATH`, 공용 JSONL 호출 로그를 제공한다.

## 기본 사용법

```python
from tests.harness.fake_providers import install_fake_provider_clis


def test_provider_flow(tmp_path):
    fake = install_fake_provider_clis(tmp_path / "fake-providers")
    env = fake.env()

    # AgentSpec.cli_command 에는 fake.codex 같은 절대 경로를 넣거나,
    # env["PATH"] 를 적용한 뒤 "codex" 명령명을 사용할 수 있다.
    assert fake.codex.exists()
```

`fake.env()`는 다음 값을 포함한다.

- `PATH`: fake `bin` 디렉터리를 맨 앞에 둔 PATH
- `TRINITY_FAKE_PROVIDER_LOG`: provider 호출 기록 JSONL 경로

## 지원하는 provider 동작

Claude fake CLI:

- `claude --version`
- `claude -p --output-format json ...`
- JSON 출력의 `result`, `session_id`, `model`, `usage`, `modelUsage`

Codex fake CLI:

- `codex --version`
- `codex debug models`
- `codex debug models --bundled`
- `codex exec --json ... -`
- JSONL 출력의 `thread.started`, `item.completed`, `turn.completed`

Antigravity fake CLI:

- `agy --version`
- `agy models`
- `agy --print ...`
- `--log-file`에 `conversation`과 `selected model` 메타데이터 기록

## 시나리오 환경 변수

공통으로 `TRINITY_FAKE_PROVIDER_MODE`를 사용할 수 있고, provider별로 더 구체적인 변수를 지정할 수 있다.

- `TRINITY_FAKE_CLAUDE_MODE`
- `TRINITY_FAKE_CODEX_MODE`
- `TRINITY_FAKE_AGY_MODE`

지원 모드:

- `success`: 기본 성공 응답
- `probe_exit1`: `--version` probe 실패
- `auth_required`: 인증 필요 메시지와 exit code 1
- `exit1`: 일반 provider 호출 실패
- `empty`: provider 호출 성공이지만 stdout 없음
- `models_empty`: 모델 탐색 결과 없음
- `models_exit1`: 모델 탐색 명령 실패
- `slow`: `TRINITY_FAKE_PROVIDER_SLEEP_SECONDS` 만큼 대기

모델 목록 override:

- `TRINITY_FAKE_CODEX_MODELS_JSON`: `codex debug models` JSON 전체를 교체
- `TRINITY_FAKE_AGY_MODELS`: `agy models`의 줄 단위 출력 교체

## 호출 로그

모든 fake CLI 호출은 `TRINITY_FAKE_PROVIDER_LOG`에 JSONL로 기록된다.

```json
{
  "provider": "codex",
  "argv": ["exec", "--json", "--ephemeral", "-"],
  "stdin": "prompt text",
  "cwd": "/tmp/project",
  "mode": "success",
  "env": {
    "TRINITY_FAKE_PROVIDER_LOG": "/tmp/.../provider-calls.jsonl"
  }
}
```

테스트에서는 `fake.read_calls()`나 `provider_calls(calls, "codex")`로 읽는다.

## 운영 원칙

- 실제 계정, 토큰, 세션 파일, 브라우저 쿠키를 테스트에 넣지 않는다.
- provider별 CLI 출력 계약을 바꾸는 작업은 fake harness도 함께 갱신한다.
- UI/UX 또는 preflight 오류 재현은 fake mode를 먼저 추가하고, 그 mode를 사용하는 회귀 테스트를 붙인다.
- 실제 CLI smoke test가 필요하면 별도 opt-in 문서와 로컬 전용 환경 변수로 분리한다. CI 기본 경로에는 포함하지 않는다.
