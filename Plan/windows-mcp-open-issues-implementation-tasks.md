---
Title: Tasks — implement the windows-mcp open-issues backlog (sections 1, 2, 3, 6)
Description: Atomic task list for Plan/windows-mcp-open-issues-implementation-plan.md. Per backlog item - failing test, fix, live check with a different tool, Skills/Skill.md update, backlog tick - plus branch set-up and one commit checkpoint per section on fix/open-issues-backlog. [User] items at the end are the ones the agent cannot do.
Total Tasks: 30
---

# Tasks

## 0. Set-up
- [x] 0.1 Create branch `fix/open-issues-backlog` off the current branch.
- [x] 0.2 Get the GitNexus repo name; refresh the index if stale.

## 1. Section 1 — High
- [x] 1.1 FileSystem `write` honours `overwrite=false`.
- [x] 1.2 Shared strict boolean parser, used by every tool that takes true/false.
- [x] 1.3 Process: substring filter for `list`, exact name (`.exe` optional) for `kill`.
- [x] 1.4 Registry: `recursive` option; refuse to delete a key with sub-keys without it.
- [x] 1.5 Snapshot: drop background-window elements covered by another window.
- [x] 1.6 Add `Skills/Skill.md` to git and update it for 1.1–1.5.
- [x] 1.7 Checkpoint commit for section 1 (fcfcf7d).

### Verification
- Each item: new test failed before the fix and passes after; full suite and ruff clean.
- Live: write over an existing file then read it with PowerShell; bool "yes"/"maybe"; `list pwsh`; key-with-sub-keys delete checked with PowerShell `Test-Path`; Snapshot with a covered window checked against a Screenshot.

## 2. Section 2 — Medium
- [x] 2.1 PowerShell returns non-terminating errors as plain text.
- [x] 2.2 PowerShell rejects `timeout` below 1.
- [x] 2.3 Registry accepts multi-byte binary values.
- [x] 2.4 Notification checks the app id and the notification switches.
- [x] 2.5 Screenshot says window list skipped.
- [x] 2.6 Screenshot draws the grid.
- [x] 2.7 Scrape says when the summary was unavailable.
- [x] 2.8 Update `Skills/Skill.md` for 2.1–2.7.
- [x] 2.9 Checkpoint commit for section 2.

### Verification
- Tests as above. Live: `Get-Item` on a missing path shows the error; binary value read back with PowerShell; fake app id reported; grid visible in the returned image.

## 3. Section 3 — Low
- [ ] 3.1 Click validates `clicks` (0–3) and names triple clicks.
- [ ] 3.2 MultiSelect reply worded by mode.
- [ ] 3.3 Snapshot text tree prints label ids.
- [ ] 3.4 Reproduce the 500-cap case; fix or close as not-a-bug.
- [ ] 3.5 App switch falls back to substring / process-name match.
- [ ] 3.6 Update `Skills/Skill.md` for 3.1–3.5.
- [ ] 3.7 Checkpoint commit for section 3.

### Verification
- Tests as above. Live: a label from the text tree clicks the right element (checked by Screenshot); `switch "Edge"` brings Edge up (checked by Screenshot).

## 4. Section 6 — missing abilities
- [ ] 4.1 Click `modifiers` (6.1).
- [ ] 4.2 Scroll and Move-drag `modifiers` (6.4).
- [ ] 4.3 Shortcut `hold` (6.2).
- [ ] 4.4 Shortcut `repeat` (6.5).
- [ ] 4.5 Move press / release (6.3).
- [ ] 4.6 Click and Type without a location (6.6).
- [ ] 4.7 Wait accepts decimals (6.7).
- [ ] 4.8 Update `Skills/Skill.md` for 6.1–6.7, then re-read it end to end (7.2).
- [ ] 4.9 Checkpoint commit for section 6; move the plan and task file to `Plan/completed/` if everything is done.

### Verification
- Tests as above. Live on a Notepad window launched for the test (killed by PID afterwards): Shift+click extends a selection, Down×5 moves the caret, Ctrl+wheel zooms, press/move/release drags a selection — each checked by Screenshot or reading the file with PowerShell.

## [User] tasks (the agent cannot do these)
- [ ] [User] Reconnect windows-mcp in Claude Code (`/mcp`) after the session so the live tools run the new code — the agent cannot restart its own tool server.
- [x] 2.4b Check whether Do Not Disturb / Focus was on during the toast test — done by the agent: it is off now; toasts appear.
- [ ] [User] 4.1 / 5.2 Full browser-page reads — blocked by the browser-lock extension on Edge.
- [ ] [User] 4.2 Point Claude Desktop at the fixed server — only the user can change that config.

# Implementation verification
- `.venv/Scripts/python.exe -m pytest -q` green and `ruff check .` clean before every checkpoint.
- Every backlog item in sections 1, 2, 3, 6 is ticked or explicitly closed with a reason in `Plan/windows-mcp-open-issues.md`.
- `Skills/Skill.md` matches the new behaviour: no workaround remains for a fixed bug, every new option is documented.
- GitNexus detect_changes before each commit shows only the expected symbols.
