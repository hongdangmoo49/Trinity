# Nexus Follow-up Target Workspace Sync

## Background

Nexus can show a selected workspace from the screen-level workspace candidate even when
the workflow session target is not yet aligned. In that state, a user can type a
follow-up such as "analyze this project" while the visible header points to the
intended project, but the workflow may continue with the previous session target or
without a target.

This is especially confusing when Trinity was launched from the control repository and
the user later selects another project in the Nexus page.

## Goal

- Before submitting a Nexus follow-up, align the workflow session target with the
  workspace currently visible to the user.
- Prefer the workflow snapshot target when present, then the app-level workspace
  candidate.
- Do not silently select the Trinity control repository unless the existing target
  confirmation flow has already approved it.
- Keep explicit workspace selection, project intake, execution, and review flows
  unchanged.

## User Experience

When the Nexus header says:

```text
Workspace: /home/user/workspace/msu
```

and the user submits:

```text
프로젝트를 분석해라.
```

the workflow should receive `/home/user/workspace/msu` as the target workspace before
the deliberation starts. The agents and central synthesis should therefore describe and
plan for `msu`, not the Trinity control repository that happened to be the launch cwd.

## Design

1. Add a small pure helper in `ask_commands.py` that decides which target workspace
   should be applied for a Nexus follow-up.
2. In `TrinityTextualApp.on_nexus_screen_follow_up_submitted`, call that helper before
   `workflow_controller.submit_follow_up`.
3. If the helper returns a target, call `workflow_controller.set_target_workspace` first
   and remember the preflight target so Nexus, Execution Matrix, and snapshots remain
   aligned.
4. Reuse `safe_start_target_workspace` to avoid silently targeting the control repo.
5. Cover the helper with unit tests and add an app-level regression using lightweight
   fakes so the event route cannot regress.

## Non-goals

- This change does not alter provider cwd isolation.
- This change does not redesign project intake persistence.
- This change does not add another confirmation modal for control-repo targets; those
  still go through the existing explicit selection and confirmation paths.

## Validation

- Unit tests for helper selection precedence and control-repo exclusion.
- App event regression confirming a Nexus follow-up syncs the selected workspace before
  submission.
- Required smoke tests before PR merge.
