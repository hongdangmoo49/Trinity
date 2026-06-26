# Risk and Severity Label Localization

## 배경

상태값과 source 메타데이터는 한국어 표시 라벨로 정리되었지만, WP 상세/실행 매트릭스/Inspector/후속 보강 목록에는 `high`, `medium`, `low`, `unknown` 같은 risk/severity 원본값이 그대로 노출된다. 한국어 UI에서는 작업 위험도와 리뷰 심각도를 빠르게 읽을 수 있어야 한다.

## 목표

- risk 값(`high`, `medium`, `low`, `unknown`)을 한국어 표시 라벨로 렌더링한다.
- severity 값(`critical`, `high`, `medium`, `low`, `info`)을 한국어 표시 라벨로 렌더링한다.
- WP 상세 모달, 실행 매트릭스, 중앙 에이전트 후속 보강, Inspector, `/improve` presenter에 적용한다.
- snapshot 원본값과 persistence 형식은 변경하지 않는다.

## 비목표

- routing `kind`나 profile revision 같은 내부 분류는 이번 작업에서 번역하지 않는다.
- blueprint 원문 Markdown 내부의 risk 문장은 provider/central 출력이므로 그대로 둔다.
- 영어 UI 표기는 기존 raw 값을 유지한다.

## 설계

1. `trinity.display_labels`에 `display_risk_value()`와 `display_severity_value()`를 추가한다.
2. 화면 렌더링 지점에서만 헬퍼를 호출한다.
3. 상태/source 라벨 작업과 같은 패턴으로 테스트는 한국어 UI의 기대값을 보강하고 영어 회귀는 기존 기대값을 유지한다.

## 검증

- `uv run pytest tests/test_textual_app.py tests/test_report.py -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
