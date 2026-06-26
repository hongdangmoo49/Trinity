# Question Panel Empty Class Cache

## 배경

QuestionPanel은 Nexus 중앙 에이전트 질문을 별도 패널로 렌더링한다. 질문 내용이 바뀌면
`apply_questions()`가 패널의 empty/non-empty 클래스를 다시 동기화한 뒤 제목과 본문을
갱신한다.

`question-panel-empty` 클래스는 질문 목록이 비었는지 여부에만 의존한다. 따라서 질문
내용이나 답변 상태가 바뀌어도 empty 여부가 같다면 class mutation은 반복할 필요가 없다.
Nexus 페이지가 스냅샷 갱신을 자주 받는 흐름에서는 이 작은 mutation도 누적될 수 있다.

## 개선 방향

- QuestionPanel에 마지막 empty 상태를 캐시한다.
- empty 여부가 바뀐 경우에만 `set_class()`를 호출한다.
- 질문 내용이 바뀐 경우 기존처럼 제목과 본문 렌더링은 수행한다.

## 범위

- `src/trinity/textual_app/widgets/question_panel.py`
- `tests/test_question_panel.py`

## 검증

- non-empty 질문에서 다른 non-empty 질문으로 바뀔 때 empty class sync가 생략되는지 확인한다.
- 질문 목록이 empty로 바뀌면 기존처럼 empty class가 반영되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
