# Existing Scope Anchor Review

## Problem

Existing-project intake can detect monorepo-like scope candidates such as
`apps/web` or `packages/core`, and the intake schema already has
`selected_scope`. However, the Workbench analysis review modal only lets users
adjust docs, source roots, and commands. If scope candidates are the only useful
signal, the analysis flow seeds the prompt without giving the user a chance to
confirm which subproject Trinity should discuss.

This is awkward for existing projects because users often expect Trinity to
talk about a selected app or package, not the whole repository.

## Goal

Let existing-project users confirm or edit the selected scope during the same
analysis-anchor review step that already appears after `Analyze Existing`.

## Scope

- Show detected scope candidates in the existing-project anchor review modal.
- Add a `selected_scope` input to that modal.
- Preserve and persist the selected scope when the user saves the modal.
- Open the modal when scope candidates exist even if docs/source/test anchors
  are otherwise sparse.
- Keep CLI intake, prompt guidance, and execution preflight contracts unchanged.

## User Flow

1. User opens Start or Nexus on an existing project.
2. User chooses `Analyze Existing`.
3. Trinity writes read-only project intake and detects scope candidates.
4. If anchors or scope candidates exist, Trinity opens the review modal.
5. User confirms or edits `selected_scope`.
6. Trinity persists the updated intake and seeds the prompt with the selected
   scope and other anchors.

## Validation

- Focused Textual tests cover Start and Nexus anchor review persistence.
- Existing scope-candidate prompt coverage is updated to verify the modal opens
  and saves `selected_scope`.
- Required smoke tests run before PR merge.
