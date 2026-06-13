# Snapshot Memoization

작성일: 2026-06-13

브랜치: `feature/current-workflow-operation-analysis`

## 변경 요약

- `NexusSnapshotAdapter.load_snapshot()`에 instance-local snapshot memoization을 추가했다.
- cache key는 다음 입력을 포함한다.
  - `workflow/session.json` stat
  - `workflow/events.jsonl` stat
  - `shared.md` stat
  - small `shared.md` bounded content fingerprint
  - in-memory agent/model 관련 config fingerprint
  - recent runtime `TUIEvent` fingerprint
- 같은 adapter 인스턴스에서 동일 입력으로 snapshot을 반복 요청하면 projection을 재사용한다.
- events 파일, shared context, recent runtime event가 바뀌면 새 snapshot을 만든다.

## 검증

```text
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_textual_snapshot.py \
  tests/test_workflow_persistence.py \
  tests/test_performance_harness.py \
  -q
```

결과:

```text
42 passed in 0.87s
```

추가 확인:

```text
PYTHONPATH=src .venv/bin/python -m py_compile \
  src/trinity/textual_app/snapshot.py \
  tests/test_textual_snapshot.py

git diff --check
```

결과: 통과.

## 주의 사항

- `shared.md`는 stale synthesis가 사용자에게 바로 보이는 영역이므로 작은 파일은 stat 외에
  bounded content hash를 cache key에 포함했다.
- 큰 `shared.md`는 hash 비용을 피하기 위해 stat 기반 key를 사용한다. oversized shared context는
  별도의 retention/cleanup 작업에서 다룬다.

