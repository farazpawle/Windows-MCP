---
Title: Windows-MCP round 6 - speed and accuracy (tasks)
Description: Task list for Plan/windows-mcp-round6-speed-accuracy-plan.md. Part A accuracy (R6-1 App switch confirms the front window, R6-2 multi-click re-checks each item, R6-3 optional expect= on Click/Type by loc). Part B speed (R6-4 cached element search, closes R5-I2; R6-5 Scroll re-reads one element, closes R5-I1; R6-6 Registry via winreg keeping today's replies, closes R5-2; R6-7 OCR helper only if the user approves). Part C fewer calls (R6-8 recipes page; R6-9 "steps in one go" tool, design approved by the user first). Part D cleanup (R6-10 one fuzzy library). Part E user-only checks from round 4 (R6-11). Part F finish (R6-12 round-5 guide fixes and one guide ZIP rebuild). [User] tasks: R6-7b, R6-9b, R6-11a, R6-11b. Status 2026-09-28: R6-1 done; the rest not started.
Total Tasks: 66
---

# Round 6 - speed and accuracy

"Unit" = test written first and seen failing (a test that pins today's behaviour before a
rewrite passes on both sides; each item still has one that fails first). "Live" =
`windows-mcp-live-test` harness (or a real app the test starts), checked a second way, timed.
One commit per item.

**Order** (round-5 items in their recommended slot; they stay in
`Plan/windows-mcp-open-issues-round5.md`):
R6-1, R6-4, R6-5, R6-2, R6-3, R5-1, R5-3, R5-4, R5-I3, R6-6, R6-10, R6-8, R6-9, R6-7, R6-12,
then R6-11. R5-I4 is a user decision, any time.

# Part A - Accuracy

- [x] R6-1 **App switch confirms the window really came to the front.**
  - [x] a. Unit: when the window in front after the switch is not the target, the reply is a tool error naming the window in front.
  - [x] b. Unit: a dialog owned by the target coming to the front counts as success.
  - [x] c. Unit: a switch that works first time still replies "Switched to ...".
  - [x] d. After the switch, poll the front window for up to 0.1 s and compare it with the target or a window it owns.
  - [x] e. Retry the switch once when they differ.
  - [x] f. Raise the error when the retry also fails.
  - [x] g. Update the App `switch` entry in `Skills/windows-mcp/references/apps-windows.md`.
  - **Verify:** Live - switch to the harness window while another window is in front: the reply matches `GetForegroundWindow`; App `launch` of an already-open app (which switches) still works. The refused-switch path is proven by the unit test (Windows' focus lock cannot be forced reliably live).
  - **Done 2026-09-28:** three live switches between two harness windows, each with the other in front: `GetForegroundWindow` equalled the target every time, 0.075-0.117 s per call. The `launch` check was dropped: `launch` never calls `switch_app` (the plan note was wrong), so it is unchanged. Extra unit test: nothing in front (handle 0) gives the error, not a crash.

- [ ] R6-2 **MultiSelect / MultiEdit re-check each labelled item just before its click** (`loc` items have nothing to check against and are clicked as today).
  - [ ] a. Add to the live-test harness a list that inserts a row above item 2 when item 1 is clicked.
  - [ ] b. Unit: when item 2 is no longer at its spot after click 1, the call stops before clicking it and names item 2 and the clicks done.
  - [ ] c. Move the label still-there check from before the batch into the click loop.
  - [ ] d. Update the MultiSelect and MultiEdit entries in `Skills/windows-mcp/references/input.md`.
  - **Verify:** Live - MultiSelect of items 1 and 3 on the shifting list stops at item 3 with the error; on an unchanged list both are selected.

- [ ] R6-3 **Click and Type by position can refuse when the wrong thing is there (optional `expect=`).**
  - [ ] a. Unit: Click `loc` with `expect="Save"` clicks when the element at the point or one of its first three ancestors has a name containing "Save" (case ignored).
  - [ ] b. Unit: with something else at the point, it refuses without clicking and names what is there.
  - [ ] c. Unit: on a VS Code-family or not-responding window, `expect` refuses without reading that window's tree.
  - [ ] d. Unit: Click `loc` without `expect` behaves as today.
  - [ ] e. Add `expect` to Click.
  - [ ] f. Add `expect` to Type.
  - [ ] g. Update the Click and Type tool descriptions and their entries in `references/input.md`.
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
  - [ ] d. Shorten the settle wait where the profile shows the position already stable (keep the two-equal-readings rule from R4-7).
  - [ ] e. Tick R5-I1 in the round-5 backlog, pointing here.
  - **Verify:** Live - three Scrolls in a Notepad test tab: each under 0.5 s, each "now" equal to the next "was".

- [ ] R6-6 **Registry uses Python's `winreg` instead of starting PowerShell, with today's replies.**
  - [ ] a. Unit: no Registry mode starts PowerShell (fails today).
  - [ ] b. Unit: `get` shows String, MultiString (JSON list), DWord (as today's signed Int32), QWord, Binary (hex), the `(Default)` value, and ExpandString already expanded, each in today's reply text.
  - [ ] c. Unit: `set` writes each type and creates a missing key.
  - [ ] d. Unit: `list` reply matches today's and holds no `\r` (closes R5-2).
  - [ ] e. Unit: `delete` keeps the wildcard guard.
  - [ ] f. Unit: `delete` without `name` refuses a key with sub-keys unless `recursive=true`, which removes the whole tree.
  - [ ] g. Unit: `HKCU:\`, `HKEY_CURRENT_USER\`, `HKLM\` and the other hive spellings map to the right hive; paths naming no hive are still refused.
  - [ ] h. Unit: a missing key or value is a tool error naming the path and the reason.
  - [ ] i. Rewrite `get` on `winreg`.
  - [ ] j. Rewrite `set` on `winreg`.
  - [ ] k. Rewrite `list` on `winreg`.
  - [ ] l. Rewrite `delete` on `winreg` (recursive delete through pywin32's `RegDeleteTree`).
  - [ ] m. Tick R5-2 in the round-5 backlog, pointing here.
  - [ ] n. Update the Registry entry in `references/system-tools.md` and CLAUDE.md's "implemented via PowerShell cmdlets".
  - **Verify:** Live - every mode on `HKCU:\Software\WMCP-Test` with every value type, checked with `reg.exe query`; each call under 0.05 s (was 0.25-0.33 s).

- [ ] R6-7 **Kept-running OCR helper (only if approved).**
  - [ ] a. Profile FindText: process start, WinRT load, the OCR itself.
  - [ ] b. [User] Decide whether to build it (needs a person's judgement: it saves the measured start-up share of ~1.2 s per FindText but adds a background program that must restart itself after a crash).
  - [ ] c. If yes, write the build subtasks here from the profile.
  - **Verify:** per the decision - Live FindText results identical to today's, time from the MCP log.

# Part C - Fewer calls per task

- [ ] R6-8 **Recipes page in the guide.**
  - [ ] a. List the jobs test rounds 1-5 (`docs/testing/windows-mcp-tool-test-report.md`) did by clicking that one PowerShell or FileSystem call can do.
  - [ ] b. Pick 10-15 of them.
  - [ ] c. Write each as a PowerShell snippet for the PowerShell tool, naming the click-through it replaces.
  - [ ] d. Run each snippet once through the connected server on test data only (`%TEMP%`, `HKCU:\Software\WMCP-Test`), check its effect a second way, then undo it.
  - [ ] e. Write `Skills/windows-mcp/references/recipes.md` in the other reference pages' layout.
  - [ ] f. Link it from `SKILL.md`'s "Which tool for which job" table.
  - **Verify:** every recipe run live and checked; `SKILL.md` grows by one table row only.

- [ ] R6-9 **"Steps in one go" tool.**
  - [ ] a. Write the design as a Plan file (step types, the checks each step keeps including R6-2 and `expect=` from R6-3, what stops the run, the reply, a step limit, new-window handling, action log).
  - [ ] b. [User] Approve the design (needs a person's judgement: a new tool that changes how agents drive the desktop).
  - [ ] c. Write the build subtasks here from the approved design (tests first, guide, tool count in CLAUDE.md).
  - **Verify:** per design - Live, a four-step save-as on the harness in one call; a deliberately wrong step stops the run and the reply names it.

# Part D - Cleanup

- [ ] R6-10 **One fuzzy-matching library.**
  - [ ] a. Unit: a table of app and window names (short, long, zero-width space, near-duplicates) picks today's matches (passes before and after the switch).
  - [ ] b. Switch the window and app name matching import from `fuzzywuzzy` to `thefuzz` (same functions; its scores come from `rapidfuzz` and may differ slightly).
  - [ ] c. Remove `fuzzywuzzy` from `pyproject.toml`.
  - [ ] d. Remove `python-levenshtein` from `pyproject.toml` (only `fuzzywuzzy` used it).
  - [ ] e. Refresh the lock with `uv lock --offline`, then `uv sync --extra dev` (stop any running server from this `.venv` first).
  - [ ] f. Correct CLAUDE.md: fuzzy matching is for window and app names; element names use exact, then a single partial, match.
  - **Verify:** `pytest` green including a.; Live App `launch name=Notepad` and `switch name=Notepad` pick the same window as before.

# Part E - Carried over from rounds 4 and 5 (user only)

- [ ] R6-11 **Open user checks from round 4** (were R4-11c, D.33 and round-5 task 8.6).
  - [ ] a. [User] Optional lock/unlock check (needs the user: over Remote Desktop a lock ends the session view and only the user can sign back in): press Win+L, sign back in, then ask Claude for a full Screenshot; its Backend line should read dxcam.
  - [ ] b. [User] Upload the guide ZIP in Claude Desktop (needs the user's Claude account): Customize > Skills > replace the windows-mcp skill with the ZIP; keep it on. Do it once, after R6-12b.
  - **Verify:** the user reports the Backend line and that the skill shows the new recipes page.

# Part F - Finish

- [ ] R6-12 **One guide pass and one ZIP rebuild at the end.**
  - [ ] a. Apply round-5 D5-1 to D5-3 with the timings measured in round 6 (not the round-5 ones).
  - [ ] b. Rebuild the Claude Desktop guide ZIP once (replaces round-5 D5-4).
  - [ ] c. Tick D5-1 to D5-4 in the round-5 backlog, pointing here.
  - **Verify:** the ZIP's files equal `Skills/windows-mcp/`; every timing in `SKILL.md` matches the round-6 measurements.

# Implementation verification

- Every item's Verify done live and checked a second way, with times from the MCP log.
- Speed items: same target picked and same reply text as before, only faster.
- `pytest`, `ruff check .` and `ruff format --check .` clean with zero warnings.
- Guide, tool descriptions and CLAUDE.md updated with each change; `known-gaps.md` lines removed for fixed items; the guide ZIP rebuilt once, in R6-12.
- Open `[User]` tasks listed to the user at the end of each session: R6-7b, R6-9b, R6-11a, R6-11b.
