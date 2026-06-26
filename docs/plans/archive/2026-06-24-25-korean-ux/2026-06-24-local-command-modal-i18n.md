# Local Command 모달 한국어 라벨 개선

## 배경

Start 화면에서 `/status`, `/workflow` 같은 로컬 slash command를 실행하면 별도 모달이 열린다. 한국어 설정에서도 `Status`, `Current local status...`, `Close` 등 모달 chrome이 영어로 고정되어 있어 앞서 개선한 Nexus/Workspace/Inspector 흐름과 일관성이 떨어진다.

## 목표

- `StatusCommandModal`이 언어 설정을 받아 제목, 안내 문구, 닫기 버튼, 빈 테이블 문구를 한국어로 표시한다.
- `LocalCommandModal`이 언어 설정을 받아 닫기 버튼과 닫기 바인딩 설명을 한국어로 표시한다.
- 앱에서 모달을 열 때 `config.lang`을 전달한다.
- 로컬 command 결과 원문(`title`, `body`, table data)은 기존 스냅샷 결과를 유지한다.

## 설계

1. 두 모달에 `lang` 인자를 추가하고 `localize_bindings()`를 적용한다.
2. `StatusCommandModal`에는 작은 라벨 맵과 `_label()` helper를 추가한다.
3. `TrinityTextualApp`의 local command/status 모달 push 지점에서 `config.lang`을 전달한다.
4. 기존 영어 테스트는 유지하고, 한국어 설정에서 모달 chrome이 바뀌는 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "status_modal or slash_workflow_uses_generic_local_command_modal or korean_local_command"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `uv run trinity --version`
