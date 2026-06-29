# New Project Dry-Run Detail

Date: 2026-06-29
Branch: `feature/new-project-dry-run-detail`

## Problem

New-project onboarding now has starter presets and a generation confirmation
modal, but the confirmation still compresses the dry-run into broad preview
strings. A first-time user benefits from seeing the exact creation targets,
validation commands, and conflict state before agents start planning.

## Goal

Make the new-project confirmation modal read like a small dry-run checklist.

## User Experience

1. User completes a new-project brief.
2. Trinity opens the new-project confirmation modal before planning.
3. The modal shows:
   - target workspace
   - planned create targets
   - validation commands
   - guardrails
   - conflicts
4. Missing sections are explicit, not silent.

## Implementation Plan

- Extend `ProjectGenerationConfirmationSummary` with structured dry-run lines.
- Derive the lines from existing `ProjectIntake` fields so no generation logic is
  duplicated.
- Keep the existing compact preview and validation plan for continuity.
- Add tests for complete dry-run, missing validation, and conflict reporting.

## Non-Goals

- Do not create files.
- Do not execute validation commands.
- Do not replace the broader generation preview label.
- Do not change provider planning behavior.

## Success Criteria

- New-project confirmation summary exposes create, validate, guardrail, and
  conflict sections.
- Existing compact preview remains available.
- Missing validation is shown explicitly.
- Tests and required smoke pass.
