# Start and central chrome i18n

Date: 2026-06-24
Branch: ux/start-central-chrome-i18n

## Problem

Most Nexus controls are localized, but the first Start screen still shows English
chrome labels in Korean mode:

- "Three minds, one context"
- "What should Trinity work on?"
- "Select Workspace"
- "Plan first"
- "Target workspace: Not selected"
- "Select at least one agent."

The central panel title also starts as "Central Agent" even when `lang=ko`.

## Scope

- Add StartScreen labels for subtitle, placeholder, action buttons, workspace label,
  and select-agent warning.
- Reuse CentralAgentView's existing label table for the central panel title.
- Keep brand text `TRINITY` and user/provider data unchanged.

## Verification

- Add Korean Start screen chrome tests.
- Add Korean CentralAgentView title test through the Nexus screen.
- Run focused tests, Textual app tests, full test suite, diff check, and version check.
