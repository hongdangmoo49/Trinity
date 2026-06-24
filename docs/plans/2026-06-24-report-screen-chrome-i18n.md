# Report 화면 chrome 한국어 라벨 개선

## 배경

Report 화면은 한국어 설정에서도 `Deliberation Report`, `Export Markdown`, `Saved:` 같은 상단 chrome 문구가 영어로 고정되어 있다. Report 본문과 Markdown export 내용은 별도의 더 큰 범위이지만, 화면 상단의 고정 요소는 작은 패치로 먼저 정리할 수 있다.

## 목표

- Report 화면 제목, export 버튼, export 완료 상태, 로딩/빈 상태 문구를 언어 설정에 맞춰 표시한다.
- Report 화면 key binding 설명도 한국어 설정을 따른다.
- Report 본문 섹션명과 Markdown export 내용은 기존 동작을 유지한다.
- 앱에서 ReportScreen을 설치할 때 `config.lang`을 전달한다.

## 설계

1. `ReportScreen`에 `lang` 인자와 라벨 맵을 추가한다.
2. `compose()`, `show_export_path()`, 빈 상태 렌더링에서 `_label()`을 사용한다.
3. `LOCALIZED_BINDINGS`를 추가하고 `localize_bindings()`로 `ctrl+s`, `escape` 설명을 갱신한다.
4. 기존 report 렌더링 테스트는 유지하고, 한국어 chrome 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "report_screen"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `uv run trinity --version`
