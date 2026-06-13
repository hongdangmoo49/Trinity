# Provider Inspector Output Budget

작성일: 2026-06-13

브랜치: `feature/current-workflow-operation-analysis`

## 변경 요약

- Provider Inspector raw output 렌더링에 크기 budget을 추가했다.
- 큰 raw output은 전체 pretty print나 전체 RichLog write를 하지 않고 앞부분만 표시한다.
- JSON pretty print는 작은 출력에만 적용한다.
- 큰 출력은 truncation 안내를 붙여 full output은 raw artifact에서 확인하도록 유도한다.

## 검증

```text
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_textual_app.py::test_provider_inspector_pretty_prints_json_output \
  tests/test_textual_app.py::test_provider_inspector_truncates_large_raw_output \
  tests/test_textual_app.py::test_provider_inspector_all_tab_wraps_long_output \
  -q
```

결과:

```text
3 passed in 5.03s
```

전체 Textual app 회귀:

```text
PYTHONPATH=src .venv/bin/python -m pytest tests/test_textual_app.py -q
```

결과:

```text
123 passed in 83.87s
```

추가 확인:

```text
PYTHONPATH=src .venv/bin/python -m py_compile \
  src/trinity/textual_app/widgets/provider_inspector.py \
  tests/test_textual_app.py

git diff --check
```

결과: 통과.

