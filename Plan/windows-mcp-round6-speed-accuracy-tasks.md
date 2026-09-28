---
Title: Windows-MCP round 6 - speed and accuracy (tasks)
Description: Task list for Plan/windows-mcp-round6-speed-accuracy-plan.md. Part A accuracy (R6-1 App switch confirms the front window, R6-2 multi-click re-checks each item, R6-3 optional expect= on Click/Type by loc). Part B speed (R6-4 cached element search, closes R5-I2; R6-5 Scroll re-reads one element, closes R5-I1; R6-6 Registry via winreg, closes R5-2; R6-7 OCR helper only if the user approves). Part C fewer calls (R6-8 recipes page; R6-9 "steps in one go" tool, design approved by the user first). Part D cleanup (R6-10 one fuzzy library). Two [User] decisions: R6-7b, R6-9b. Status 2026-09-28: not started.
Total Tasks: 55
---

# Round 6 - speed and accuracy

"Unit" = test written first and seen failing. "Live" = `windows-mcp-live-test` harness (or a
real app the test starts), checked a second way, timed. Order: R6-1, R6-4, R6-5, R6-6, R6-2,
R6-3, R6-8, R6-9, R6-7; R6-10 any time. One commit per item.

# Part A - Accuracy

- [ ] R6-1 **App switch confirms the window really came to the front.**
  - [ ] a. Unit: when the window in front after the switch is not the target, the reply is a tool error naming the window in front.
  - [ ] b. Unit: a switch that works first time still replies "Switched to ...".
  - [ ] c. After the switch, compare the front window with the target.
  - [ ] d. Retry the switch once when they differ.
  - [ ] e. Raise the error when the retry also fails.
  - [ ] f. Update the App `switch` entry in `Skills/windows-mcp/references/apps-windows.md`.
  - **Verify:** Live - switch to the harness window while another window is in front: the reply matches `GetForegroundWindow`. The refused-switch path is proven by the unit test (Windows' focus lock cannot be forced reliably live).

- [ ] R6-2 **MultiSelect / MultiEdit re-check each item just before its click.**
  - [ ] a. Add to the live-test harness a list that inserts a row above item 2 when item 1 is clicked.
  - [ ] b. Unit: when item 2 is no longer at its spot after click 1, the call stops before clicking it and names item 2 and the clicks done.
  - [ ] c. Move the label still-there check from before the batch into the click loop.
  - [ ] d. Update the MultiSelect and MultiEdit entries in `Skills/windows-mcp/references/input.md`.
  - **Verify:** Live - MultiSelect of items 1 and 3 on the shifting list stops at item 3 with the error; on an unchanged list both are selected.

- [ ] R6-3 **Click and Type by position can refuse when the wrong thing is there (optional `expect=`).**
  - [ ] a. Unit: Click `loc` with `expect="Save"` clicks when the element at the point or one of its ancestors has a name containing "Save".
  - [ ] b. Unit: with something else at the point, it refuses without clicking and names what is there.
  - [ ] c. Unit: Click `loc` without `expect` behaves as today.
  - [ ] d. Add `expect` to Click.
  - [ ] e. Add `expect` to Type.
  - [ ] f. Update the Click and Type tool descriptions and their entries in `references/input.md`.
  - **Verify:** Live - harness: a matching `expect` clicks; a pop-up opened between the Screenshot and the Click makes it refuse; Click time within 0.02 s of today's.

# Part B - Speed

- [ ] R6-4 **Click `element=` fetches every match's details in one request (root cause of R5-I2).**
  - [ ] a. Profile Click `element="button:Got it"` on a fresh throwaway Edge window: search, per-match reads, cover check.
  - [ ] b. Unit: the element search reads type, name, box and offscreen from a cache request.
  - [ ] c. Build the cache request for those four properties.
  - [ ] d. Switch the search to `FindAllBuildCache` and cached reads.
  - [ ] e. Live: on the Edge page, cached values equal the uncached ones for every match.
  - [ ] f. Tick R5-I2 in `Plan/windows-mcp-open-issues-round5.md`, pointing here.
  - **Verify:** Live - Click `element=` in Edge under 0.5 s (was 1.5 s); Notepad no slower than 0.30 s; the same element picked as before.

- [ ] R6-5 **Scroll re-reads the element it found instead of walking up again (R5-I1).**
  - [ ] a. Profile one Scroll in Notepad and in the harness: wheel, settle wait, each position read.
  - [ ] b. Unit: after the first read, later reads ask only the found scrollable element; if it is gone they fall back to the walk.
  - [ ] c. Keep the found element from the "before" read and reuse it.
  - [ ] d. Shorten the settle wait where the profile shows the position already stable.
  - [ ] e. Tick R5-I1 in the round-5 backlog, pointing here.
  - **Verify:** Live - three Scrolls in a Notepad test tab: each under 0.5 s, each "now" equal to the next "was".

- [ ] R6-6 **Registry uses Python's `winreg` instead of starting PowerShell.**
  - [ ] a. Unit: `get` reads string, expand string, multi string, dword, qword, binary and the `(Default)` value with today's reply text.
  - [ ] b. Unit: `set` writes each of those types.
  - [ ] c. Unit: `list` reply matches today's and holds no `\r` (closes R5-2).
  - [ ] d. Unit: `delete` keeps the wildcard guard.
  - [ ] e. Unit: `HKCU:\`, `HKEY_CURRENT_USER\` and `HKLM:` style paths map to the right hive.
  - [ ] f. Rewrite `get` on `winreg`.
  - [ ] g. Rewrite `set` on `winreg`.
  - [ ] h. Rewrite `list` on `winreg`.
  - [ ] i. Rewrite `delete` on `winreg`.
  - [ ] j. Tick R5-2 in the round-5 backlog, pointing here.
  - [ ] k. Update the Registry entry in `references/system-tools.md` and CLAUDE.md's "implemented via PowerShell cmdlets".
  - **Verify:** Live - every mode on `HKCU:\Software\WMCP-Test` with every value type, checked with `reg.exe query`; each call under 0.05 s (was 0.25-0.33 s).

- [ ] R6-7 **Kept-running OCR helper (only if approved).**
  - [ ] a. Profile FindText: process start, WinRT load, the OCR itself.
  - [ ] b. [User] Decide whether to build it (needs a person's judgement: it saves the measured start-up share of ~1.2 s per FindText but adds a background program that must restart itself after a crash). Decide after R6-4 to R6-6.
  - [ ] c. If yes, write the build subtasks here from the profile.
  - **Verify:** per the decision - Live FindText results identical to today's, time from the MCP log.

# Part C - Fewer calls per task

- [ ] R6-8 **Recipes page in the guide.**
  - [ ] a. List the jobs test rounds 1-5 (`docs/testing/windows-mcp-tool-test-report.md`) did by clicking that one PowerShell or FileSystem call can do.
  - [ ] b. Pick 10-15 of them.
  - [ ] c. Write each as a PowerShell snippet for the PowerShell tool, naming the click-through it replaces.
  - [ ] d. Run each snippet once through the connected server and check its effect a second way.
  - [ ] e. Write `Skills/windows-mcp/references/recipes.md` in the other reference pages' layout.
  - [ ] f. Link it from `SKILL.md`'s "Which tool for which job" table.
  - [ ] g. Rebuild the Claude Desktop guide ZIP.
  - **Verify:** every recipe run live and checked; `SKILL.md` grows by one table row only.

- [ ] R6-9 **"Steps in one go" tool.**
  - [ ] a. Write the design as a Plan file (step types, the checks each step keeps, what stops the run, the reply, a step limit, new-window handling, action log).
  - [ ] b. [User] Approve the design (needs a person's judgement: a new tool that changes how agents drive the desktop).
  - [ ] c. Write the build subtasks here from the approved design (tests first, guide, tool count in CLAUDE.md).
  - **Verify:** per design - Live, a four-step save-as on the harness in one call; a deliberately wrong step stops the run and the reply names it.

# Part D - Cleanup

- [ ] R6-10 **One fuzzy-matching library.**
  - [ ] a. Switch the window and app name matching import from `fuzzywuzzy` to `thefuzz`.
  - [ ] b. Remove `fuzzywuzzy` from `pyproject.toml`.
  - [ ] c. Refresh the lock with `uv lock --offline`.
  - [ ] d. Correct CLAUDE.md: fuzzy matching is for window and app names; element names use exact, then a single partial, match.
  - **Verify:** `pytest` green; Live App `launch name=Notepad` and `switch name=Notepad` pick the same window as before.

# Implementation verification

- Every item's Verify done live and checked a second way, with times from the MCP log.
- Speed items: same target picked and same reply text as before, only faster.
- `pytest`, `ruff check .` and `ruff format --check .` clean with zero warnings.
- Guide, tool descriptions and CLAUDE.md updated with each change; `known-gaps.md` lines removed for fixed items; guide ZIP rebuilt at the end.
- Open `[User]` tasks listed to the user at the end of each session: R6-7b, R6-9b.
