# Task and Action Kind Label Localization

## 배경

상태, source, risk/severity 라벨은 한국어 표시로 정리되었지만, 작업 유형과 후속 조치 kind는 여전히 `implementation`, `validation`, `test` 같은 내부 분류값으로 노출된다. 특히 `/improve` 결과 행의 `kind=test`와 리포트/WP 상세의 `종류 implementation`은 한국어 UI의 일관성을 깨뜨린다.

## 목표

- 작업 유형/후속 조치 kind 값을 한국어 표시 라벨로 렌더링한다.
- `/improve` 행, 리포트 라우팅 요약, WP 상세 모달에 적용한다.
- snapshot 원본값과 workflow/routing 내부 분류는 변경하지 않는다.

## 비목표

- profile revision, routing reason, session kind 같은 진단용 원본값은 변경하지 않는다.
- 영어 UI는 기존 raw kind 값을 유지한다.
- provider/central 원문 Markdown 내부의 자유 텍스트는 번역하지 않는다.

## 설계

1. `trinity.display_labels.display_kind_value()`를 추가한다.
2. 후속 조치 kind와 task kind가 공유하는 주요 값을 같은 라벨 맵으로 처리한다.
3. 한국어 presenter/report/widget 렌더링에서만 표시 라벨을 사용한다.
4. 테스트는 한국어 UI 기대값을 갱신하고 영어 raw 값 유지 테스트는 그대로 둔다.

## 검증

- `uv run pytest tests/test_textual_app.py tests/test_report.py -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
