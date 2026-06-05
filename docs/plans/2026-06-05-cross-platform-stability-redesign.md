# Cross-Platform Stability Redesign

- Date: 2026-06-05
- Branch: `codex/cross-platform-stability-redesign`
- Scope: Windows Terminal, PowerShell, macOS Terminal, Linux terminal에서 `pip install trinity-agent` 후 안정적으로 실행되는 Trinity 런타임/TUI 재설계

## 배경

Trinity는 현재 기본 agent transport를 `one-shot`으로 전환했기 때문에 provider 호출 자체는 cross-platform화하기 좋은 상태다. 그러나 아직 다음 경로에 플랫폼 의존성이 남아 있다.

- `trinity bootstrap`은 tmux session을 만들고 provider CLI를 pane에 띄운다.
- `trinity attach`는 tmux transport session attach만 수행한다.
- `trinity logs --follow`는 POSIX `tail -f`에 의존한다.
- isolated provider state는 `HOME`, `XDG_*` 중심이라 Windows의 `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`를 충분히 반영하지 않는다.
- TUI는 Rich/prompt_toolkit 기반으로 동작하지만 terminal capability, emoji/box character fallback, 좁은 폭 레이아웃, dumb terminal 대응이 명시적인 계층으로 분리되어 있지 않다.
- README와 일부 문서는 tmux interactive mode를 여전히 주요 실행 방식처럼 설명한다.

목표는 Windows Terminal/PowerShell, macOS Terminal, Linux terminal 모두에서 기본 기능이 같은 방식으로 동작하게 만들고, tmux는 명시적인 legacy/debug 기능으로만 남기는 것이다.

## 목표

1. `pip install trinity-agent` 후 `trinity`, `trinity init`, `trinity ask`, `trinity status`, `trinity logs`, `trinity bootstrap`이 Windows/macOS/Linux에서 동작한다.
2. 기본 런타임은 tmux, POSIX shell, `tail`, `env VAR=... command` 문법에 의존하지 않는다.
3. provider CLI auth는 기본적으로 사용자 PC의 기존 auth를 재사용한다.
4. isolated provider state를 선택했을 때도 Windows/macOS/Linux별 home/config env가 일관되게 적용된다.
5. TUI는 terminal capability에 따라 자동으로 rich/compact/plain rendering을 선택한다.
6. 고급 TUI 개선은 안정적인 Rich 기반 UI를 우선 정리하고, Textual 도입은 별도 선택 사항으로 둔다.
7. 기존 tmux transport는 깨지지 않게 legacy/debug 경로로 유지하되, unsupported platform에서는 명확한 안내를 출력한다.

## 비목표

- provider CLI 자체가 Windows/macOS/Linux에서 지원하지 않는 기능까지 Trinity가 보장하지 않는다.
- Claude/Codex/Antigravity의 auth flow를 직접 구현하지 않는다. Trinity는 설치 감지, 실행, readiness 진단, 안내만 제공한다.
- tmux interactive transport를 cross-platform 핵심 경로로 되살리지 않는다.
- TUI 고도화 작업에서 웹/GUI 앱으로 전환하지 않는다.

## 현재 구조 진단

### 기본 transport

`transport_mode` 기본값은 `one-shot`이다. 이 경로에서는 provider CLI를 `subprocess.run([...])`로 호출하고 stdout/stderr를 파싱한다. 이 방향은 cross-platform에 적합하다.

유지할 원칙:

- shell string이 아니라 argv list를 사용한다.
- stdin/stdout/stderr encoding은 UTF-8 + replacement policy를 유지한다.
- provider별 command builder가 shell quoting을 소유하지 않게 한다.

### tmux 잔존 경로

tmux는 현재 다음에 사용된다.

- `transport_mode = "tmux"` 또는 `trinity ask -i`
- `trinity attach`
- `trinity bootstrap`
- legacy completion detector tests

일반 라운드 처리에서는 이미 기본값이 아니므로 제거보다 격리가 맞다. 다만 `bootstrap`은 신규 사용자 onboarding의 핵심 명령이므로 tmux 의존을 제거해야 한다.

### POSIX 전용 명령

`trinity logs --follow`는 `tail -f`를 실행한다. Windows에서 실패한다. Python으로 파일 tail/follow를 구현해야 한다.

