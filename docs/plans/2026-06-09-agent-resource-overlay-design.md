# Agent Resource Overlay Design

- 작성일: 2026-06-09
- 작업 브랜치: `feature/agent-resource-overlay-design`
- 상태: design draft
- 관련 문서:
  - `docs/plans/2026-06-04-isolated-provider-bootstrap.md`
  - `docs/plans/2026-06-09-provider-session-model-context-design.md`
  - `docs/plans/2026-06-06-trinity-slash-command-routing-design.md`
  - `docs/plans/2026-06-06-provider-cli-slash-command-backlog.md`

## 목적

Trinity에 연결된 세 agent, 즉 Claude Code, Codex, Antigravity CLI가 각 provider의 원래
user home이나 provider-native 설정에 이미 가지고 있는 skill, hook, command, MCP/server
설정과 별개로 Trinity가 제공하는 확장 리소스를 사용할 수 있게 한다.

핵심은 "agent가 원래 가진 것"과 "Trinity workflow가 임시 또는 프로젝트 단위로 제공한 것"을
명확히 분리하는 것이다. Trinity는 provider의 원본 설정을 덮어쓰지 않고, agent별 managed
home과 resource overlay를 통해 필요한 리소스만 발견, 검증, 투영, 회수한다.

## 현재 상태

현재 코드 기준으로 관련 구조는 다음과 같다.

- `AgentSpec`은 provider, CLI command, model, role prompt, extra args, workspace mode만 가진다.
- `ManagedHome`은 `.trinity/agents/<agent>/provider-state`를 만들고 `HOME`, `XDG_*`,
  Windows profile env를 override할 수 있다.
- `ProviderBootstrapper`는 isolated provider home에서 first-run/auth/bootstrap을 실행한다.
- `AgentFactory`는 Claude, Codex, Antigravity agent wrapper를 생성한다.
- `completion/hook.py`의 hook은 tmux interactive 완료 감지용 Trinity 내부 hook이다.
  provider skill/hook 리소스와 같은 개념이 아니다.
- provider-native session id와 runtime model metadata는 workflow session에 저장되기 시작했다.

빠진 부분은 다음이다.

- Trinity가 소유하는 skill/hook/command/resource manifest 모델이 없다.
- agent별로 어떤 Trinity resource pack을 활성화할지 config에 표현할 수 없다.
- provider별 CLI가 읽을 수 있는 위치로 resource를 안전하게 투영하는 adapter가 없다.
- native resource와 Trinity overlay resource의 충돌, 우선순위, 감사 로그 정책이 없다.

## 목표

1. 세 provider에 공통으로 적용 가능한 `AgentResource` 모델을 정의한다.
2. Trinity resource를 project/workflow/agent scope로 활성화할 수 있게 한다.
3. provider 원본 home이나 사용자의 실제 home을 직접 수정하지 않는다.
4. isolated provider-state와 user-home mode 모두에서 동작 가능한 adapter 경계를 둔다.
5. skill/hook/command를 provider별 파일 포맷으로 직접 섞지 않고 projection 단계에서만 변환한다.
6. resource activation 결과를 workflow event와 session state에 남긴다.
7. read-only deliberation과 workspace-write execution에서 사용할 수 있는 hook 권한을 분리한다.
8. provider 포맷이 확인되지 않은 resource는 prompt inventory로만 노출하고 provider config에 쓰지 않는다.

## 비목표

- Claude, Codex, Antigravity의 실제 native resource 포맷을 이 문서에서 확정하지 않는다.
- 사용자의 real home에 있는 개인 skill/hook을 자동 import하지 않는다.
- provider CLI가 지원하지 않는 resource 유형을 강제로 에뮬레이션하지 않는다.
- provider-native marketplace, plugin install, auth flow를 Trinity가 대체하지 않는다.
- hook이 임의 command를 실행하도록 기본 허용하지 않는다.

## 용어

