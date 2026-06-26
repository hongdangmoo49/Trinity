# Nexus 액션바 문구 한국어화

## 배경

한국어 설정에서도 Nexus 상단 액션바의 핵심 버튼과 워크스페이스 라벨, Composer placeholder가 영어로 고정되어 있다. 사용자는 실행 페이지에서 가장 먼저 이 영역을 보게 되므로, 버튼 라벨이 한국어 UI와 섞이면 흐름이 덜 자연스럽다.

## 목표

- 한국어 설정에서 Nexus 액션바 버튼을 한국어로 표시한다.
- 워크스페이스 라벨의 선택/미선택 상태를 한국어로 표시한다.
- Composer placeholder를 한국어로 표시한다.
- 영어 기본값과 기존 레이아웃, 버튼 ID, 이벤트 동작은 유지한다.

## 설계

1. `NexusScreen`에 간단한 라벨 맵과 `_label()` helper를 추가한다.
2. `compose()`에서 버튼 라벨과 Composer placeholder를 `_label()`로 렌더링한다.
3. `_workspace_label()`에서 `Workspace: ...`, `Workspace: not selected`를 언어별로 분기한다.
4. 기존 영어 테스트는 유지하고, 한국어 설정의 액션바/워크스페이스/placeholder 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "nexus_select_workspace or nexus_action_bar"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `uv run trinity --version`