### isolated home/env

현재 isolated mode는 `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`를 제공한다. Windows provider CLI는 보통 `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`를 참조할 수 있으므로 isolated mode가 불완전하다.

### TUI

현재 TUI는 Rich Live와 prompt_toolkit을 사용한다. prompt_toolkit의 Windows screen buffer fallback은 일부 존재한다. 그러나 렌더링 정책이 terminal capability와 분리되어 있지 않다.

문제:

- emoji/box drawing width 차이로 Windows/macOS/Linux에서 줄 깨짐 가능
- 작은 터미널 폭에서 panel text overflow 가능
- dumb terminal, CI, redirected stdout에서 Live UI가 부적절할 수 있음
- UI theme가 기능 상태와 시각 표현을 강하게 결합함

## 목표 아키텍처

### 1. Platform Capability Layer

새 모듈 후보:

- `src/trinity/platform/__init__.py`
- `src/trinity/platform/capabilities.py`
- `src/trinity/platform/paths.py`
- `src/trinity/platform/process.py`
- `src/trinity/platform/log_tail.py`

주요 모델:

```python
@dataclass(frozen=True)
class PlatformInfo:
    os_name: Literal["windows", "macos", "linux", "unknown"]
    shell_name: str
    terminal_name: str
    is_tty: bool
    is_ci: bool

@dataclass(frozen=True)
class TerminalCapabilities:
    color_system: Literal["truecolor", "256color", "standard", "none"]
    supports_unicode: bool
    supports_emoji: bool
    supports_box_drawing: bool
    supports_live_render: bool
    width: int
    height: int
```

사용 위치:

- CLI startup에서 capability를 감지한다.
- TUI renderer가 capability에 따라 icon set, border style, layout density를 선택한다.
- `trinity doctor`가 capability 결과를 출력한다.
- unsupported legacy tmux 경로에서 platform-specific hint를 출력한다.

### 2. Cross-Platform Process Runner

provider 호출과 bootstrap 실행을 공통 runner로 통일한다.

원칙:

- 항상 argv list 사용
- `shell=True` 금지
- env merge는 Python dict로 처리
- cwd는 `Path`로 전달하고 존재 여부를 선검증
- Windows에서는 `.cmd`, `.exe`, PowerShell shim 실행을 `shutil.which()` 결과 기준으로 처리
- command display는 실행용 argv와 별도의 human-readable rendering으로 분리

새 모델 후보:

```python
@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str]
    timeout_seconds: float | None = None

class ProcessRunner:
    def run(self, command: CommandSpec) -> CompletedProcess[str]: ...
    def stream_interactive(self, command: CommandSpec) -> int: ...
```

`stream_interactive()`는 `trinity bootstrap`에서 provider CLI를 현재 터미널에 직접 연결할 때 사용한다. tmux pane이 아니라 현재 터미널에서 순차적으로 실행한다.

### 3. Bootstrap Redesign

현재:

```text
trinity bootstrap
  -> tmux session 생성
  -> agent별 pane 생성
  -> 각 pane에 provider CLI command 전송
  -> attach
```

목표:

```text
trinity bootstrap
  -> 대상 provider 목록 산출
  -> provider별 readiness 확인
  -> 사용자에게 실행할 provider와 state mode 설명
  -> provider CLI를 현재 터미널에서 하나씩 실행
  -> 사용자가 auth/trust/setup 완료 후 종료
  -> 다음 provider 진행
  -> 마지막에 readiness 재검사 및 요약 출력
```

CLI 옵션 변경 제안:

- 유지: `--agents`, `--all`, `--force`
- 추가: `--check-only`, `--skip-ready`, `--continue-on-error`
- 변경: `--session-name`, `--no-attach`는 legacy tmux bootstrap 전용으로 deprecated
- 추가 legacy escape hatch: `trinity bootstrap --legacy-tmux`

Windows/PowerShell에서 기대 동작:

- `tmux` 없이 실행된다.
- provider CLI가 현재 콘솔에서 직접 auth prompt를 표시한다.
- CLI 종료 후 Trinity가 다음 provider로 이동한다.

### 4. Provider State Env

`provider_state_mode = "user-home"`:

- env override 없음.
- 사용자의 기존 Claude/Codex/Antigravity auth를 그대로 사용한다.
- cross-platform 기본값으로 유지한다.

