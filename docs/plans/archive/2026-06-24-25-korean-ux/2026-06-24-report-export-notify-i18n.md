# Report Export 알림 한국어 라벨 개선

## 배경

`/report save` 로컬 명령 결과는 한국어 라벨을 지원하지만, 실제 Markdown 파일을 저장하는 `_export_report_markdown()`의 notify 제목과 본문은 영어로 고정되어 있다. Report 화면에서 `Ctrl+S` 또는 export 버튼을 사용할 때 한국어 UI 안에 영어 알림이 섞인다.

## 목표

- 한국어 설정에서 export 불가 알림 제목과 본문을 한국어로 표시한다.
- 한국어 설정에서 export 완료 알림 제목과 저장 경로 본문을 한국어로 표시한다.
- 기존 `/report save` 로컬 명령 결과 helper와 의미를 맞춘다.
- 영어 기본 동작은 유지한다.

## 설계

1. `presenters.py`에 export unavailable/complete title helper와 saved notification helper를 추가한다.
2. `_export_report_markdown()`에서 `config.lang`을 기준으로 notify 문구를 생성한다.
3. 빈 snapshot과 한국어 snapshot export 경로 테스트에서 notify 내용을 검증한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "report or export"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
