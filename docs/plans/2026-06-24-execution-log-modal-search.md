# Execution Log Modal Search

## 문제

Full Log 모달은 긴 workflow log를 bounded window로 렌더링하지만, 사용자가 특정 WP id,
provider, error, review event를 찾으려면 눈으로 스크롤해야 한다.

실행 페이지의 목적은 문제 상태를 빠르게 진단하는 것이므로, log modal에는 간단한
case-insensitive 검색/필터가 필요하다.

## 설계

- `ExecutionLogModal`에 검색 `Input`을 추가한다.
- 검색어가 비어 있으면 기존 tail window를 그대로 보여준다.
- 검색어가 있으면 전체 log source에서 case-insensitive substring match를 수행한다.
- match 결과도 최근 500줄 window로 제한한다.
- match가 없으면 빈 결과 문구를 표시한다.
- 한국어 UI에는 placeholder와 empty filtered state를 한국어로 제공한다.

## 기대 효과

- 사용자가 `WP-001`, `failed`, `review`, provider 이름 등으로 긴 로그를 빠르게 좁힐 수 있다.
- 검색 결과 렌더링도 bounded window를 유지해 모달 mount/update 비용이 커지지 않는다.
- snapshot/log 저장 구조와 export 동작은 변경하지 않는다.

## 테스트

- 검색어가 없으면 기존 render window가 유지된다.
- 검색어가 있으면 matching line만 표시된다.
- 검색은 대소문자를 구분하지 않는다.
- match가 없으면 localized empty filtered state를 표시한다.
- Input 변경 시 modal body가 다시 렌더링된다.
