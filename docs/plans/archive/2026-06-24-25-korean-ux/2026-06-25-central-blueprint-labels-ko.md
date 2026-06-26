# 중앙 설계안 markdown 라벨 한국어화

## 배경

Nexus 중앙 패널에 표시되는 설계안 markdown은 `NexusSnapshotAdapter`에서 생성된다. 한국어 UI에서도 이 생성 markdown의 섹션 제목과 보조 라벨이 `Architecture`, `Data Flow`, `Dependencies`, `Mitigation`, `Options`, `Recommended`처럼 영어로 남아 있어, 중앙 패널의 다른 한국어 상태/가이드 문구와 어긋난다.

## 목표

- 한국어 설정에서 중앙 설계안 markdown의 고정 섹션 제목을 한국어로 표시한다.
- 구성 요소의 dependency, risk mitigation, 질문 options/recommended 보조 라벨도 한국어로 표시한다.
- blueprint 제목/요약/본문처럼 에이전트가 생성한 실제 내용은 원문을 유지한다.
- 영어 UI 출력은 기존과 동일하게 유지한다.

## 작업 범위

1. `NexusSnapshotAdapter`가 config 언어에 따라 설계안 라벨을 선택하도록 변경한다.
2. 중앙 설계안 markdown 생성부의 하드코딩된 라벨을 helper로 치환한다.
3. 한국어/영어 snapshot adapter 테스트를 추가한다.
4. 패치 버전을 갱신하고 테스트를 실행한다.

## 비범위

- blueprint 데이터 구조 변경.
- 에이전트가 생성한 설계안 본문 번역.
- 중앙 패널 markdown 렌더러 구조 변경.
