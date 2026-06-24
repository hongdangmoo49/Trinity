# Report Markdown export 한국어 라벨 개선

## 배경

Report 화면 chrome은 한국어 설정을 따르게 되었지만, in-memory snapshot fallback으로 저장되는 Markdown 본문은 `Deliberation Report`, `Providers`, `Execution Log`, `Status` 같은 영어 라벨로 고정되어 있다. 한국어 설정 사용자가 아직 persisted session이 없는 상태에서 리포트를 저장할 때 화면과 산출물의 언어가 달라지는 문제가 있다.

## 목표

- `snapshot_report_markdown()`에 `lang` 인자를 추가하되 기본값은 영어로 유지한다.
- 한국어 설정의 snapshot fallback export에서 Markdown 제목, 주요 필드, 섹션 제목, 실행 복구/라우팅/품질 라벨을 한국어로 저장한다.
- 사용자 입력, provider 원문, ID, 상태 값 같은 원자료는 번역하지 않는다.
- persisted `DeliberationReport.to_markdown()` 경로는 별도 구조가 크므로 이번 범위에서는 기존 영어 동작을 유지한다.

## 설계

1. `report_export.py`에 Markdown 라벨 맵과 `_label()` helper를 추가한다.
2. 기존 helper들에 `lang` 인자를 선택적으로 전달해 영어 기본 동작을 유지한다.
3. `TrinityTextualApp._export_report_markdown()`의 snapshot fallback 분기에서 `snapshot_report_markdown(snapshot, lang=self.config.lang)`을 호출한다.
4. 기존 영어 테스트는 그대로 유지하고, 한국어 Markdown export 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "snapshot_report_markdown or textual_export"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `uv run trinity --version`
