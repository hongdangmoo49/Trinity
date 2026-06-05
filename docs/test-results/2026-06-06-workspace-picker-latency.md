# Workspace Picker Latency Follow-up

작성일: 2026-06-06

브랜치: `codex/execution-matrix-hardening`

## 문제

`Choose now` 클릭 후 workspace picker가 뜨기 전 화면이 멈춘 것처럼 보였다.

## 원인

- 시작 화면의 조기 workspace 선택은 work package 정보가 필요 없는데도
  `workflow_controller.snapshot()`을 호출해 persisted workflow state를 읽었다.
- `WorkspacePicker.compose()`가 `DirectoryTree`를 즉시 생성했다. Textual
  `DirectoryTree`는 mount 후 root directory loader를 시작하고, 각 child path에
  `is_dir()` stat을 수행한다. 느린 workspace root, 마운트, 대형 프로젝트가 있으면
  모달이 뜨기 전 UI thread가 멈춘 것처럼 보일 수 있다.

## 수정

- `Choose now` 경로에서는 빈 `WorkflowNexusSnapshot()`을 사용해 불필요한
  workflow snapshot 로드를 제거했다.
- Workspace picker는 placeholder를 먼저 렌더링하고, `DirectoryTree`는 0.2초 뒤
  지연 mount한다. 따라서 입력창, preflight, 버튼이 먼저 표시되고 폴더 tree는
  뒤따라 로드된다.

## 검증

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_textual_workspace_picker.py tests/test_textual_app.py::test_start_choose_now_opens_workspace_picker tests/test_textual_app.py::test_start_choose_now_updates_workspace_candidate -q
```

결과:

```text
13 passed in 3.48s
```

```bash
/home/zaemi/.local/bin/uv run --with ruff ruff check src/trinity/textual_app/app.py src/trinity/textual_app/widgets/workspace_picker.py tests/test_textual_workspace_picker.py tests/test_textual_app.py
```

결과:

```text
All checks passed!
```

```bash
/home/zaemi/.local/bin/uv run pytest -q
```

결과:

```text
1159 passed, 1 warning in 48.91s
```
