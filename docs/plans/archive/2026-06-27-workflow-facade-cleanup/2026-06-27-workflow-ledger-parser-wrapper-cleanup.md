# Workflow Ledger Parser Wrapper Cleanup

## 목적

`WorkflowEngine`에 남아 있는 shared ledger parser forwarding wrapper를 제거해 ledger parsing 책임을 `WorkflowLedgerSync`에만 둔다.

## 범위

- 사용처가 없는 `WorkflowEngine._extract_shared_preserved_sections()`를 제거한다.
- 사용처가 없는 `WorkflowEngine._parse_markdown_sections()`를 제거한다.
- 실제 shared ledger sync 동작은 `WorkflowLedgerSync` 구현을 그대로 사용한다.
- 패치 버전을 `1.0.410`으로 올린다.

## 검증

- shared ledger sync focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.410`을 출력해야 한다.
