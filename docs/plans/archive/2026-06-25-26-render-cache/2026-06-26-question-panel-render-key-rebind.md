# QuestionPanel 렌더 키 재바인딩 보강

- 브랜치: `perf/question-panel-render-key-rebind`
- 버전: `1.0.289` -> `1.0.290`
- 대상: `src/trinity/textual_app/widgets/question_panel.py`

## 배경

`QuestionPanel`은 중앙 에이전트가 사용자에게 묻는 질문 목록을 렌더하고, `_questions_key`와 `_title_key`, `_empty_state_key`로 같은 질문 상태의 반복 렌더를 건너뛴다. 하지만 패널이 `refresh(recompose=True)`로 다시 그려지면 title/body 위젯은 새로 만들어지고 body는 빈 상태가 된다.

기존 compose 경로는 위젯 참조만 초기화했기 때문에, 같은 질문 목록이 다시 적용될 때 `_questions_key`가 이전 값과 같으면 렌더가 생략될 수 있다. 그러면 화면에는 질문 버튼이 없지만 내부 상태는 이미 렌더된 것으로 판단하는 불일치가 생긴다.

## 개선안

1. compose 시작 시 고정 위젯 캐시와 함께 질문 렌더 키도 초기화한다.
2. `_button_answers`, `_questions_key`, `_empty_state_key`, `_title_key`를 새 DOM 기준으로 리셋한다.
3. 리컴포즈 후 같은 질문 목록을 다시 적용해도 DOM 재조회 없이 새 body와 버튼 매핑이 렌더되는지 테스트한다.

## 기대 효과

- Nexus 질문 패널 리컴포즈 후 질문/답변 버튼이 사라진 채 갱신이 스킵되는 상황을 방지한다.
- 버튼 id와 `QuestionAnswer` 매핑이 새 DOM 렌더 시점에 다시 생성된다.
- 질문 패널의 widget cache와 render cache 생명주기를 다른 Nexus 위젯과 맞춘다.
