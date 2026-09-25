# Known gaps and workarounds

Each entry names its backlog item (round 4: Plan/windows-mcp-open-issues-round4.md; round 3:
Plan/completed/windows-mcp-open-issues-round3.md); the fix removes it.

- **Several screens: full captures can miss a pop-up** (R3-2). With more than one display,
  full Screenshot and Snapshot images use "pillow", which missed Avast's alert. If a window
  reported in front is not in the image, capture its rectangle with `region`.
- **Snapshot lists elements hidden under an in-window panel** (R4-13), such as words under
  Notepad's open Find and Replace panel. Close the panel, or check with a Screenshot, before
  clicking a label there.