| 용어 | 의미 |
| :--- | :--- |
| native resource | provider CLI가 원래 user home 또는 provider home에서 읽는 기존 skill/hook/command |
| Trinity resource | Trinity가 프로젝트나 workflow를 위해 별도로 제공하는 skill/hook/command |
| resource pack | 여러 Trinity resource를 묶은 배포 단위 |
| overlay | native resource와 분리된 Trinity resource namespace |
| projection | Trinity resource를 provider가 읽을 수 있는 파일, env, argv, prompt inventory로 변환하는 과정 |
| provider adapter | provider별 projection 포맷과 CLI contract를 담당하는 구현체 |
| prompt inventory | provider config에 직접 쓰지 않고 prompt/context에 "사용 가능한 리소스 목록"으로 전달하는 fallback |

## 설계 원칙

1. 원본 provider 설정은 읽기 전용으로 취급한다.
2. Trinity가 만든 파일은 `.trinity` 아래에서만 관리한다.
3. 같은 이름의 native resource와 Trinity resource는 같은 namespace에 넣지 않는다.
4. provider가 flat namespace만 지원하면 Trinity resource 이름에 `trinity__<pack>__<id>` prefix를 붙인다.
5. provider별 포맷은 adapter 내부로 가둔다.
6. projection은 idempotent해야 한다.
7. manifest checksum이 바뀌면 이전 projection을 폐기하고 새 projection을 만든다.
8. hook은 side effect 등급을 manifest에 선언해야 하며 access policy와 맞지 않으면 비활성화한다.
9. workflow resume 시 같은 resource revision을 복원할 수 있어야 한다.
10. 실패 시 provider 호출 전체를 막을지, prompt inventory로 degrade할지 resource별 정책으로 결정한다.

## 디렉터리 구조

권장 layout:

```text
.trinity/
  resources/
    registry.toml
    packs/
      trinity-core/
        manifest.toml
        skills/
        hooks/
        commands/
        prompts/
        files/
      review-hardening/
        manifest.toml
        skills/
        hooks/
  agents/
    claude/
      provider-state/
      overlay/
        manifest.lock
        projected/
    codex/
      provider-state/
      overlay/
        manifest.lock
        projected/
    antigravity/
      provider-state/
      overlay/
        manifest.lock
        projected/
  workflow/
    session.json
    events.jsonl
```

역할:

- `resources/packs/*`는 사람이 관리하는 source of truth다.
- `agents/<agent>/overlay/projected`는 provider adapter가 생성한 산출물이다.
- `manifest.lock`은 pack id, version, checksum, projection path, provider adapter version을 저장한다.
- `provider-state`는 provider가 자체적으로 쓰는 state/auth/config 공간이다. Trinity overlay source를 직접
  섞지 않는다.

## Cross-platform 경로 정책

경로 정책의 기준은 "provider CLI 프로세스가 실제로 접근할 수 있는 경로만 provider에 전달한다"이다.
Trinity가 WSL, Linux, macOS, Windows 중 어디에서 실행되는지와 provider CLI가 어느 OS namespace의
프로세스로 실행되는지를 먼저 확정한 뒤, 그 namespace에 맞는 path/env를 렌더링한다.

### 저장 형식과 렌더링 형식 분리

Manifest와 workflow session에는 host 고유 절대 경로를 가능한 저장하지 않는다.

| 위치 | 저장 방식 | 예 |
| :--- | :--- | :--- |
| resource manifest `path` | pack root 기준 POSIX 상대 경로 | `skills/implementation-plan.md` |
| registry pack path | resource root 기준 상대 경로 | `packs/trinity-core` |
| workflow resource lock | state dir 기준 상대 경로와 checksum | `agents/codex/overlay/projected/...` |
| diagnostics/log | 필요할 때만 OS별 절대 경로 허용 | `/home/user/...`, `C:\Users\...` |

Manifest의 `path`는 다음을 금지한다.

- 절대 경로: `/home/user/x`, `C:\Users\x`
- parent traversal: `../x`
- UNC 경로: `\\server\share\x`
- OS별 separator 의존: `skills\foo.md`

실제 파일 접근은 `PathResolver`가 담당한다.

