# New Brief Starter Recommendations

## Problem

New-project prompts now carry the saved brief and missing-field guidance, but
they still leave agents to infer the first implementation direction from free
text. First-run users benefit from seeing Trinity translate their brief into a
small set of starter recommendations without silently committing to a framework
or template.

## Scope

- Add prompt-only starter recommendations for `mode == "new"`.
- Derive recommendations from existing brief fields only:
  `project_type`, `stack_preferences`, `target_users`, and constraints.
- Keep existing-project prompts unchanged.
- Do not create files, templates, config, or package manifests.
- Do not change project-intake persistence, readiness policy, or preflight
  gates.

## Design

`_project_brief_start_prompt` remains the single prompt builder. For new
projects, append a small "Starter recommendations" block when useful signal is
available:

- Architecture: a simple starter shape derived from project type.
- Stack: user-provided stack preferences when present.
- UX focus: target users when present.
- Guardrails: constraints when present.

The wording must stay advisory: agents should treat these as candidate starting
points and ask before making irreversible scaffold choices when the brief is
incomplete.

This deliberately avoids a broad template resolver. The goal is better first
planning context, not automatic project generation.

## Tests

- Complete English new-project prompt includes starter recommendations.
- Korean new-project prompt includes localized starter recommendations.
- Existing-project prompt does not include starter recommendations.
- New-project prompt without recommendation signal keeps the current compact
  missing-field behavior.
