# Known gaps and workarounds

Each entry names its backlog item (Plan/windows-mcp-open-issues-round3.md); the fix removes it.

- **Several screens: full captures can miss a pop-up** (R3-2). With more than one display,
  full Screenshot and Snapshot images use "pillow", which missed Avast's alert. If a window
  reported in front is not in the image, capture its rectangle with `region`.
- **App `list` shows no window position** (R3-I11): use Snapshot or Screenshot to see where a
  window is.
- **Pop-ups are not announced** (R3-N1). A dialog or alert that opens during a task is found
  only by looking: after an unexpected result, check Snapshot's "Focused Window" or App `list`.
