# Question Panel Question Key Cache

## 배경

QuestionPanel은 질문 목록 key를 저장해 body render 중복을 줄이고 있었지만, key 비교 전에 empty class와 title 계산을 먼저 수행했다. Nexus snapshot이 같은 질문 목록을 반복 적용하면 실제 질문 UI가 그대로여도 일부 계산과 위젯 접근이 남는다.

또한 `_questions_key` 초기값이 빈 tuple이라 최초 빈 질문 목록은 body render를 건너뛰어 empty 메시지가 mount되지 않을 수 있었다.

## 개선 방향

- 질문 목록 key를 먼저 계산한다.
- mounted 상태에서 key가 직전 key와 같으면 class/title/body 갱신을 모두 생략한다.
- `_questions_key` 초기값을 `None`으로 두어 최초 빈 질문 목록도 empty body를 렌더한다.

## 범위

- `src/trinity/textual_app/widgets/question_panel.py`
- `tests/test_question_panel.py`

## 검증

- 같은 질문 목록 재적용 시 `_render_questions()`가 호출되지 않는지 확인한다.
- 질문 answer가 바뀌면 body render가 다시 호출되는지 확인한다.
- 최초 빈 질문 목록에서 empty 메시지가 렌더되는지 확인한다.
- QuestionPanel focused test와 전체 테스트를 통과시킨다.
