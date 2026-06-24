# Workflow Inspector 의존성 상세 라벨 한국어화

## 배경

Nexus 실행/계획 화면은 한국어 설정을 점진적으로 반영하고 있지만, Workflow Inspector는 `lang` 값을 받지 않아 진행 요약과 의존성 상세 라벨이 영어로 고정된다. 특히 `waiting on WP-002`, `repair 2/2`, `+1 more`, `group 2` 같은 문구는 한국어 UI에서 섞여 보이며, 사용자가 다음 작업의 대기 이유나 차단 상태를 빠르게 읽기 어렵다.

## 목표

- `WorkflowInspector`가 `TrinityConfig.lang`을 받아 렌더링에 사용한다.
- 진행 요약, Next 의존성 상세, Blocked 복구 시도 상세, 초과 항목 표기를 한국어로 표시한다.
- 영어 기본 동작과 기존 테스트 기대값은 유지한다.

## 설계

1. `WorkflowInspector` 생성자에 `lang` 인자를 추가하고 `NexusScreen`에서 `config.lang`을 전달한다.
2. `progress_summary_line`, `next_work_package_line`, `waiting_on_detail_line`, `blocked_detail_line`에 언어 인자를 적용한다.
3. 한국어일 때 다음 라벨을 사용한다.
   - `group 2` -> `그룹 2`
   - `waiting on WP-002` -> `대기: WP-002`
   - `+1 more` -> `외 1개`
   - `repair 2/2` -> `복구 2/2`
   - `(none)` -> `(없음)`
4. Korean 설정의 Nexus 화면 테스트를 추가해 Inspector가 실제 앱 언어를 반영하는지 검증한다.
5. 전체 테스트 중 드러난 `CentralAgentView._should_show_repair_actions` presenter 분리 호환성을 얇은 위임 메서드로 복구한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "workflow_inspector"`
- `uv run pytest tests/test_textual_app.py`
- `uv run trinity --version`
