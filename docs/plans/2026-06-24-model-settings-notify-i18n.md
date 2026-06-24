# Model Settings 알림 한국어 라벨 개선

## 배경

모델 설정 모달을 열 수 없는 화면에서 표시되는 경고와 모델 선택 적용 완료 알림이 영어로 고정되어 있다. 한국어 설정에서 Start/Nexus의 모델 선택 UX는 한국어를 지원하지만, 알림 문구가 영어로 남아 있다.

## 목표

- 한국어 설정에서 모델 설정 사용 불가 경고를 한국어로 표시한다.
- 한국어 설정에서 모델 설정 적용 완료 알림을 한국어로 표시한다.
- 영어 기본 문구는 유지한다.

## 설계

1. `presenters.py`에 model settings title/unavailable/updated helper를 추가한다.
2. `_open_model_settings_modal()`과 `_on_model_settings_applied()`에서 helper를 사용한다.
3. helper 단위 테스트와 앱 알림 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "model_settings"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
