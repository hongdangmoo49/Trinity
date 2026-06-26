# Central Action Presenter

## Problem

`CentralAgentView` renders Nexus action buttons and also decides which action
group has priority. Provider error gates, review repair gates, execution retry,
and blueprint actions now live in the widget, making future UX changes harder
to test without mounting Textual widgets.

## Design

- Move central action-group selection into a pure presenter helper.
- Keep labels and widget mounting inside `CentralAgentView`.
- Preserve the current priority order:
  1. provider error gate
  2. review repair gate
  3. execution retry recovery
  4. blueprint actions
- Keep button action ids and variants unchanged.

## Acceptance

- Pure presenter tests cover the action priority order.
- Existing Textual action tests continue to pass.
- `CentralAgentView` becomes a renderer for the presenter result rather than
  the owner of action decision logic.
