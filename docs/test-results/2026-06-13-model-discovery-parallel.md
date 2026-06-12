# Model Discovery Parallelization

작성일: 2026-06-13

브랜치: `feature/current-workflow-operation-analysis`

## 변경 요약

- Textual app의 provider model discovery를 provider별 병렬 실행으로 변경했다.
- 기존처럼 worker thread 안에서 실행하되, 내부에서 `ThreadPoolExecutor`와 `as_completed()`를
  사용해 빠르게 끝난 provider 결과를 먼저 UI thread에 전달한다.
- 한 provider discovery가 예외를 내도 다른 provider 결과 적용을 막지 않도록 해당 provider만
  빈 결과로 처리한다.

## 검증

```text
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_textual_app.py::test_model_discovery_applies_fast_provider_before_slow_provider \
  tests/test_provider_model_discovery.py \
  -q
```

결과:

```text
9 passed in 1.07s
```

전체 Textual app 회귀:

```text
PYTHONPATH=src .venv/bin/python -m pytest tests/test_textual_app.py -q
```

결과:

```text
122 passed in 84.55s
```

추가 확인:

```text
PYTHONPATH=src .venv/bin/python -m py_compile \
  src/trinity/textual_app/app.py \
  tests/test_textual_app.py

git diff --check
```

결과: 통과.

