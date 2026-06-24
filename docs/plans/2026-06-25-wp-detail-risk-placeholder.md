# WP 상세 리스크 placeholder 지역화

## 배경

Nexus 실행 화면의 작업 패키지 상세 모달은 대부분의 섹션 라벨과 빈 값 placeholder를 한국어로 표시한다. 다만 `risk` 값이 비어 있는 경우 본문에 `unknown`이 직접 출력되어 한국어 UI에서 영어 fallback이 남는다.

상태값은 등록되지 않은 provider/workflow 상태를 그대로 보여주는 것이 디버깅에 유리하므로, 기존 unknown status 보존 동작은 유지한다.

## 목표

- 한국어 모달에서 비어 있는 리스크 값을 `알 수 없음`으로 표시한다.
- 영어 모달의 기존 표시인 `unknown`은 유지한다.
- 미등록 상태값 보존 테스트와 충돌하지 않도록 변경 범위를 `risk` fallback에 한정한다.

## 작업 범위

1. `WorkPackageDetailModal` 라벨 사전에 `unknown` placeholder를 추가한다.
2. `package.risk`가 비어 있을 때 하드코딩된 `unknown` 대신 지역화 라벨을 사용한다.
3. 한국어/영어 렌더링 회귀 테스트를 추가한다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/widgets/work_package_detail_modal.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "work_package_detail_modal"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest -q`
