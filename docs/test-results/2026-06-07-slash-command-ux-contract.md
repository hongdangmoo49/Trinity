# Slash Command UX Contract Validation

작성일: 2026-06-07

브랜치: `codex/slash-command-docs`

## 목적

Trinity slash command를 개별 증상 패치가 아니라 Start/Nexus/plain TUI 전체 UX 계약으로
정리하기 위해 새 계획 문서를 추가했다.

## 변경 문서

- `docs/plans/2026-06-07-trinity-slash-command-ux-contract.md`
  - slash command 입력/자동완성 UX
  - Start/Nexus surface 정의
  - 명령별 Start/Nexus/empty/error/agent-call 계약
  - 구현 순서와 회귀 테스트 기준
- `docs/plans/2026-06-06-trinity-slash-command-routing-design.md`
  - 화면별 UI surface 계약은 새 UX contract를 기준으로 한다는 링크 추가
- `docs/slash-command-reference.md`
  - routing contract와 UX contract의 역할을 분리해 링크 추가
- `docs/checkpoint.md`
  - 최신 Textual slash command UX 기준 문서 링크 추가

## 검증

실행한 명령:

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_slash_command_docs.py -q
git diff --check
```

결과:

- Slash command 문서 정합성: `4 passed in 0.03s`
- `git diff --check` 통과

## 다음 구현 단위

1. 공통 local command result model과 Start/Nexus renderer 정리
2. 조회 명령(`/help`, `/workflow`, `/questions`, `/decisions`, `/packages`, `/subtasks`, `/history`, `/report`) UX 일괄 보강
3. 설정 명령(`/rounds`, `/agent`, `/caveman`) UX 일괄 보강
4. workflow-local 명령(`/target`, `/resume`, `/questions --select`, `/answer`) UX 보강
5. 실행/종료/unknown command UX 마감