```python
@dataclass(frozen=True)
class ResourcePathSet:
    project_dir: Path
    state_dir: Path
    resource_root: Path
    pack_root: Path
    managed_home: Path
    overlay_dir: Path
    projected_dir: Path
    provider_visible_projected_dir: str
    provider_visible_home: str
    platform: str # linux | macos | windows | wsl
```

내부 검증은 `Path.resolve()`와 `is_relative_to()`로 수행한다. Provider에 넘기는 문자열은
`provider_visible_*` 필드처럼 adapter가 마지막에 렌더링한 값만 사용한다.

### OS별 managed home env

`ManagedHome`은 agent별 provider-state를 만들고 provider process 환경변수로 home을 바꾼다.

| OS namespace | Env override | Provider가 보게 되는 home |
| :--- | :--- | :--- |
| Linux/WSL | `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME` | `/home/user/project/.trinity/agents/<agent>/provider-state` |
| macOS | `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME` | `/Users/name/project/.trinity/agents/<agent>/provider-state` |
| Windows | `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA` | `C:\Users\name\project\.trinity\agents\<agent>\provider-state` |

Windows에서는 다음 형태를 만든다.

```text
.trinity\agents\<agent>\provider-state\
  AppData\Roaming\
  AppData\Local\
```

그리고 provider process에는 다음을 넘긴다.

```text
HOME=<managed-home>
USERPROFILE=<managed-home>
APPDATA=<managed-home>\AppData\Roaming
LOCALAPPDATA=<managed-home>\AppData\Local
```

macOS에서는 provider CLI가 `~/Library/Application Support`를 직접 쓰는 contract가 확인되면
adapter가 managed home 아래에 다음 경로를 추가 생성할 수 있다.

```text
.trinity/agents/<agent>/provider-state/Library/Application Support/
```

단, 이 경로도 real `/Users/<name>/Library`가 아니라 managed home 내부여야 한다.

### WSL과 Windows executable 혼용 금지

WSL에서 Trinity가 실행되면 기본 provider CLI도 WSL 안의 Linux executable로 본다.

```text
Trinity process: WSL/Linux
Provider process: WSL/Linux
Path format: /home/user/workspace/Trinity/.trinity/...
```

반대로 Windows PowerShell/CMD에서 Trinity가 실행되면 provider CLI도 Windows executable로 본다.

```text
Trinity process: Windows
Provider process: Windows
Path format: C:\Users\USER\workspace\Trinity\.trinity\...
```

기본 정책은 "서로 다른 namespace 실행을 자동 지원하지 않는다"이다. 예를 들어 WSL Trinity가
Windows `codex.exe`를 직접 실행하거나 Windows Trinity가 WSL `claude`를 직접 실행하는 경우,
다음 문제가 생긴다.

- `/home/user/...`를 Windows executable이 읽지 못한다.
- `C:\Users\...`를 Linux executable이 읽지 못한다.
- `HOME`과 `USERPROFILE` 중 어느 쪽을 provider가 신뢰하는지 달라진다.
- prompt inventory에 적힌 파일 경로가 실제 provider tool에서 열리지 않는다.

따라서 cross-namespace 실행은 명시 opt-in으로만 허용한다.

```toml
[general]
provider_process_namespace = "auto" # auto | host | wsl | windows
```

초기 구현에서는 `auto`만 지원한다. `auto`는 Trinity 프로세스와 같은 namespace의 provider command만
정상 지원한다. 나중에 `wsl -> windows`를 지원하려면 adapter가 `wslpath -w` 변환, Windows env 생성,
Windows cwd 변환을 모두 통과하는 contract test를 가져야 한다.

### Prompt inventory 경로

Prompt inventory에 넣는 path는 provider process가 읽을 수 있는 path여야 한다.

우선순위:

1. Provider cwd 아래에 projected file이 있으면 cwd 기준 상대 경로를 쓴다.
2. Provider cwd 밖에 있으면 provider namespace의 절대 경로를 쓴다.
3. Cross-namespace path 변환이 검증되지 않았으면 path를 숨기고 summary/body만 넣는다.

예:

