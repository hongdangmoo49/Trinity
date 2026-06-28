# Workbench Intake Refresh Action

This design improves the visible Start/Nexus action after existing-project
intake drift detection.

## Problem

Start/Nexus now show when saved existing-project intake differs from the live
workspace profile. The action button still says `Analyze Existing`, even when
the selected workspace already has saved intake and the useful action is to
refresh that saved analysis.

The existing button already calls the correct internal path: it rebuilds and
writes project intake for the active target. The missing piece is the visible
label.

## Contract

When saved existing-project intake targets the selected workspace and the saved
analysis is sparse, stale, or changed, the Workbench action label should be:

- English: `Refresh Analysis`
- Korean: `분석 갱신`

All other cases keep the existing journey label:

- English: `Analyze Existing`
- Korean: `기존 프로젝트 분석`

The action id and event flow remain unchanged. Tests and automation can keep
using `analyze_workspace` and `nexus-analyze-workspace`.

## Non-Goals

- Adding a second button.
- Changing persistence behavior.
- Automatically refreshing analysis without user action.
- Changing new-project brief behavior.

## Tests

Coverage should prove:

- default Start/Nexus labels remain `Analyze Existing`;
- sparse, stale, or changed matching existing intake changes the label to
  `Refresh Analysis`;
- Korean labels use `분석 갱신`;
- mounted Start/Nexus refresh updates the button text as well as the variant.
