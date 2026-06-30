# Existing Project Read-First Checklist

## Problem

Existing-project intake detects documentation, source roots, entrypoints, scope
candidates, and test/build commands. `/project` diagnostics and CLI status
already include a compact `read first` hint, and analysis prompts include
detected anchors.

The remaining UX problem is visibility: before planning or execution, users
cannot clearly see the minimum reading checklist agents should complete before
proposing edits. For existing projects, that checklist is one of the strongest
safety signals because it prevents repository-wide assumptions and stale
context.

## Scope

- Add a derived read-first checklist preview for saved `mode == "existing"`
  project intake.
- Show the preview through `/project` diagnostics near the other project-intake
  previews.
- Expose the same preview through `trinity project status` text and JSON.
- Derive the checklist from saved intake only:
  `selected_scope`, `docs_found`, `source_roots`, `entrypoints`,
  `scope_candidates`, and validation commands.
- Keep the preview advisory and non-blocking.

## Non-Goals

- Do not track whether an agent actually read each item.
- Do not execute commands or inspect file contents.
- Do not add new project-intake schema fields.
- Do not block execution when the checklist is sparse.
- Do not replace the existing anchor review modal.

## Design

Add a shared `project_read_first_checklist_label()` helper next to the existing
project-intake label helpers. It returns an empty string unless the saved intake
matches the selected existing-project target.

The helper should render a compact localized line:

- English: `Read-first checklist: scope ... | read ... | inspect ... | verify ...`
- Korean: `먼저 읽기 체크리스트: 범위 ... | 읽기 ... | 점검 ... | 검증 ...`

Derivation rules:

1. `scope`
   - Use `selected_scope` when present.
   - Otherwise show compact `scope_candidates`.
   - Otherwise show `target root`.
2. `read`
   - Combine `docs_found` and `source_roots`, preserving order and removing
     duplicates.
   - If empty, show `README/docs/source roots missing`.
3. `inspect`
   - Prefer `entrypoints`.
   - Otherwise show `entrypoints missing`.
4. `verify`
   - Prefer test commands, then build commands.
   - Otherwise show `record validation command`.

This helper is intentionally a preview. Later work can add actual read-progress
tracking or per-agent evidence, but this change keeps the UX focused and safe.

## Tests

- Shared helper returns English and Korean checklists for existing intake.
- Existing intake with no anchors still returns a useful sparse checklist.
- New-project intake returns no read-first checklist.
- CLI `project status` text and JSON include the checklist for existing intake.
- `/project` diagnostics refresh the checklist after project intake changes.
