# Known gaps and workarounds

Each entry names its backlog item (Plan/windows-mcp-open-issues-round3.md); the fix removes it.

- **Several screens: full captures can miss a pop-up** (R3-2). With more than one display,
  full Screenshot and Snapshot images use "pillow", which missed Avast's alert. If a window
  reported in front is not in the image, capture its rectangle with `region`.
