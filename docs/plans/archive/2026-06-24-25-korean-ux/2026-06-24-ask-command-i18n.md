# Ask 로컬 명령 한국어 라벨 개선

## 배경

`/ask` 명령은 특정 에이전트나 전체 에이전트에게 후속 질문을 라우팅한다. 정상 경로는 워크플로우 실행으로 이어지지만, 인자 누락, 알 수 없는 에이전트, 활성 에이전트 없음, 모델 누락, 빈 프롬프트 같은 로컬 검증 오류는 Nexus 로컬 명령 결과로 표시된다. 한국어 설정에서도 이 오류 제목, 본문, action hint가 영어로 고정되어 있다.

## 목표

- 한국어 설정에서 `/ask` 로컬 검증 오류 제목, 본문, action hint를 한국어로 표시한다.
- `/ask <all|agent[,agent...]> [--model MODEL] <prompt>` 명령 형식은 원문 그대로 유지한다.
- 정상 start/follow-up 라우팅과 provider 호출 경로는 변경하지 않는다.
- 기존 영어 기본 동작은 유지한다.

## 설계

1. `presenters.py`에 ask 전용 title/usage/error helper를 추가한다.
2. `_parse_ask_args()`가 오류 코드와 값만 반환하도록 변경하지 않고, 최소 변경으로 `config.lang`에 맞는 문자열을 직접 반환하도록 helper를 호출한다.
3. `_handle_textual_ask_command()`의 로컬 오류 결과 title/action hint를 helper 기반으로 교체한다.
4. presenter 단위 테스트와 한국어 `/ask` 오류 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "ask"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
