# Question Panel Title Update Cache

## 배경

Nexus의 QuestionPanel은 질문 목록 body를 `_questions_key`로 캐시하지만, title은 `apply_questions()`가 호출될 때마다 같은 문자열이어도 `Static.update()`를 호출한다.

workflow snapshot poll이 잦은 상황에서 사용자가 답변할 질문 상태가 변하지 않는다면 title 갱신은 화면 변화를 만들지 않는 반복 작업이다.

## 개선 방향

- QuestionPanel에 마지막 title 문자열을 저장한다.
- `apply_questions()`는 새 title이 이전 title과 다를 때만 title 위젯을 갱신한다.
- 질문 body 렌더링은 기존 `_questions_key` 캐시를 그대로 유지한다.

## 범위

- `src/trinity/textual_app/widgets/question_panel.py`
- `tests/test_question_panel.py`

## 검증

- 같은 질문 목록을 다시 적용할 때 title update가 생략되는지 확인한다.
- 질문이 답변 완료 상태로 바뀌면 title이 정상 갱신되는지 확인한다.
- 전체 테스트를 통과시킨다.
