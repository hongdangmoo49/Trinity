# Workspace Picker 한국어 라벨 개선

## 배경

Nexus 액션바와 Provider Inspector는 한국어 라벨을 따르도록 개선되었지만, 작업 폴더 선택/생성 흐름의 Workspace Picker에는 `New Folder`, `Cancel`, `Confirm Execute`, preflight 항목명, 폴더 생성 상태 메시지가 영어로 남아 있다. 실행 전에 사용자가 반드시 거치는 화면이므로 언어 일관성을 맞출 필요가 있다.

## 목표

- Workspace Picker 제목, 버튼, 입력 placeholder를 언어 설정에 맞춰 표시한다.
- preflight 패널 항목명을 한국어 설정에서 한국어로 표시한다.
- 폴더 생성 prompt와 생성/오류 상태 메시지를 한국어 설정에 맞춘다.
- 영어 기본값과 기존 폴더 생성/확인 동작은 유지한다.

## 설계

1. `workspace_picker.py`에 언어별 라벨 맵과 `_label()`, `_format_label()` helper를 추가한다.
2. `WorkspacePreflight.render(lang="en")`으로 확장해 기존 호출은 영어를 유지하고, Picker에서는 `self.lang`을 전달한다.
3. `CreateMissingDirectoryPrompt`, `FolderNamePrompt`, `WorkspacePicker`의 compose/status 메시지에 helper를 적용한다.
4. 기존 영어 테스트는 유지하고, 한국어 preflight/render/chrome/status 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_workspace_picker.py`
- `uv run pytest tests/test_textual_app.py -k "workspace_picker or select_workspace"`
- `uv run pytest`
- `uv run trinity --version`
