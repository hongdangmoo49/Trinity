# Gemini 제거 및 Antigravity 전환 구현 결과

- Date: 2026-06-05
- Branch: `codex/replace-gemini-with-antigravity`
- Version: `0.9.1`

## 구현 요약

- 기본 세 번째 agent를 `gemini`에서 `antigravity`로 전환했다.
- `Provider.GEMINI_CLI`를 active provider enum에서 제거했다.
- `src/trinity/legacy/gemini/`와 `src/trinity/agents/gemini_agent.py`를 제거했다.
- `AgentFactory`는 더 이상 Gemini runtime wrapper를 생성하지 않는다.
- legacy `[agents.gemini] provider = "gemini-cli"` config는 load 시
  `[agents.antigravity] provider = "antigravity-cli"`로 마이그레이션된다.
- setup detector는 `gemini` binary를 migration hint로만 감지하고, setup wizard는
  Gemini를 선택 가능한 agent로 만들지 않는다.
- workflow/decomposer/distributor/theme/i18n/test fixtures를 `antigravity` 기준으로
  정리했다.

## 남긴 호환 표면

- Config migration:
  - `[agents.gemini] provider = "gemini-cli"` → `[agents.antigravity]`
  - 임의 agent key의 `provider = "gemini-cli"` → `provider = "antigravity-cli"`
- Setup migration hint:
  - legacy Gemini CLI 감지 시 `agy plugin import gemini` 안내를 표시한다.
- Execution owner alias:
  - 과거 workflow package owner가 `gemini`이고 현재 agent에 `antigravity`가 있으면
    `antigravity`를 실행 후보로 사용한다.
- Response cleaner:
  - 과거 Gemini CLI migration/auth/banner noise 제거 패턴은 유지한다.
- Antigravity 공식 설정 경로:
  - `.gemini/antigravity-cli`는 공식 Antigravity CLI namespace이므로 유지한다.

## 검증

```text
uv run pytest
973 passed, 1 warning in 25.63s
```

```text
uv run trinity status
claude      / claude-code      active
codex       / codex            active
antigravity / antigravity-cli  active
Transport: one-shot
```

## 완료 기준 확인

- `uv run trinity status`에서 세 번째 agent가 `antigravity / antigravity-cli`로 표시된다.
- 새 default config와 template은 `antigravity-cli` / `agy`를 사용한다.
- legacy Gemini config load/save가 canonical Antigravity config로 변환된다.
- Gemini runtime provider enum, factory branch, wrapper 파일이 제거됐다.
- active source의 `gemini-cli` 문자열은 migration warning/config migration/legacy
  cleaner 범위로 제한됐다.
