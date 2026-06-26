# Work Package Detail Title Summary

## Problem

Work-package detail modals use the full package title in the modal header. Long
titles can make the header visually noisy, but clipping the header would hide
the full package identity because the Summary section does not show the package
title separately.

## Design

- Keep the modal header compact by clipping very long titles.
- Preserve the full package title in the Summary section.
- Localize the Summary title/topic labels for Korean UI mode.
- Preserve package ids, status values, agent names, and other workflow data as
  raw values.

## Acceptance

- Long modal headers stay bounded.
- The Summary section contains the full package title.
- Korean UI mode shows Korean title labels.
- Existing detail modal section ordering remains unchanged.
