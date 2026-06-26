# Korean UI Glossary

This glossary records the Korean terms stabilized during the Nexus UI
localization pass. Use it before adding new Korean labels or consolidating
duplicated presenter strings.

## Source of Truth

Prefer existing shared helpers before adding local strings:

- `src/trinity/display_labels.py`
  - source/model/profile/risk/severity/kind value labels
- `src/trinity/textual_app/presenters.py`
  - Textual command titles, body strings, table labels, and action hints
- `src/trinity/textual_app/widgets/status_label.py`
  - compact status/readiness/review status labels

## Preferred Terms

| English/source term | Korean display | Notes |
| --- | --- | --- |
| provider | 프로바이더 | Use for CLI/model provider surfaces. |
| agent | 에이전트 | Use for Claude/Codex/Antigravity participants. |
| workspace | 작업 폴더 | Use for user target workspace. |
| target workspace | 대상 작업 폴더 | Use when distinguishing from Trinity control repo. |
| work package | 작업 패키지 | Keep WP abbreviation only in compact IDs. |
| peer review | 동료 리뷰 | Use for non-owner review stage. |
| no peer reviewer | 동료 리뷰어 없음 | Use when one-provider setups skip peer review. |
| retry | 재시도 | Use for execution retry and provider retry. |
| recovery | 복구 | Use for interrupted execution recovery. |
| output contract | 출력 형식 | Use for provider/profile output requirements. |
| profile revision | 프로필 버전 | Use for AgentProfile metadata. |
| action context | 작업 맥락 | Use in detail/report sections. |
| risk | 리스크 | Use as section label; risk values use 낮음/보통/높음/치명적. |
| severity | 심각도 | Value labels use 정보/경고/오류/치명적 when applicable. |
| waiting | 대기 | Bucket waiting states consistently. |
| succeeded/done | 완료 | Show completed execution states as 완료. |

## Value Labels

Use `display_labels.py` for these value families:

- `display_source_value`
- `compact_source_value`
- `display_risk_value`
- `display_severity_value`
- `display_kind_value`
- `display_profile_value`

Do not duplicate these mappings in widgets, reports, or command handlers unless
the target string is intentionally different for layout reasons.

## Presenter Labels

Use `STATUS_CONTEXT_LABELS` in `textual_app.presenters` for command surfaces:

- local slash command titles
- usage and action hints
- report/export messages
- target workspace messages
- review/repair/retry messages
- table column labels

When adding a new presenter label:

1. Add both `en` and `ko` values.
2. Prefer existing glossary terms.
3. Add or update a focused presenter/parser test.
4. Run the required smoke gate when the label affects shared Textual output.

## Consolidation Rule

Only consolidate repeated Korean strings when all affected surfaces expect the
same wording. Report export, Textual widgets, and local command output may need
different lengths even when they describe the same concept.

Safe consolidation candidates:

- status values
- source/profile/risk/severity/kind values
- table column labels reused across command results

Risky consolidation candidates:

- button labels with width constraints
- report prose
- modal body copy
- action hints that depend on current workflow state

## Focused Tests

Use these tests when touching Korean UI labels:

```bash
uv run pytest -q tests/test_i18n.py tests/test_textual_command_parsers.py tests/test_textual_app.py tests/test_textual_settings.py
```

Run required smoke before merging shared presenter changes:

```bash
uv run python scripts/run_required_smoke_tests.py -q
```