```text
# Linux/WSL provider
Path: /home/user/workspace/Trinity/.trinity/agents/codex/overlay/projected/...

# macOS provider
Path: /Users/name/workspace/Trinity/.trinity/agents/codex/overlay/projected/...

# Windows provider
Path: C:\Users\USER\workspace\Trinity\.trinity\agents\codex\overlay\projected\...
```

Git worktree mode에서는 provider cwd가 `.trinity/workspace/<agent>`일 수 있다. 이때 overlay가
control repo의 `.trinity/agents/<agent>/overlay`에 있으면 cwd 밖 경로가 된다. Adapter는 이 경로를
provider-visible absolute path로 전달하거나, 필요하면 worktree 안의 `.trinity-overlay/<agent>`로
copy projection을 만들 수 있다. Symlink는 Windows 권한과 WSL mount 옵션에 따라 실패할 수 있으므로
기본값으로 쓰지 않는다.

### Lock file 경로

`manifest.lock`에는 다음 값을 저장한다.

```json
{
  "platform": "linux",
  "pack_id": "trinity-core",
  "resource_id": "implementation-plan",
  "source_relpath": "resources/packs/trinity-core/skills/implementation-plan.md",
  "projected_relpath": "agents/codex/overlay/projected/trinity-core/skills/implementation-plan.md",
  "checksum": "sha256:..."
}
```

OS별 절대 경로는 lock의 canonical key로 쓰지 않는다. Resume 시에는 현재 OS와 현재 `state_dir`을
기준으로 절대 경로를 다시 계산한다. 이 방식이면 같은 workflow archive를 macOS에서 만들고 Linux에서
복원할 때도 checksum과 상대 경로 기준으로 호환성 판단을 할 수 있다.

### Adapter 책임

Provider adapter는 다음을 보장해야 한다.

- provider process와 같은 OS namespace의 path string만 env/argv/prompt에 넣는다.
- Windows provider에는 POSIX path를 넘기지 않는다.
- Linux/macOS provider에는 drive-letter path를 넘기지 않는다.
- UNC path는 provider contract test가 없으면 넘기지 않는다.
- Provider cwd, managed home, overlay path가 서로 다른 filesystem에 있어도 copy projection으로 동작한다.
- Real user home을 쓰는 `user-home` mode에서도 Trinity overlay 산출물은 `.trinity` 아래에만 쓴다.

## Config 확장

### 전역 설정

```toml
[resources]
enabled = true
root = ".trinity/resources"
projection_mode = "managed-overlay" # managed-overlay | prompt-only | disabled
collision_policy = "namespace"      # namespace | fail | native-wins
default_failure_policy = "degrade"  # degrade | fail-provider-call
audit = true
```

### Agent별 설정

```toml
[agents.claude.resources]
packs = ["trinity-core", "review-hardening"]
types = ["skill", "hook", "command", "prompt"]
disabled = []
activation = "auto"

[agents.codex.resources]
packs = ["trinity-core"]
types = ["skill", "command", "prompt"]
disabled = ["review-hardening.blocking-hook"]

[agents.antigravity.resources]
packs = ["trinity-core"]
types = ["skill", "prompt"]
activation = "prompt-only"
```

`activation` 값:

| 값 | 의미 |
| :--- | :--- |
| `auto` | provider adapter가 지원하면 projection, 아니면 prompt inventory |
| `project` | provider-readable 파일/env/argv projection 필수 |
| `prompt-only` | provider config에는 쓰지 않고 prompt inventory로만 전달 |
| `off` | 해당 agent에서 Trinity resource 비활성화 |

## Resource Pack Manifest

각 pack은 `manifest.toml`을 가진다.

```toml
id = "trinity-core"
version = "0.1.0"
title = "Trinity Core Agent Resources"
description = "Shared skills and prompts provided by Trinity."

[[resources]]
id = "implementation-plan"
type = "skill"
path = "skills/implementation-plan.md"
summary = "Turn a blueprint into an execution-ready package plan."
target_providers = ["claude-code", "codex", "antigravity-cli"]
target_agents = ["claude", "codex", "antigravity"]
lanes = ["deliberation", "execution"]
access = ["read-only", "workspace-write"]
mount = "copy"
failure_policy = "degrade"

[[resources]]
id = "pre-write-guard"
type = "hook"
path = "hooks/pre-write-guard.toml"
summary = "Validate write scope before execution hooks are enabled."
target_providers = ["claude-code", "codex"]
target_agents = ["claude", "codex"]
lanes = ["execution"]
access = ["workspace-write"]
side_effects = "read"
mount = "adapter"
failure_policy = "fail-provider-call"
```

