# ExecutionLogModal 렌더 상태 재바인딩 보강

- 브랜치: `perf/execution-log-modal-render-rebind`
- 버전: `1.0.288` -> `1.0.289`
- 대상: `src/trinity/textual_app/widgets/execution_log_modal.py`

## 배경

전체 실행 로그 모달은 검색 상태와 렌더된 라인 목록을 키로 저장해 같은 검색 결과를 반복 렌더하지 않는다. 하지만 모달이 `refresh(recompose=True)`로 다시 그려지면 status/body 위젯은 새로 생성되는데 `_status_text_key`와 `_rendered_lines_key`가 이전 값을 유지할 수 있다.

이 경우 새 body가 비어 있어도 같은 검색어에 대한 `_refresh_log()`가 렌더를 건너뛸 수 있다. 또한 `filter_query`가 남아 있는데 새 Input은 빈 값으로 생성되어 검색어와 UI 표시가 어긋날 수 있다.

## 개선안

1. compose 시작 시 status/body 위젯 캐시와 함께 렌더 상태 키도 초기화한다.
2. 새 검색 Input에는 현재 `filter_query` 값을 넣어 리컴포즈 후 필터 상태와 입력값을 맞춘다.
3. 리컴포즈 후 같은 검색어로 다시 `_refresh_log()`를 호출해도 DOM 재조회 없이 새 status/body에 결과가 렌더되는지 테스트한다.

## 기대 효과

- 전체 실행 로그 모달 리컴포즈 후 빈 로그 화면이 유지되는 상태 불일치를 방지한다.
- 검색어 표시와 실제 필터 상태가 어긋나지 않는다.
- 실행 페이지의 activity log와 full log 모달의 cache 생명주기를 일관되게 맞춘다.
