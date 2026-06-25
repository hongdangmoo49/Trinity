# Nexus 입력창 한국어 안내문 개선

## 배경

Nexus 입력창의 한국어 placeholder는 `답변하거나 방향을 조정하세요. / 로 명령 입력`으로 표시된다. 의미는 전달되지만 `/ 로` 띄어쓰기가 부자연스럽고, 입력창 placeholder로는 문장이 다소 길다.

## 목표

- Nexus 입력창 한국어 placeholder를 더 짧고 자연스럽게 다듬는다.
- `/`로 명령을 시작할 수 있다는 힌트는 유지한다.
- 영어 placeholder와 명령 처리 동작은 변경하지 않는다.

## 작업 범위

1. `NEXUS_LABELS["ko"]["composer_placeholder"]` 문구를 수정한다.
2. 관련 Textual 테스트 기대값을 갱신한다.
3. 패치 버전을 갱신하고 테스트를 실행한다.

## 비범위

- PromptComposer 동작 변경.
- 영어 placeholder 변경.
- 슬래시 명령 처리 로직 변경.