Resource type:

| Type | 설명 |
| :--- | :--- |
| `skill` | agent가 사용할 절차, 지식, workflow guide |
| `hook` | provider 또는 Trinity invocation 전후에 실행/검증되는 hook 정의 |
| `command` | provider slash command 또는 Trinity-local command extension 후보 |
| `prompt` | role/context에 포함할 prompt fragment |
| `mcp` | MCP/server connector 설정 조각 |
| `file` | 위 유형을 지원하기 위한 보조 파일 |

Mount mode:

| Mode | 의미 |
| :--- | :--- |
| `copy` | overlay projected dir로 파일 복사 |
| `render` | template 변수 치환 후 projected dir에 생성 |
| `adapter` | provider adapter가 native 포맷으로 변환 |
| `prompt` | 파일 투영 없이 prompt inventory에만 포함 |

## 데이터 모델

### AgentResourceRef

```python
@dataclass(frozen=True)
class AgentResourceRef:
    id: str
    pack_id: str
    version: str
    resource_type: str
    source_path: Path
    summary: str = ""
    target_providers: tuple[str, ...] = ()
    target_agents: tuple[str, ...] = ()
    lanes: tuple[str, ...] = ()
    access: tuple[str, ...] = ()
    mount: str = "copy"
    side_effects: str = "none"
    failure_policy: str = "degrade"
    checksum: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
```

### AgentResourceProjection

```python
@dataclass
class AgentResourceProjection:
    agent_name: str
    provider: str
    pack_id: str
    resource_id: str
    resource_type: str
    projection_mode: str
    source_checksum: str
    projected_path: Path | None = None
    provider_path: Path | None = None
    env: dict[str, str] = field(default_factory=dict)
    argv: list[str] = field(default_factory=list)
    prompt_inventory: list[str] = field(default_factory=list)
    status: str = "pending" # pending | projected | prompt_only | skipped | failed
    diagnostics: list[str] = field(default_factory=list)
```

### WorkflowSession 확장

`WorkflowSession`에는 이미 `provider_sessions`와 `runtime_models`가 있다. 여기에 다음 필드를
추가한다.

```python
resource_projections: dict[str, AgentResourceProjection] = field(default_factory=dict)
```

Key 규칙:

```text
{workflow_id}:{agent_name}:{provider}:{pack_id}:{resource_id}:{lane}:{access}
```

이 값은 `/resume` 후 같은 workflow에서 어떤 Trinity resource revision이 쓰였는지 재현하는
근거가 된다.

## 실행 흐름

공통 one-shot 호출 흐름:

```text
load TrinityConfig
-> load ResourceRegistry
-> select active AgentResourceRef for agent/provider/lane/access
-> ManagedHome.setup(agent)
-> ResourceProjector.plan(...)
-> ProviderResourceAdapter.project(...)
-> merge env/argv/prompt_inventory into PromptRequest
-> invoke provider
-> persist resource_projection events and workflow session
```

tmux interactive 흐름:

```text
prepare agent pane
-> project resources before provider process starts
-> launch provider with projected env/argv
-> include prompt inventory in initial role/context prompt
-> do not mutate projection while pane process is alive unless user restarts agent
```

bootstrap 흐름:

```text
trinity bootstrap
-> prepare isolated provider-state
-> optionally project bootstrap-safe resources
-> launch provider CLI for auth/setup
```

Bootstrap에서는 hook과 command projection을 기본 비활성화한다. first-run/auth 단계에서 hook이
provider setup을 방해할 수 있기 때문이다. skill/prompt inventory처럼 side effect가 없는 resource만
허용한다.

## Provider Adapter 계약

공통 interface:

