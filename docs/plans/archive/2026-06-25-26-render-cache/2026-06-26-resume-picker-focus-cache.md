# ResumeWorkflowPicker 포커스 캐시 보강

- 브랜치: `perf/resume-picker-focus-cache`
- 버전: `1.0.284` -> `1.0.285`
- 대상: `src/trinity/textual_app/widgets/resume_picker.py`

## 배경

워크플로우 재개 모달은 저장된 세션 목록에서 방향키로 선택 항목을 이동한다. 기존 `_focus_selected_archive()`는 매 이동마다 `.resume-archive-option` 버튼 목록과 `#resume-archive-list` 스크롤 컨테이너를 DOM에서 다시 조회한다.

저장 세션이 많거나 방향키 입력이 연속으로 들어오는 경우, 포커스 이동은 사용자 입력 경로이므로 compose 시점에 이미 생성한 버튼과 컨테이너를 재사용하는 편이 더 안정적이다.

## 개선안

1. compose 시작 시 archive 버튼 캐시와 스크롤 컨테이너 캐시를 초기화한다.
2. archive 버튼을 생성하는 즉시 `_archive_buttons`에 저장한다.
3. `VerticalScroll` 컨테이너도 compose 시점에 `_archive_list_widget`으로 저장한다.
4. `_focus_selected_archive()`는 캐시를 우선 사용하고, 캐시가 비어 있을 때만 DOM 조회로 복구한다.
5. 방향키 이동이 `query()`/`query_one()` 없이 캐시된 컨트롤만 사용하는지 테스트한다.

## 기대 효과

- 재개 모달에서 방향키 이동 시 반복 DOM 조회를 줄인다.
- compose/recompose 이후 캐시가 새 위젯으로 재바인딩되는 흐름을 명확히 한다.
- 실행 재개 UX의 입력 반응성을 조금 더 안정화한다.
