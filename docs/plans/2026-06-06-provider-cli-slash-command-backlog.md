# Provider CLI Slash Command Backlog

작성일: 2026-06-06

상태: 후속 과제

## 목적

Trinity 앱 자체 slash command와 provider CLI 내부 slash command를 분리한다. 현재
Trinity의 `/status`, `/execute` 같은 명령은 Trinity workflow와 Textual/Plain TUI를
제어하는 top-level 명령이다. 반면 Claude, Codex, Antigravity CLI 내부의 slash command와
`.trinity/agents/*/provider-state` 아래에 캐시된 외부 플러그인 문서의 slash command는
provider 런타임 또는 외부 플러그인의 명령 체계다.

이 둘을 같은 팔레트에 섞으면 다음 문제가 생긴다.

- 이름 충돌: provider의 `/status`, `/help`, `/model` 등이 Trinity의 `/status`, `/help`와
  다른 의미를 가질 수 있다.
- 실행 경계 혼동: Trinity 로컬 UI 명령이어야 하는 입력이 provider 모델 호출 또는 provider
  내부 도구 호출로 넘어갈 수 있다.
- 버전 드리프트: provider CLI와 플러그인 캐시는 사용자 환경, 인증 상태, 설치 버전에 따라
  수시로 달라진다.
- 캐시 노이즈: `.trinity/agents/*/provider-state` 아래에는 외부 문서, 예제, changelog,
  marketplace cache가 섞일 수 있어 Trinity 앱의 공식 명령 정의로 사용할 수 없다.

## 현재 범위에서 제외하는 것

이번 Trinity slash command 설계에서는 다음을 정의하지 않는다.

| 범위 | 예시 | 제외 이유 |
| :--- | :--- | :--- |
| Claude CLI 내부 slash command | `/model`, `/permissions`, `/mcp`, 플러그인 명령 | Claude CLI 버전과 설치 플러그인에 종속된다. |
| Codex CLI 내부 slash command | Codex 대화형 세션 내부 command | Codex 런타임, auth, 플러그인 상태에 종속된다. |
| Antigravity CLI 내부 slash command | Antigravity 대화형 command | 현재 Trinity provider adapter 밖의 런타임 계약이다. |
| provider-state 캐시의 외부 플러그인 문서 | `.trinity/agents/*/provider-state/**/plugins/**` | 문서/예제/캐시이며 Trinity 앱 명령이 아니다. |
| provider command pass-through | Trinity에서 provider CLI command를 대신 보내는 기능 | 명시적 UX와 보안 정책 없이 허용하면 위험하다. |

## 후속 조사 항목

1. 현재 설치된 provider CLI 버전을 기록한다.
   - `claude --version`
   - `codex --version`
   - Antigravity CLI version command
2. 각 provider의 공식 slash command 목록을 provider별로 수집한다.
   - 공식 문서 또는 CLI 내장 help를 우선한다.
   - user/plugin cache에서 발견한 명령은 별도 "local extension"으로 분류한다.
3. `.trinity/agents/*/provider-state` 아래 cache를 inventory한다.
   - command 정의 파일과 단순 문서/예제를 분리한다.
   - credentials, user prompt, session transcript는 수집 대상에서 제외한다.
4. Trinity top-level command와 이름 충돌을 분석한다.
   - 충돌 command는 Trinity 명령을 우선한다.
   - provider 명령은 별도 namespace 또는 pass-through UX가 필요하다.
5. pass-through 정책을 설계한다.
   - 예: `/provider claude /model sonnet`
   - 기본값은 disabled가 안전하다.
   - 실행 전 provider, target session, side effect를 표시해야 한다.
6. Textual palette 노출 정책을 정한다.
   - Trinity 앱 command는 기본 팔레트에 노출한다.
   - provider command는 opt-in filter 또는 provider-specific palette에서만 노출한다.

## 수용 기준

- Trinity 앱의 top-level slash command 목록은 provider cache와 무관하게 결정된다.
- `.trinity/agents/*/provider-state` 아래 문서나 plugin cache가 Trinity palette 후보를
  자동으로 늘리지 않는다.
- provider CLI command inventory에는 수집 날짜, provider version, 출처가 기록된다.
- 이름이 충돌하는 provider command는 Trinity command로 오인되지 않는다.
- provider pass-through를 구현할 경우 명시적 namespace와 사용자 확인 정책이 있다.
- secrets, auth token, transcript를 문서화 산출물에 포함하지 않는다.

## 향후 산출물

| 산출물 | 목적 |
| :--- | :--- |
| `docs/provider-cli-command-inventory.md` | provider별 내부 command 목록과 출처 기록 |
| `docs/plans/provider-command-pass-through.md` | provider command pass-through UX와 안전 정책 설계 |
| `tests/test_provider_command_inventory.py` | provider cache가 Trinity command registry를 오염시키지 않는지 검증 |
| `tests/test_textual_provider_palette.py` | provider-specific palette를 만들 경우 노출/필터링 검증 |

## 현재 결정

Trinity v0.10.3 기준 slash command 설계의 source of truth는 Trinity 앱 자체 명령만
다룬다. provider CLI 내부 slash command와 외부 플러그인 cache command는 이 문서의
후속 과제로 남긴다.
