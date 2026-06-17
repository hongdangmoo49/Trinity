# Nexus Post-Merge Follow-up Plan

작성일: 2026-06-17

브랜치: `feature/nexus-post-merge-followups`

상태: 병렬 진행 중

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
