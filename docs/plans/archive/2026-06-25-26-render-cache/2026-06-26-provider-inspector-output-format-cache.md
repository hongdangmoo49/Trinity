# Provider Inspector Output Format Cache

## Context

`ProviderInspector` renders each provider in its own tab and also renders an
`All` tab. Both paths call `_provider_output(provider)`.

Raw output path reads are already cached, but raw output formatting is not.
Large JSON output, fenced JSON, or large text truncation can therefore be
processed more than once during a single inspector compose.

## Goal

Cache formatted provider output within a `ProviderInspector` instance.

## Design

- Add an instance-level formatted output cache keyed by the resolved raw output
  text.
- Keep the existing raw output path read cache unchanged.
- Format each distinct output string once per inspector instance.
- Reuse the formatted value for both the provider tab and the `All` tab.

## Tests

- Add a focused provider inspector cache test.
- Verify repeated `_provider_output()` calls for the same provider call
  `_format_output()` only once and return the same formatted text.

## Versioning

Patch release: `1.0.262` -> `1.0.263`.