`provider_state_mode = "isolated"`:

운영체제별 env override를 제공한다.

Windows:

- `USERPROFILE=<provider-state>`
- `APPDATA=<provider-state>/AppData/Roaming`
- `LOCALAPPDATA=<provider-state>/AppData/Local`
- `HOME=<provider-state>`도 보조로 제공

macOS/Linux:

- `HOME=<provider-state>`
- `XDG_CONFIG_HOME=<provider-state>/.config`
- `XDG_DATA_HOME=<provider-state>/.local/share`
- `XDG_CACHE_HOME=<provider-state>/.cache`

공통:

- env path directory는 provider 실행 전 생성한다.
- provider별 subdir는 `ManagedHome`이 생성한다.
- env override는 command string에 삽입하지 않고 `subprocess` env dict로만 전달한다.

### 5. Logs Follow

`trinity logs --follow`를 Python 구현으로 교체한다.

요구사항:

- Windows/macOS/Linux에서 동일하게 동작
- `Ctrl+C`로 정상 종료
- UTF-8 decoding replacement
- 파일이 rotate되거나 삭제되었을 때 친절한 메시지
- 초기 N줄 출력 후 append polling

구현 후보:

- `trinity.platform.log_tail.follow_file(path, lines, poll_interval=0.5)`
- CLI는 이 generator를 소비해 `console.print()`만 수행

### 6. TUI Rendering Redesign

Rich 기반을 유지하면서 renderer를 capability-aware로 분리한다.

새 계층:

```text
tui/
  app.py              # state model + high-level rendering orchestration
  renderers/
    rich.py           # normal/modern rendering
    compact.py        # narrow terminal rendering
    plain.py          # dumb terminal, CI, redirected stdout
  style.py            # palette, icon set, border set
  layout.py           # width-aware layout decisions
```

Icon set:

- `modern`: emoji + unicode box drawing
- `unicode`: unicode symbols without emoji
- `ascii`: ASCII only

Layout modes:

- `full`: width >= 110
- `compact`: 80 <= width < 110
- `narrow`: width < 80
- `plain`: non-TTY or no live render

UI 목표:

- 상단 header는 버전, transport, synthesis provider, target workspace를 한 줄로 보여준다.
- agent 상태는 카드가 아니라 scan 가능한 rail/list로 보여준다.
- 중앙은 transcript-like session view로 바꾼다.
- workflow 질문은 대화형 choice block으로 보여주고 바로 선택/입력할 수 있게 한다.
- live update 중 provider splash/raw output은 표시하지 않고 상태/요약/진행률만 보여준다.
- 결과 출력은 Markdown panel을 유지하되 작은 화면에서는 plain summary로 자동 축소한다.

Textual 도입 판단:

- 1차 안정화에서는 도입하지 않는다.
- Rich renderer 정리 후 `trinity tui --experimental-textual` 형태로 별도 feature branch에서 검토한다.
- 이유: cross-platform 안정화와 UI framework migration을 동시에 하면 장애 원인 분리가 어렵다.

### 7. Doctor Command

`trinity doctor`를 추가하거나 기존 status/readiness를 확장한다.

출력 항목:

- Trinity version
- Python version
- OS/shell/terminal/capabilities
- active config path
- state dir
- transport mode
- provider_state_mode
- provider CLI installed/version/path
- provider auth/readiness result
- one-shot smoke 가능 여부
- legacy tmux availability, 단 기본 경로에는 필요 없다고 표시

이 명령은 이슈 리포트와 사용자 self-diagnosis의 기준이 된다.

### 8. Packaging and CI

`pip install trinity-agent` 품질 기준:

- wheel에 필요한 package data 누락 없음
- console script `trinity` 정상 생성
- Python 3.10/3.11/3.12 지원 유지
- Windows/macOS/Linux matrix에서 unit test 통과
- provider CLI가 없는 CI에서도 setup/detection/readiness가 graceful failure로 끝남

GitHub Actions matrix 제안:

- `ubuntu-latest`: Python 3.10, 3.11, 3.12
- `windows-latest`: Python 3.10, 3.11, 3.12
- `macos-latest`: Python 3.11, 3.12

테스트 분리:

