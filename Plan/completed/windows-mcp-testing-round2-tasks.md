---
Title: Windows-MCP testing round 2 - tasks
Description: DONE 2026-09-22. Task list for the second round of live windows-mcp testing (2026-09-22). Covers set-up, the seven section 6 abilities, regressions of every round-1 fix, untried edge cases, chained workflows with truthfulness checks, a line-by-line Skills/Skill.md check, and the write-up (new backlog and updated test report). No code fixes this round. Paired with Plan/windows-mcp-testing-round2-plan.md.
Total Tasks: 52
---

# Tasks

## 0. Set-up
- [x] 0.1 Confirm the live tools run current code (Click `modifiers`, Move `mouse_button`).
- [x] 0.2 Create `%TEMP%\wmcp-r2` test folder.
- [x] 0.3 Write a held-key checker script (`GetAsyncKeyState` for Ctrl, Shift, Alt, Win, left/right/middle mouse).
- [x] 0.4 Start the WinForms harness and record its PID.

## 1. Section 6 abilities
- [x] 1.1 Click `modifiers`: shift, ctrl, alt, win, "ctrl+shift", list form; verify in harness log.
- [x] 1.2 Click `modifiers` bad values: unknown key, empty string, duplicates, "ctrl+" ; confirm clean error and nothing held.
- [x] 1.3 Click `modifiers` with error partway (bad `label`, off-screen `loc`); confirm keys released.
- [x] 1.4 Scroll `modifiers` (ctrl, shift, alt, bad value); verified by the harness wheel log with modifier state (adapted from a Notepad zoom check).
- [x] 1.5 Move drag `modifiers`; `modifiers` without `drag` (should be refused or ignored truthfully).
- [x] 1.6 Shortcut `repeat`: 1, 5, 100, 0, 101, -1, text value; count key events in harness log.
- [x] 1.7 Shortcut `hold`: 0.5, 10, 10.5, 0, negative, text; measure the real hold length.
- [x] 1.8 Shortcut `hold` + `repeat` together (should be refused).
- [x] 1.9 Shortcut bad key with `repeat`/`hold`; confirm no key left down.
- [x] 1.10 Move `mouse_button` down, moves, up; verify selection and button released.
- [x] 1.11 Move `mouse_button` up with no down, down twice, down with `drag=true`, bad value.
- [x] 1.12 Click with no location; Click with no location plus `modifiers`.
- [x] 1.13 Type with no location into a focused field; caret and selection unchanged.
- [x] 1.14 Type with no location and `clear=true`, `caret_position`, `press_enter`.
- [x] 1.15 Wait decimals: 0.5, 0.01, 0, "1.5", -1, "abc", measured; "very large" checked by code reading only, since running it would block the session.
- [x] 1.16 Held-key check after every test above.

## 2. Regressions of round-1 fixes
- [x] 2.1 FileSystem `write` with `overwrite=false` on an existing file.
- [x] 2.2 FileSystem boolean strings (yes/no/1/0/on/off/unknown).
- [x] 2.3 Process kill by exact name vs. near-miss name (own processes only).
- [x] 2.4 Registry delete of a key with sub-keys, with and without `recursive`.
- [x] 2.5 Snapshot hides elements covered by another window.
- [x] 2.6 PowerShell error stream at exit 0; `timeout` below 1; real timeout.
- [x] 2.7 Registry binary values (hex list, hex string, decimal list, bad input); read back with reg.exe.
- [x] 2.8 Notification unknown app id; valid app id.
- [x] 2.9 Screenshot "window list skipped" wording; grid lines each alone and together.
- [x] 2.10 Scrape note when summary unavailable.
- [x] 2.11 Click `clicks` 0-3 and out-of-range values; MultiSelect wording by mode.
- [x] 2.12 Snapshot `[label:N]` ids; click by a label read from text.
- [x] 2.13 App switch by substring and program name; launch by name; resize exact size.
- [x] 2.14 Snapshot `region` reads only overlapping windows (timing).
- [x] 2.15 Screenshot backends dxcam/pillow/bad value (via a separate server run).
- [x] 2.16 VS Code-family guard: Snapshot lists VS Code by name only, without freezing it.

## 3. Edge cases
- [x] 3.1 Empty and whitespace inputs to every text parameter.
- [x] 3.2 Very long text (10k+ chars) to Type, Clipboard, FileSystem, PowerShell.
- [x] 3.3 Unicode, emoji, RTL and combining characters through Type, Clipboard, FileSystem, Registry.
- [x] 3.4 Paths with spaces, Unicode names, trailing dots, long paths.
- [x] 3.5 Minimised window: App switch restores it; Snapshot leaves it out. Typing "into" a minimised window was skipped on purpose: the keys would go to whatever is in front (VS Code).
- [x] 3.6 Maximised window: App resize, Screenshot region.
- [x] 3.7 Off-screen window (moved to x=-3000): App resize allowed it silently; WaitFor still finds its elements. Click by label on it skipped (the clamped click would hit another window).
- [x] 3.8 Off-screen / negative / huge coordinates for Click, Move, Scroll, Screenshot region.
- [x] 3.9 Rapid back-to-back calls (10+ Clicks, Types, Screenshots) - order and completeness.
- [ ] 3.10 [User] True high-DPI test (125%/150% scaling). Needs the user to change display scaling and sign out, which the agent cannot do without logging the user out of this session. Optional.

## 4. Chained workflows (truthfulness)
- [x] 4.1 Notepad: launch_executable with a new file (opened as a tab in the user's window), type, Ctrl+S, read the file back two ways, close only that tab with Ctrl+W (not by PID: the tab shares the user's process).
- [x] 4.2 Harness form: fill with MultiEdit by label, press ShowLater, WaitFor the revealed text, compare state.json (adapted: the harness has no check boxes or submit button). Found 1.3 of the round-2 backlog here.
- [x] 4.3 Registry: create key, write every type, list, read back with PowerShell, delete (done inside block 2, 2.4 and 2.7).
- [x] 4.4 Clipboard to app: set, paste with Shortcut, read back via the app's text.
- [x] 4.5 Edge tab: open own tab, Scrape `use_dom`, click a link by label, close own tab.
- [x] 4.6 Compare every reply in 4.1-4.5 to reality; list any false "done".

## 5. Skills/Skill.md check
- [x] 5.1 Read Skills/Skill.md line by line.
- [x] 5.2 Mark each claim confirmed, wrong or untested, using this round's results.

## 6. Write-up
- [x] 6.1 Write Plan/windows-mcp-open-issues-round2.md grouped by priority.
- [x] 6.2 Update docs/testing/windows-mcp-tool-test-report.md with a round-2 section.
- [x] 6.3 Clean up: test folder, registry key, own PIDs, own tabs, clipboard restored.
- [x] 6.4 Summarise findings to the user and ask which bugs to fix.

# Implementation verification
- Every result is checked a second way (harness log/state, Screenshot, file read, PowerShell registry read, process list) - never the tool's own reply alone.
- After every input test the held-key checker reports nothing held.
- Cleanup confirmed: `%TEMP%\wmcp-r2` gone, `HKCU:\Software\WMCP-Test` gone, no test PIDs left, clipboard restored.
- Acceptance: every task above is done, or marked [User] with the reason; every bug has tool, steps, actual, expected, severity and suggested fix.
