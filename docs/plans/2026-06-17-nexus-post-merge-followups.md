# Nexus Post-Merge Follow-up Plan

작성일: 2026-06-17

브랜치: `feature/nexus-post-merge-followups`

상태: 병렬 구현 완료

## 배경

`feature/nexus-dependency-ready-next`가 PR #67로 `main`에 병합되면서 Nexus Inspector의 `Next`는
dependency-ready WP를 먼저 표시하게 되었다. 남은 후속작업은 실제 화면 체감, provider card 정보 보강,
Execution Matrix와 Nexus 상태 표현 통일, Inspector 복잡도 관리다.

## 병렬 트랙

### 1. Provider Card Model/Session 보강

목표:

- provider card에 현재 모델, provider-native session id 축약값, context/budget 상태를 한 줄로 표시한다.
- card를 다시 장황하게 만들지 않는다.
- 상세 정보는 Provider Inspector에 유지한다.

주요 파일:

- `src/trinity/textual_app/widgets/provider_panel.py`
- `src/trinity/textual_app/screens/nexus.py`
- `tests/test_provider_panel.py`

### 2. Execution Matrix 상태 라벨 통일

목표:

- Execution Matrix의 raw status 표시를 Nexus vocabulary와 맞춘 compact label로 바꾼다.
- 표시 전용 변경으로 유지하고 snapshot/session 상태 값은 바꾸지 않는다.

주요 파일:

- `src/trinity/textual_app/screens/execution_matrix.py`
- `tests/test_textual_app.py`

### 3. 실제 TUI QA 기준 정리

목표:

- compact provider strip, 긴 provider 이름, 한국어 상태 라벨, Inspector 밀도, progress bar 작은 터미널
  가독성을 확인한다.
- brittle screenshot 테스트보다 유지보수 가능한 focused test를 우선한다.

후보 검증:

- `ProviderPanel` pure helper 테스트
- Textual `run_test(size=(...))` 기반 compact viewport smoke
- Inspector content assertion

## 통합 원칙

- 각 트랙은 가능한 한 파일 소유 범위를 좁힌다.
- 공통 status label helper가 필요하면 중복 구현을 제거하고 하나의 small helper로 모은다.
- 시각 QA는 자동 테스트로 잡히는 부분과 실제 실행 확인이 필요한 부분을 분리해 기록한다.
- 중앙 `CentralAgentView`는 계속 compact 계약을 유지하고, 상세 정보는 Inspector/Provider Inspector/Execution Matrix에 둔다.

## 구현 결과

### Provider Card Model/Session

- `ProviderPanelState`에 model/context/budget/session projection 필드를 추가했다.
- Nexus snapshot 적용 경로에서 `ProviderSnapshot`의 `configured_model`, `actual_model`, `model_label`,
  `context_window`, `budget_source`, `session_id`를 provider card로 전달한다.
- 초기 config 기반 provider card도 configured model/context budget 힌트를 받는다.
- provider meta row는 `provider · model · ctx 272K/local · sid 019ea9e3`처럼 한 줄로만 표시한다.
- summary와 meta row 모두 기존 72자 compact truncation을 유지한다.

### Execution Matrix Status

- `widgets/status_label.py`를 추가해 compact status group/label mapping을 공유한다.
- Execution Matrix의 status column은 raw status 대신 `RUN`, `WAIT`, `DONE`, `ISSUE`, `IDLE`, `?`를 표시한다.
- ProviderPanel도 같은 status group helper를 사용해 Nexus/Matrix 상태 bucket이 어긋나지 않게 했다.
- snapshot/session의 원본 status 값은 바꾸지 않고 display-only로 처리했다.

### TUI QA Regression

- 한국어 provider 상태 라벨을 running/waiting/idle/done/issue/off/unknown 버킷으로 확장 검증했다.
- `progress_bar()`의 width compaction 경로를 검증해 작은 Inspector에서도 bar 폭이 제한되고 nonzero state marker가 유지되도록 했다.
- `80x24` Nexus viewport에서 provider strip과 provider panel 높이가 5줄 계약을 유지하고, `Antigravity`
  provider name/status/meta가 렌더되는지 확인하는 Textual test를 추가했다.

## 검증 결과

```text
/home/user/workspace/Trinity/.venv/bin/python -m pytest \
  /home/user/workspace/Trinity/tests/test_provider_panel.py \
  /home/user/workspace/Trinity/tests/test_progress_summary.py \
  /home/user/workspace/Trinity/tests/test_central_agent_view.py \
  /home/user/workspace/Trinity/tests/test_textual_app.py \
  -q

158 passed in 63.27s (0:01:03)
```

```text
/home/user/workspace/Trinity/.venv/bin/python -m pytest \
  /home/user/workspace/Trinity/tests/test_textual_snapshot.py \
  /home/user/workspace/Trinity/tests/test_textual_workflow_controller.py \
  /home/user/workspace/Trinity/tests/test_textual_smoke.py \
  -q

66 passed in 2.27s
```

## 최신 후속 상태

2026-06-24 기준 추가 완료:

- Report 화면 진입 시 workflow event tail만 읽도록 제한했다.
- Workflow event index JSONL은 동일 파일 상태에서 반복 파싱하지 않도록 캐시한다.
- `NexusSnapshotAdapter` fallback helper도 full event load로 되돌아가지 않도록 tail/slice 기반으로 제한했다.
- large workflow snapshot projection이 full event scan으로 회귀하지 않도록 performance budget test를 추가했다.
- 위 후속 PR들은 GitHub Actions cross-platform smoke를 통과했다.

남은 후속:

- 실제 터미널에서 `80x24`, `100x30`, `120x40` 크기와 한국어 설정으로 눈검증한다.
- Inspector 섹션이 더 늘어나는 경우 `Overview`, `Details`, `Log` 탭화 또는 접힘 구조를 별도 브랜치에서 검토한다.
- review queued/started/completed/skipped 이벤트를 추가해 reviewer별 상태를 더 세밀하게 표시한다.
