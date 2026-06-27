# CI Docs Version Fast Path

## 목적

문서와 패치 버전만 바뀐 PR에서 3플랫폼 required smoke 전체를 반복 실행하는 비용을 줄인다.

## 범위

- 변경 파일을 `docs_version_only`와 `required_smoke`로 분류하는 CI helper script를 추가한다.
- `docs/`, root markdown, 그리고 버전 파일(`pyproject.toml`, `uv.lock`, `src/trinity/__init__.py`)의 버전 줄만 바뀐 경우에만 `docs_version_only`로 분류한다.
- `docs_version_only` PR에서는 pytest required smoke를 건너뛰고, manifest list 확인과 wheel/console script smoke는 유지한다.
- 코드, 테스트, workflow, script, dependency 변경은 기존 required smoke 경로를 그대로 사용한다.
- classifier 단위 테스트를 required smoke manifest에 추가한다.
- 패치 버전을 `1.0.448`로 올린다.

## 비목표

- 변경 영역별 세부 테스트 선택은 이번 PR에서 구현하지 않는다.
- main push, publish workflow, wheel install smoke는 생략하지 않는다.
- required smoke test 목록 자체를 줄이지 않는다.

## 검증

- CI classifier 단위 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.448`을 출력해야 한다.