- 기본 unit tests
- platform tests with monkeypatch
- packaging smoke: `python -m pip install dist/*.whl`, `trinity --version`, `trinity --help`
- optional provider smoke는 로컬/수동 checklist로 유지

## 작업 순서

### P0. Cross-platform audit baseline

목표:

- 현재 플랫폼 의존 지점을 코드/테스트로 명시한다.
- 문서와 README에서 tmux가 기본 경로처럼 보이는 표현을 분리한다.

주요 작업:

- `git grep` 기반 POSIX/tmux/shell 의존 audit 문서 갱신
- `trinity bootstrap`, `trinity logs`, `ManagedHome`, `TUI prompt/render` 관련 테스트 목록 정리
- Windows/macOS/Linux manual smoke checklist 작성

병렬 가능 여부:

- 다른 구현과 병렬 가능하지만, P1/P2 작업 전 완료하는 것이 좋다.

### P1. Platform capability layer

목표:

- OS/shell/terminal capability 감지 API를 추가한다.
- TUI/doctor/log/bootstrap이 이 API를 참조할 수 있게 한다.

주요 작업:

- `trinity.platform.capabilities` 추가
- `TerminalCapabilities` 테스트 추가
- Windows/macOS/Linux 환경 변수 monkeypatch 테스트 추가

병렬 가능 여부:

- P3 logs, P4 TUI와 병렬 설계 가능
- P2 bootstrap은 P1 결과를 사용하는 것이 좋다.

### P2. Process runner and env normalization

목표:

- provider 실행과 bootstrap 실행이 shell string에 의존하지 않게 한다.
- isolated env를 Windows/macOS/Linux별로 보강한다.

주요 작업:

- `ProcessRunner`, `CommandSpec` 추가
- `ManagedHome.get_env_overrides()`를 platform-aware로 변경
- `build_provider_command()` 같은 display용 shell string과 실행용 command spec 분리
- provider invoker tests 보강

병렬 가능 여부:

- P1 이후 진행 권장
- P3 logs와 병렬 가능
- P2 완료 후 P4 bootstrap을 시작한다.

### P3. Pure Python logs follow

목표:

- `tail -f` 제거.

주요 작업:

- `trinity.platform.log_tail` 추가
- `trinity logs --follow`를 Python follower로 전환
- rotate/delete/empty file 테스트 추가

병렬 가능 여부:

- P1/P2와 독립적으로 병렬 가능

### P4. Bootstrap no-tmux path

목표:

- `trinity bootstrap` 기본 경로에서 tmux를 제거한다.

주요 작업:

- `ProviderBootstrapper.launch_session()`을 legacy tmux 전용으로 이름 변경 또는 분리
- 새 `ProviderBootstrapper.run_interactive_sequence()` 추가
- provider별 현재 터미널 실행 flow 구현
- readiness pre-check/post-check 출력
- `--legacy-tmux`를 escape hatch로 추가
- `--session-name`, `--no-attach` deprecation 안내

병렬 가능 여부:

- P2 이후 진행
- TUI 개선(P5)과 병렬 가능

### P5. Adaptive Rich TUI

목표:

- terminal capability에 따라 UI가 깨지지 않게 한다.
- 현재보다 session-like하고 전문적인 화면으로 정리한다.

주요 작업:

- icon/border/palette set 분리
- width-aware layout 추가
- non-TTY/plain fallback 추가
- prompt_toolkit fallback 범위 확장
- workflow question choice block 개선
- status/header/workflow panel 재배치

병렬 가능 여부:

- P1 이후 진행
- P3/P4와 병렬 가능
- Textual 실험은 P5 완료 후 별도 branch 권장

### P6. Doctor and packaging matrix

목표:

- 사용자가 환경 문제를 스스로 진단할 수 있게 한다.
- CI에서 Windows/macOS/Linux 회귀를 막는다.

주요 작업:

- `trinity doctor` 추가
- provider CLI detection/readiness summary 통합
- GitHub Actions matrix 추가
- wheel install smoke 추가
- README 설치/문제 해결 문서 갱신

병렬 가능 여부:

- P1/P2가 필요
- CI matrix는 P3/P4/P5 완료 후 안정화 단계에서 병합 권장

## 병렬 작업 매트릭스