```python
class ProviderResourceAdapter(Protocol):
    provider: Provider

    def supports(self, resource: AgentResourceRef) -> bool:
        ...

    def plan(
        self,
        agent_name: str,
        managed_home: Path,
        overlay_dir: Path,
        resource: AgentResourceRef,
        lane: str,
        access: InvocationAccess,
    ) -> AgentResourceProjection:
        ...

    def project(self, projection: AgentResourceProjection) -> AgentResourceProjection:
        ...
```

Adapter 책임:

- provider CLI가 실제로 읽는 경로, config file, env var, argv flag를 캡슐화한다.
- 지원하지 않는 resource는 `prompt_only` projection으로 degrade한다.
- provider-state 내부에 파일을 써야 한다면 Trinity가 생성한 block임을 metadata/comment로 남긴다.
- native file과 충돌하면 기본적으로 같은 파일을 덮어쓰지 않는다.
- projection 결과를 lock file에 기록한다.

### Claude Code Adapter

초기 정책:

- `skill`, `prompt`는 prompt inventory를 우선 지원한다.
- native skill/hook 파일 포맷이 contract test로 검증되기 전에는 provider-state 설정 파일을 수정하지 않는다.
- provider가 명시적 설정 경로/env를 지원하는 것이 확인되면 overlay path를 env/argv로 연결한다.
- hook은 `side_effects = "none"` 또는 `read`이고 `access`가 맞을 때만 candidate로 둔다.

주의:

- 사용자의 real `~/.claude`를 scan/import하지 않는다.
- isolated mode의 `.trinity/agents/claude/provider-state`에 bootstrap으로 생긴 provider-native 설정과
  Trinity overlay source를 섞지 않는다.

### Codex Adapter

초기 정책:

- `skill`, `prompt`, `command`는 prompt inventory를 우선 지원한다.
- Codex config/cache 위치는 provider CLI contract test로 검증된 뒤 adapter에 반영한다.
- `codex exec` one-shot에서는 stdin prompt가 이미 지원되므로 resource inventory를 prompt packing에
  넣는 fallback이 안전하다.
- workspace-write access에서 실행 hook을 provider-native config로 연결하기 전, sandbox와 cwd가
  그대로 유지되는지 test가 필요하다.

주의:

- `--ephemeral` continuity와 충돌하는 기존 설계와 같은 문제를 만들지 않도록, resource projection은
  provider session continuity와 독립적으로 동작해야 한다.
- user-home mode에서는 real home config를 직접 쓰지 않는다. 필요한 경우 `.trinity/agents/codex/overlay`
  아래 파일을 만들고 env/argv로 provider에 알려줄 수 있을 때만 project mode를 허용한다.

### Antigravity Adapter

초기 정책:

- stdout/로그 contract가 다른 provider보다 약하므로 prompt inventory를 기본값으로 둔다.
- `agy --log-file`처럼 Trinity가 이미 per-call log를 지정하는 흐름과 resource audit log를 분리한다.
- provider-native conversation id는 resource projection key에 넣지 않는다. 같은 workflow에서
  conversation이 바뀌어도 resource revision은 유지되어야 한다.

주의:

- Antigravity가 resource file path를 명시적으로 받을 수 있는 contract가 확인되기 전까지
  native hook/command projection은 지원하지 않는다.

## Prompt Inventory

Provider-native projection을 못 하거나 의도적으로 피할 때, Trinity는 prompt에 compact inventory를
넣는다.

예:

```text
[Trinity Resource Overlay]
The following Trinity-provided resources are available for this turn.
Use them only when relevant to the task.

- trinity::trinity-core/implementation-plan (skill)
  Turn a blueprint into an execution-ready package plan.
  Path: .trinity/agents/codex/overlay/projected/trinity-core/skills/implementation-plan.md
- trinity::review-hardening/review-checklist (skill)
  Apply review checklist before final summary.
```

Prompt packing 정책:

- summary는 항상 포함 가능하다.
- 본문은 resource별 `prompt_budget_chars`가 있을 때만 포함한다.
- 본문 합계가 budget을 넘으면 path와 summary만 남긴다.
- hook의 실행 내용은 prompt에 노출하지 않고 capability/side effect만 요약한다.

