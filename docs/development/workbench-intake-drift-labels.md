# Workbench Intake Drift Labels

This design extends the existing-project intake drift signal into Start/Nexus
Workbench labels.

## Problem

The CLI status command and Execute Preflight can now detect when saved
existing-project intake differs from the live workspace profile. Start/Nexus
still show the previous saved intake label and default Analyze Existing action
unless the intake is missing, stale, sparse, or mismatched.

For existing-project users, that means the Workbench can look ready until the
execute modal is opened.

## Contract

When saved existing-project intake matches the selected workspace but differs
from the live read-only profile:

- the project-intake label includes an analysis changed signal;
- the label includes the same `trinity project analyze <target>` refresh hint
  used by stale analysis;
- the Analyze Existing action variant becomes `warning`;
- target mismatch, target missing, sparse analysis, and stale analysis keep their
  existing precedence.

New-project intake is not checked for drift here because brief completeness is
the stronger signal for that journey.

## Cost

The check uses the same local read-only profile comparison as Execute Preflight
and `trinity project status`. It does not call providers, package managers,
tests, builds, or user code. It may read manifests, source/doc directory
existence, and Git status.

## Tests

Coverage should prove:

- unchanged existing-project intake keeps the concise label and default Analyze
  Existing variant;
- changed existing-project intake adds the changed signal and refresh hint;
- Analyze Existing becomes warning for changed intake;
- Korean labels render the changed signal.