| 작업 | 선행 조건 | 병렬 가능 |
| --- | --- | --- |
| P0 audit | 없음 | P1과 병렬 가능 |
| P1 capability | 없음 | P0/P3 설계와 병렬 가능 |
| P2 runner/env | P1 권장 | P3과 병렬 가능 |
| P3 logs follow | 없음 | P1/P2와 병렬 가능 |
| P4 bootstrap | P2 필요 | P5와 병렬 가능 |
| P5 adaptive TUI | P1 필요 | P4와 병렬 가능 |
| P6 doctor/CI | P1/P2 필요 | 마지막 통합 단계 권장 |

## 호환성 정책

### 유지

- `transport_mode = "one-shot"` 기본값
- `transport_mode = "tmux"` legacy/debug 옵션
- `trinity ask -i` legacy alias
- 기존 `trinity.tmux.*` compatibility shim

### 변경

- `trinity bootstrap` 기본 동작은 tmux가 아니라 순차 interactive execution
- `trinity logs --follow`는 Python 구현
- README에서 tmux는 optional legacy/debug로 재분류

### Deprecated

- `trinity bootstrap --session-name`
- `trinity bootstrap --no-attach`
- 기본 설정에서 `trinity attach` 사용 기대

### 제거 후보

즉시 제거하지 않는다. 다음 릴리스 이후 사용 로그와 테스트 안정성을 보고 판단한다.

- tmux bootstrap default path
- tmux pane title update in deliberation protocol
- Claude/Codex tmux interactive wrappers

## 검증 기준

### 자동 테스트

- `uv run pytest`
- Windows monkeypatch tests:
  - `USERPROFILE`, `APPDATA`, `LOCALAPPDATA` env 생성
  - `tail` 미사용
  - tmux 없는 환경에서 bootstrap default 성공 경로 mock
- macOS/Linux monkeypatch tests:
  - `HOME`, `XDG_*` env 생성
  - tmux legacy guard 유지
- packaging smoke:
  - `uv build`
  - wheel install into clean venv
  - `trinity --version`
  - `trinity --help`
  - `trinity init --non-interactive`
  - `trinity status`

### 수동 smoke

Windows Terminal + PowerShell:

- `pip install trinity-agent`
- `trinity --version`
- `trinity init`
- `trinity doctor`
- `trinity bootstrap --agents codex`
- `trinity ask "간단히 응답해줘" --agents codex`
- `trinity logs --follow`

macOS Terminal/zsh:

- 동일 smoke
- Unicode/emoji rendering 확인
- narrow terminal width 확인

Linux/bash:

- 동일 smoke
- legacy `transport_mode = "tmux"` smoke는 optional

## 리스크와 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| provider CLI별 Windows auth 저장 위치 차이 | isolated mode auth 실패 | user-home 기본 유지, isolated는 env matrix 테스트와 문서화 |
| prompt_toolkit Windows console 예외 | TUI 입력 실패 | Dummy fallback 외 plain input fallback 추가 |
| Unicode width 차이 | UI 깨짐 | capability 기반 ascii/unicode/emoji icon set |
| bootstrap provider CLI가 현재 터미널을 점유 | UX 혼란 | provider별 안내 panel과 post-check summary 제공 |
| Textual 도입 시 회귀 증가 | 릴리스 지연 | 1차 안정화에서는 Rich 유지, Textual은 별도 실험 |

## 권장 릴리스 전략

1. `0.9.x`: cross-platform 안정화 기반 작업
2. `0.10.0`: tmux-free bootstrap, doctor, CI matrix까지 포함한 cross-platform milestone
3. `0.11.0`: adaptive TUI polish
4. 이후: Textual experimental UI 검토

## 완료 정의

이 재설계는 다음 조건을 만족하면 구현 완료로 본다.

- 기본 명령이 Windows/macOS/Linux에서 POSIX/tmux 의존 없이 실행된다.
- `trinity bootstrap` 기본 경로가 tmux 없이 동작한다.
- isolated env가 Windows/macOS/Linux별 home/config env를 제공한다.
- `trinity logs --follow`가 Python 구현으로 대체된다.
- TUI가 terminal capability에 따라 modern/unicode/ascii/plain 중 하나를 안정적으로 선택한다.
- CI에 Windows/macOS/Linux packaging smoke가 추가된다.
- README와 troubleshooting 문서가 새 기본 경로를 설명한다.
