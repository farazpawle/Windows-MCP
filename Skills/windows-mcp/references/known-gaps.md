# Known gaps and workarounds

Each entry names its backlog item (round 4: Plan/windows-mcp-open-issues-round4.md; round 3:
Plan/completed/windows-mcp-open-issues-round3.md); the fix removes it.

- **Typing into Windows 11 Notepad can garble text** (R4-16): once Notepad auto-corrects a
  word ("charlie" -> "Charlie") or starts a new line, the rest of a Type call can come out
  as one letter repeated, with text lost. Write documents with FileSystem `write` and open
  them; after typing into Notepad, read the text back (Ctrl+A, Ctrl+C, Clipboard `get`).
  Notepad's own auto-correct also changes some words whatever the typing speed.
- **Several screens: full captures can miss a pop-up** (R3-2). With more than one display,
  full Screenshot and Snapshot images use "pillow", which missed Avast's alert. If a window
  reported in front is not in the image, capture its rectangle with `region`.
- **Snapshot lists elements hidden under an in-window panel** (R4-13), such as words under
  Notepad's open Find and Replace panel. Close the panel, or check with a Screenshot, before
  clicking a label there.
