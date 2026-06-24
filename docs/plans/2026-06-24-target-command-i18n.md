# Target 로컬 명령 한국어 라벨 개선

## 배경

`/target` 명령은 실행 대상 워크스페이스 조회, 초기화, 설정, 제어 저장소 확인 취소, 경로 준비 오류를 Nexus 로컬 명령 결과로 보여준다. 한국어 설정에서도 제목, 본문, action hint, 표 헤더와 행 라벨이 영어로 고정되어 있다.

## 목표

- 한국어 설정에서 `/target` 조회/초기화/설정/취소/오류 결과를 한국어로 표시한다.
- 성공 결과의 표 헤더와 `Path`, `Inside control repo`, `Control repo confirmed` 행 라벨을 한국어화한다.
- 기존 영어 기본 동작과 target workspace 설정 로직은 유지한다.

## 설계

1. `presenters.py`에 target 전용 메시지와 row helper를 추가한다.
2. `TrinityTextualApp`의 `/target` 관련 로컬 결과 기록 지점에서 helper에 `config.lang`을 전달한다.
3. 제어 저장소 확인 취소와 preflight 취소 경로도 동일한 helper를 사용한다.
4. presenter 단위 테스트와 한국어 `/target` 실행 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "target"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
