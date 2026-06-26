# WP Detail Lane I18n

## 문제

WP 상세 모달은 한국어 UI에서 `실행 레인` 라벨을 사용하지만 값은 `serial` 또는
`unspecified`로 표시한다.

실행 매트릭스는 이미 직렬 레인을 한국어로 표시하므로, 상세 모달도 같은 의미를 맞춰야 한다.

## 설계

- `WorkPackageDetailModal`의 execution lane value를 locale-aware하게 만든다.
- parallel group이 있으면 기존 `g1`, `g2` 형식을 유지한다.
- serial lane은 영어 `serial`, 한국어 `직렬`로 표시한다.
- parallelizable이지만 group이 없으면 영어 `unspecified`, 한국어 `미지정`으로 표시한다.
- snapshot/data model은 변경하지 않는다.

## 기대 효과

- 한국어 상세 모달의 언어 혼합을 줄인다.
- 실행 매트릭스와 WP 상세 모달의 lane 의미가 더 일관된다.
- 기존 영어 UI와 group lane 표기는 유지된다.

## 테스트

- 영어 serial lane은 기존 `serial`을 유지한다.
- 한국어 serial lane은 `직렬`로 표시한다.
- 한국어 unspecified lane은 `미지정`으로 표시한다.
- parallel group lane은 기존 `gN` 표기를 유지한다.