## 충돌 정책

Resource id는 logical namespace를 가진다.

```text
native::<provider>/<name>
trinity::<pack>/<resource>
session::<workflow>/<resource>
```

Provider가 flat name만 지원하면 adapter가 다음처럼 변환한다.

```text
trinity__trinity-core__implementation-plan
```

정책:

| 상황 | 기본 동작 |
| :--- | :--- |
| Trinity resource끼리 id 충돌 | registry load 실패 |
| native와 Trinity 이름 충돌 | prefix namespace 적용 |
| provider config 파일 충돌 | fail 또는 prompt-only degrade |
| 같은 checksum 재투영 | no-op |
| checksum 변경 | 이전 projected dir 폐기 후 재생성 |

## Hook 권한 모델

Hook manifest는 side effect를 선언해야 한다.

```toml
side_effects = "none" # none | read | write | network | exec
access = ["read-only"]
```

허용 matrix:

| Invocation access | 허용 side effects |
| :--- | :--- |
| `read-only` | `none`, `read` |
| `workspace-write` | `none`, `read`, `write` |
| future `network` policy | 명시 opt-in 필요 |
| future `exec` policy | 명시 opt-in 필요 |

Hook이 shell command를 실행해야 한다면 다음을 추가 요구한다.

- command argv는 manifest에 배열로 저장한다. shell string은 금지한다.
- source path는 resource pack 내부여야 한다.
- symlink가 pack root 밖으로 나가면 load 실패한다.
- hook output은 `.trinity/logs/resource-hooks/`에 저장한다.
- read-only turn에서는 workspace write가 감지되면 provider 호출 전에 실패한다.

## 감사 로그

`WorkflowPersistence.append_event()`에 다음 event를 남긴다.

```json
{
  "event": "resource_projection_completed",
  "workflow_id": "wf-...",
  "agent_name": "codex",
  "provider": "codex",
  "pack_id": "trinity-core",
  "resource_id": "implementation-plan",
  "resource_type": "skill",
  "projection_mode": "prompt-only",
  "checksum": "sha256:...",
  "status": "prompt_only"
}
```

추가 event:

- `resource_registry_loaded`
- `resource_projection_started`
- `resource_projection_skipped`
- `resource_projection_failed`
- `resource_hook_blocked`
- `resource_conflict_detected`

UI와 `/status`는 active agent별 resource count를 보여준다.

```text
Resources:
  claude: 2 skills, 0 hooks, prompt-only
  codex: 3 skills, 1 command, managed-overlay
  antigravity: 1 skill, prompt-only
```

## 실패 정책

Resource별 `failure_policy`가 우선한다.

| Policy | 동작 |
| :--- | :--- |
| `degrade` | provider-native projection 실패 시 prompt inventory로 계속 진행 |
| `skip` | 해당 resource만 비활성화하고 provider 호출은 계속 |
| `fail-provider-call` | provider 호출 전에 오류로 중단 |
| `fail-workflow` | workflow state를 failed로 전환 |

기본값은 `degrade`다. 단, hook이 write guard처럼 안전성 보장에 쓰이면 `fail-provider-call`을 쓴다.

## CLI와 UI

추가할 CLI 후보:

```text
trinity resources list
trinity resources inspect <pack-or-resource-id>
trinity resources apply [--agent AGENT] [--lane LANE] [--access ACCESS]
trinity resources doctor
```

Slash command 후보:

```text
/resources
/resources inspect <id>
/resources reload
```

초기 구현에서는 slash command를 조회 전용으로 둔다. resource activation은 config와 workflow start 시점에서
결정하고, 실행 중 reload는 tmux interactive process와 충돌할 수 있으므로 별도 phase로 둔다.

## 구현 단계

### Phase 1: Manifest와 prompt inventory

