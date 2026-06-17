# Default Target Workspace From CLI CWD

작성일: 2026-06-17

브랜치: `feature/default-target-workspace-cwd`

상태: 구현 완료

## 배경

Textual workbench 시작 시 target workspace가 `Not selected`로 보이면 사용자가 실행 전에 별도 선택을 해야
한다고 느낀다. Trinity는 CLI 환경에서 실행되는 도구이므로, 사용자가 `trinity`를 실행한 현재 작업 경로를
기본 target workspace 후보로 보여주는 편이 자연스럽다.

## 목표

1. Textual app 시작 시 `Path.cwd()`를 기본 workspace candidate로 설정한다.
2. Start 화면의 `Target workspace` label이 처음부터 실행 경로를 보여주게 한다.
3. 시작 prompt 또는 `/ask`로 workflow를 시작할 때 기본 후보가 안전한 target이면 workflow target으로 전달한다.
4. 자동 target이 설정된 경우 Execution Matrix header도 `workspace: not selected`가 아니라 해당 경로를 보여준다.
5. control repo 내부 쓰기 안전장치는 유지한다.

## 비목표

- provider workspace-write safety guard를 완화하지 않는다.
- control repo 내부 경로를 사용자 확인 없이 자동 승인하지 않는다.
- WorkspacePicker UI 구조를 바꾸지 않는다.

## 구현 결과

- `TrinityTextualApp`이 생성될 때 `launch_cwd`를 캡처하고, 기본 `workspace_candidate`로 사용한다.
- production 경로에서는 `launch_cwd`를 생략하면 `Path.cwd()`가 사용된다.
- 테스트에서는 `launch_cwd`를 주입할 수 있게 해 cwd 의존성을 명시적으로 검증한다.
- start prompt와 start 화면 `/ask` 경로에서 safe target이 전달되면 `confirmed_preflight`도 함께 생성한다.
- `/target <path>`로 target을 설정한 경우에도 `confirmed_preflight`를 갱신해 Execution Matrix header가 즉시 맞춰진다.
- `/target clear`는 `confirmed_preflight`를 해제한다.
- launch cwd가 control repo 내부이면 Start 화면에는 후보로 표시하되, workflow target으로는 자동 저장하지 않는다.

## 검증

```text
/home/user/workspace/Trinity/.venv/bin/python -m pytest \
  /home/user/workspace/Trinity/tests/test_textual_app.py \
  -k "start_screen_defaults_target_workspace or launch_cwd_inside_control_repo or start_submission_persists_selected_workspace_target or target_path_inside_control_repo or target_path_outside_control_repo or workspace_preflight_inside_control_repo" \
  -q

6 passed, 121 deselected in 4.13s
```

```text
/home/user/workspace/Trinity/.venv/bin/python -m pytest \
  /home/user/workspace/Trinity/tests/test_textual_app.py \
  /home/user/workspace/Trinity/tests/test_textual_workspace_picker.py \
  /home/user/workspace/Trinity/tests/test_textual_workflow_controller.py \
  -q

169 passed in 68.11s (0:01:08)
```

## 남은 확인

- 실제 CLI에서 target workspace로 삼을 프로젝트 폴더에서 `trinity`를 실행했을 때 Start 화면 label과 Execution Matrix header가 기대 경로를 보여주는지 눈검증한다.
- control repo에서 직접 실행하는 경우에는 기존처럼 execution 전 confirmation 경로가 유지되는지 확인한다.
