# Review Repair 로컬 결과 한국어 라벨 개선

## 배경

review repair loop guard가 실행을 멈추면 Nexus 중앙 패널에 `/review` 로컬 결과가 기록된다. 현재 제목, 안내문, 표 컬럼, 상세 설명이 영어로 고정되어 있어 한국어 UI 흐름에서 이질적으로 보인다.

## 목표

- 한국어 설정에서 review repair 결과 제목과 action hint를 한국어로 표시한다.
- review repair 상세 본문과 표 컬럼을 언어 설정에 맞게 표시한다.
- 기존 영어 기본 출력과 내부 reason/status 토큰은 유지한다.
- recovery-only 후보와 work package 기반 후보 모두 기존 동작을 유지한다.

## 설계

1. `presenters.py`에 review repair title/action/table helper를 추가한다.
2. `review_repair_details_markdown()`과 `review_repair_rows()`에 선택적 `lang` 인자를 추가한다.
3. `TrinityTextualApp._present_review_repair_details()`에서 `config.lang`을 전달한다.
4. 기존 영어 테스트는 유지하고 한국어 presenter/app 경로를 추가 검증한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "review_repair"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