- `src/trinity/resources/models.py` 추가
- `ResourceRegistry`로 `.trinity/resources/registry.toml`와 pack manifest load
- `ResourcePathResolver`로 project/state/resource/managed-home/overlay path를 OS별로 계산
- `AgentSpec` 또는 별도 config 모델에 resource 설정 추가
- one-shot prompt build 시 prompt inventory 삽입
- workflow event에 prompt-only projection 기록
- manifest와 lock file에는 상대 경로와 checksum을 저장하고, provider prompt에는 provider-visible path만 삽입
- provider config 파일은 수정하지 않음

### Phase 2: Managed overlay projection

- `ResourceProjector`와 provider adapter interface 추가
- `.trinity/agents/<agent>/overlay/projected` 생성
- lock file 기록과 checksum 기반 no-op 처리
- `ManagedHome` 준비 후 provider invocation 전에 projection 적용
- Linux, macOS, Windows env override 생성 로직을 adapter contract로 고정
- path traversal, symlink escape, checksum, OS별 separator test 추가

### Phase 3: Provider-native adapter 확장

- provider별 resource contract smoke test 작성
- 확인된 provider만 native skill/command/hook projection 지원
- hook side effect policy 적용
- `/resources`와 `trinity resources doctor`에 adapter capability 표시

### Phase 4: Workflow resume와 resource revision 고정

- `WorkflowSession.resource_projections` 저장/복원
- workflow archive/restore 시 사용한 pack version/checksum 표시
- pack version 변경 후 resume 시 `changed`, `missing`, `compatible` 상태 판단

## 테스트 기준

| 테스트 | 목적 |
| :--- | :--- |
| manifest parse 성공/실패 | 필수 필드, enum, target provider 검증 |
| path traversal 차단 | `../` source path와 pack 밖 symlink 차단 |
| manifest OS path 차단 | 절대 경로, drive-letter, UNC, backslash source path 거부 |
| path resolver linux/macos/windows | state/resource/home/overlay 경로와 env override가 OS별로 맞는지 검증 |
| prompt inventory provider-visible path | provider cwd 안/밖, git-worktree mode에서 접근 가능한 경로만 표시 |
| WSL/Windows namespace guard | WSL Trinity가 Windows exe path를 자동으로 섞지 않는지 검증 |
| lock file relative path | lock/session에 host 절대 경로 없이 checksum과 상대 경로가 저장되는지 검증 |
| duplicate resource id 실패 | 같은 pack 또는 registry 내 id 충돌 방지 |
| agent target filtering | agent/provider/lane/access 기준 resource 선택 |
| prompt inventory packing | budget 초과 시 summary/path만 유지 |
| projection idempotency | 같은 checksum 재실행 no-op |
| projection checksum 변경 | 이전 projection 폐기 후 새 projection 생성 |
| user-home no-write | provider_state_mode=user-home에서도 real home에 쓰지 않음 |
| isolated home separation | provider-state와 overlay source가 분리됨 |
| hook side effect matrix | read-only에서 write/exec hook 차단 |
| provider adapter fallback | unsupported type은 prompt-only로 degrade |
| workflow persistence | resource projection event와 session state round-trip |

## 수용 기준

- 세 agent가 같은 Trinity resource pack을 agent별 설정에 따라 받을 수 있다.
- native provider resource와 Trinity overlay resource가 provenance와 namespace로 분리된다.
- 기본 동작은 real user home을 수정하지 않는다.
- provider-native projection을 지원하지 않는 경우에도 prompt inventory로 안전하게 사용할 수 있다.
- hook은 access/side effect policy를 통과해야 활성화된다.
- workflow event와 session JSON에서 어떤 resource revision이 쓰였는지 확인할 수 있다.
- resource projection 실패가 provider 호출을 계속할지 막을지 manifest로 제어된다.

## 남은 확인 사항

- Claude Code의 현재 skill/hook 파일 포맷과 외부 overlay path 지정 방법
- Codex CLI의 resource/plugin/skill 설정 contract와 `CODEX_HOME` 또는 config path override 지원 여부
- Antigravity CLI가 prompt 외 resource path를 받을 수 있는지 여부
- Textual UI에서 `/resources` 결과를 central agent log, inspector, modal 중 어디에 표시할지
- resource pack을 repo에 커밋할지, `.trinity/resources`처럼 local state로만 둘지에 대한 배포 정책
