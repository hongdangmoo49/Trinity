# Workspace Creatable Permission Probe

## Problem

The Nexus execute workspace picker can show a missing target path as
`Creatable: True` even when Windows later rejects directory creation with
`[WinError 5] Access is denied`.

The observed case is a target such as:

```text
C:\Users\snake-game-trinity
```

The nearest existing parent is `C:\Users`. `os.access(parent, os.W_OK)` can
report a permissive result on Windows even when the actual ACL denies creating
a child directory there. The UI then allows confirmation, but `Path.mkdir()`
fails.

## Goals

- Treat `creatable` as an actual creation capability, not only a UI toggle.
- Avoid marking protected parents such as `C:\Users` as creatable when the OS
  denies child creation.
- Keep the existing flow for normal user-owned paths such as
  `C:\Users\USER\workspace\new-project`.
- Prevent the `New Folder` action from opening a prompt when the selected base
  cannot accept child directories.
- Preserve the existing safe failure path if `mkdir` still fails because of a
  race or external permission change.

## Design

1. Replace the `os.access()`-only creatable check with a real write probe:
   create a temporary hidden preflight directory under the nearest existing
   parent and remove it immediately.
2. Clamp `creatable=True` overrides with the real creation capability. A user
   toggle may request creation, but it cannot override an unsupported path.
3. Simplify `WorkspacePreflight.can_create` so it trusts the already-probed
   `creatable` field instead of probing repeatedly.
4. Validate the `New Folder` base before showing the folder-name prompt. If the
   base cannot accept child creation, show a status message instead of letting
   the later `mkdir` fail.

## Tests

- Missing child under a writable temporary directory remains creatable.
- Probe failure makes a missing child non-creatable.
- `creatable=True` override cannot force an unsupported path to creatable.
- The write probe cleans up its temporary directory.
- `New Folder` does not open the folder-name prompt when the base cannot accept
  children.

## Release

After implementation and full test verification, bump the patch version from
`0.13.6` to `0.13.7`.
