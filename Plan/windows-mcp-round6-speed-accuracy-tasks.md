---
Title: Windows-MCP round 6 - speed and accuracy (tasks)
Description: Task list for Plan/windows-mcp-round6-speed-accuracy-plan.md. Part A accuracy (R6-1 App switch confirms the front window, R6-2 multi-click re-checks each item, R6-3 optional expect= on Click/Type by loc, R6-13 Snapshot order of a native window, logged 2026-09-28). Part B speed (R6-4 cached element search, closes R5-I2; R6-5 Scroll re-reads one element, closes R5-I1; R6-6 Registry via winreg keeping today's replies, closes R5-2; R6-7 OCR helper only if the user approves). Part C fewer calls (R6-8 recipes page; R6-9 "steps in one go" tool, design approved by the user first). Part D cleanup (R6-10 one fuzzy library). Part E user-only checks from round 4 (R6-11). Part F finish (R6-12 round-5 guide fixes and one guide ZIP rebuild). [User] tasks: R6-7b, R6-9b, R6-11a, R6-11b. Status 2026-09-28: R6-1, R6-2, R6-3, R6-5, R6-6 and R6-13 done (R5-1, R5-3, R5-4 and R5-I3 too, in the round-5 file); R6-4 closed by measurement with no code change (the 1.5 s was a throwaway Edge profile slowing every window); R6-10 done 2026-09-29; the rest not started.
Total Tasks: 70
---

# Round 6 - speed and accuracy

"Unit" = test written first and seen failing (a test that pins today's behaviour before a
rewrite passes on both sides; each item still has one that fails first). "Live" =
`windows-mcp-live-test` harness (or a real app the test starts), checked a second way, timed.
One commit per item.

**Order** (round-5 items in their recommended slot; they stay in
`Plan/windows-mcp-open-issues-round5.md`):
R6-1, R6-4, R6-5, R6-2, R6-3, R5-1, R5-3, R5-4, R5-I3, R6-13, R6-6, R6-10, R6-8, R6-9, R6-7, R6-12,
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

- [x] R6-2 **MultiSelect / MultiEdit re-check each labelled item just before its click** (`loc` items have nothing to check against and are clicked as today).
  - [x] a. Add to the live-test harness a list that inserts a row above item 2 when item 1 is clicked.
  - [x] b. Unit: when item 2 is no longer at its spot after click 1, the call stops before clicking it and names item 2 and the clicks done.
  - [x] c. Move the label still-there check from before the batch into the click loop.
  - [x] d. Update the MultiSelect and MultiEdit entries in `Skills/windows-mcp/references/input.md`.
  - **Verify:** Live - MultiSelect of items 1 and 3 on the shifting list stops at item 3 with the error; on an unchanged list both are selected.
  - **Done 2026-09-28:** live on the harness (`shifting_list=True`): MultiSelect labels of items 1 and 3 clicked item 1 (the window logged it and the inserted row), then stopped with "MultiSelect stopped at label 4: ... no longer at its spot ... Done: label 6."; item 3 was never clicked. On an unchanged list both clicks were logged (0.43 s). Also: Ctrl is now released in a `finally`, and failures name items as `locs[i]` / `label N`.

- [x] R6-3 **Click and Type by position can refuse when the wrong thing is there (optional `expect=`).**
  - [x] a. Unit: Click `loc` with `expect="Save"` clicks when the element at the point or one of its first three ancestors has a name containing "Save" (case ignored).
  - [x] b. Unit: with something else at the point, it refuses without clicking and names what is there.
  - [x] c. Unit: on a VS Code-family or not-responding window, `expect` refuses without reading that window's tree.
  - [x] d. Unit: Click `loc` without `expect` behaves as today.
  - [x] e. Add `expect` to Click.
  - [x] f. Add `expect` to Type.
  - [x] g. Update the Click and Type tool descriptions and their entries in `references/input.md`.
  - **Verify:** Live - harness: a matching `expect` clicks; a pop-up opened between the Screenshot and the Click makes it refuse; Click time within 0.02 s of today's.
  - **Done 2026-09-28:** live on the harness (Save button, text box, a second harness window as the pop-up): `expect="save"` clicked; with the pop-up over the button Click refused (`found pane in "R63Popup"`) and the pop-up logged nothing; Type with `expect="Save"` on the text box refused and nothing was typed. The main window logged exactly the 13 allowed clicks. Timing over 6 alternating pairs: median 0.160 s plain, 0.164 s with `expect`. Extra unit tests: a fourth parent is too far, a blank `expect` is refused, Type `expect` without `loc`/`label` is refused, a UIA error refuses.

- [x] R6-13 **Low - Snapshot may list a native window's elements bottom-to-top.** Found during R5-3 (2026-09-28), user asked to log it: a `region` Snapshot of a Notepad file tab listed the scroll bar first, then the words from the last line up, the document, tabs, menu, and the title-bar buttons last (labels count down the page). The region filter keeps the order it is given, so the likely cause is the reorder step for native windows (`tree/service.py` `get_nodes`, `_reverse_children_order`). Not yet checked without `region`, or in other apps.
  - [x] a. Live: Snapshot of a Notepad test tab with and without `region`, and of the harness window: note the order each lists.
  - [x] b. Unit: a native window's elements are listed top of the window first (title bar, menu, tabs, document), words in reading order.
  - [x] c. Fix the order where it goes wrong.
  - **Verify:** Live - Snapshot of a Notepad test tab, with and without `region`: title-bar buttons and menu first, the document's words in reading order; labels unchanged for Click.
  - **Done 2026-09-28:**
    - Before, both with and without `region`: Notepad listed its words last-first, then the document, tabs, menu, title bar; the harness its text box, buttons, title bar; labels counted up the page. The taskbar (one row) was already left to right.
    - Cause: UIA gives a window's content before its title bar and menus, the traversal walks children last-to-first, and one flip of the tree afterwards (`_reverse_children_order`) put each element's parts (a document's words, a tab's close button) before it, reversed.
    - Fix (`tree/views.py` `sort_reading_order`, called in `get_nodes` for native windows): each tree level sorted into rows (top to bottom; same row when each middle lies inside the other's height), left to right within a row, a group placed by its top element; the window's flat interactive and scroll lists re-sorted to the tree, so labels count down it. A named pop-up window inside a window is now its own group, so its buttons are not sorted in among what lies under it. Browser pages and window order are unchanged.
    - Live after: Notepad test tab with and without `region` (0.27 / 0.29 s) and the harness: System menu, tabs, Minimise/Maximise/Close, then File/Edit/View and the toolbar, the document, then alpha ... foxtrot; labels 0, 1, 2 ... down the page. Click `label=5` from the new harness Snapshot clicked "Save" (the harness logged exactly `click Save`).
    - The first live run's reads took 4-32 s with an Avast window up; the second took 0.1-0.3 s. Not from this code.

# Part B - Speed

- [x] R6-4 **Click `element=` fetches every match's details in one request (root cause of R5-I2).** Closed by measurement, no code change (user decision 2026-09-28).
  - [x] a. Profile Click `element="button:Got it"` on a fresh throwaway Edge window: search, per-match reads, cover check.
  - [-] b. Unit: the element search reads type, name, box and offscreen from a cache request. Not done: see findings.
  - [-] c. Build the cache request for those four properties. Not done.
  - [-] d. Switch the search to `FindAllBuildCache` and cached reads. Not done.
  - [x] e. Live: on the Edge page, cached values equal the uncached ones for every match (equal in every round; measured, not adopted).
  - [x] f. Tick R5-I2 in `Plan/windows-mcp-open-issues-round5.md`, pointing here.
  - **Verify:** Live - Click `element=` in Edge under 0.5 s (was 1.5 s); Notepad no slower than 0.30 s; the same element picked as before.
  - **Findings 2026-09-28 (the premise was wrong):**
    - `find_element` on the throwaway Edge page with the sync notice: FindAll 0.29-0.31 s, uncached reads of all 3 matches 0.019 s, cover check ~0.08 s, total 0.39-0.40 s. `FindAllBuildCache` saved 0.02-0.06 s. Warm, on a page without the notice: 0.017 s in total.
    - A full Click `element="button:Got it" window="R64 Profile Page"`: 1.6-2.0 s, of which `pick_window` (by name, i.e. `get_windows`) was 1.16-1.39 s on every call, `find_element` 0.18-0.33 s and the click with its settle 0.17 s.
    - `get_windows` normally takes 0.06-0.09 s, and `pick_window` by name against the user's own Edge takes 0.06-0.08 s. With a fresh throwaway Edge profile it took 1.56 s 3 s after the start, 0.09 s at 10 s and 20 s, and 1.4-1.8 s from about 40 s on (after the profile signs in and syncs). Every UIA call slowed then (ControlFromHandle 0.013-0.035 s per window of any app, against 0.001 s), with low CPU use. Cause not found; it is outside this code.
    - So round 5's 1.5 s was the throwaway profile's start-up and sync, not the element search. Guide note added to `references/web.md`.

- [x] R6-5 **Scroll re-reads the element it found instead of walking up again (R5-I1).**
  - [x] a. Profile one Scroll in Notepad and in the harness: wheel, settle wait, each position read.
  - [x] b. Unit: after the first read, later reads ask only the found scrollable element; if it is gone they fall back to the walk.
  - [x] c. Keep the found element from the "before" read and reuse it.
  - [x] d. Shorten the settle wait where the profile shows the position already stable (keep the two-equal-readings rule from R4-7).
  - [x] e. Tick R5-I1 in the round-5 backlog, pointing here.
  - **Verify:** Live - three Scrolls in a Notepad test tab: each under 0.5 s, each "now" equal to the next "was".
  - **Done 2026-09-28:**
    - Profile (harness, 3 notches): 0.43-0.45 s = move 0.11 (a fixed 0.1 s hover settle), wheel 0.25 (0.05 s per notch plus a fixed 0.1 s), settle 0.06-0.07, position reads ~0.01 each. The reads were never the cost.
    - Notepad animates each scroll for ~0.25-0.3 s after the wheel (readings 0.8, 1.3, 1.6, 2.1, 2.6, 2.9, 2.9 at 50 ms steps), so its settle wait legitimately runs ~0.3 s.
    - Changes: the reader walks once and re-reads that element, walking again if it is gone (`tree/utils.py` `scroll_reader`). The fixed 0.1 s after the wheel is gone, and `_settled(unmoved=before)` does not count readings equal to the one before the wheel as settled. The Scroll's pointer move has no hover settle (`move(settle=0)`).
    - Live after: harness 0.22 s (from 0.44); Notepad test tab 0.535 / 0.497 / 0.497 s (from 0.60-0.68; the first call is 0.035 s over the target). Every "now" equalled the next "was". The harness logged all 12 wheel notches (none lost without the settle).
    - The Notepad test tab was a file opened with `notepad.exe <file>` (its own tab), closed with Ctrl+W; the user's window stayed open.

- [x] R6-6 **Registry uses Python's `winreg` instead of starting PowerShell, with today's replies.**
  - [x] a. Unit: no Registry mode starts PowerShell (fails today).
  - [x] b. Unit: `get` shows String, MultiString (JSON list), DWord (unsigned, as pwsh 7 showed it: the "signed Int32" here was wrong), QWord, Binary (hex), the `(Default)` value, and ExpandString already expanded, each in today's reply text.
  - [x] c. Unit: `set` writes each type and creates a missing key.
  - [x] d. Unit: `list` reply matches today's and holds no `\r` (closes R5-2).
  - [x] e. Unit: `delete` keeps the wildcard guard.
  - [x] f. Unit: `delete` without `name` refuses a key with sub-keys unless `recursive=true`, which removes the whole tree.
  - [x] g. Unit: `HKCU:\`, `HKEY_CURRENT_USER\`, `HKLM\` and the other hive spellings map to the right hive; paths naming no hive are still refused.
  - [x] h. Unit: a missing key or value is a tool error naming the path and the reason.
  - [x] i. Rewrite `get` on `winreg`.
  - [x] j. Rewrite `set` on `winreg`.
  - [x] k. Rewrite `list` on `winreg`.
  - [x] l. Rewrite `delete` on `winreg` (recursive delete through pywin32's `RegDeleteTree`).
  - [x] m. Tick R5-2 in the round-5 backlog, pointing here.
  - [x] n. Update the Registry entry in `references/system-tools.md` and CLAUDE.md's "implemented via PowerShell cmdlets".
  - **Verify:** Live - every mode on `HKCU:\Software\WMCP-Test` with every value type, checked with `reg.exe query`; each call under 0.05 s (was 0.25-0.33 s).
  - **Done 2026-09-28:**
    - Recorded 56 replies (every mode, every type, the default value, edge numbers, missing key/value, sub-keys, wildcard) from the PowerShell version first, then again after: 45 identical; the other 11 are the intended changes - error texts now name the path as given and the reason (PowerShell's own text before, with a different path spelling), and `list` has no stray `\r` and shows values whose names start with "PS" (PowerShell's list filtered them out as its own fields). `reg query` showed every type and value as set (REG_DWORD 0xffffffff for -1, REG_MULTI_SZ items, REG_EXPAND_SZ unexpanded).
    - Time per call: under 1 ms in-process, 1-6 ms through the tool (first call 0.06 s), from 0.29-0.48 s.
    - Also changed: a DWord/QWord outside its range is refused before writing (was PowerShell's conversion error); `delete` with `name=""` now deletes the default value, as the tool description says (it deleted the whole key); a whole hive (`HKCU:\`, `HKLM\`) is always refused.
    - Unit tests use a real throwaway key `HKCU\Software\WMCP-Test\UT<pid>`; the registry tests run in 1.6 s instead of 36 s. The PowerShell-command tests (`test_registry.py`, `test_registry_default_value.py`, two in `test_open_issues_section1/2.py`) were replaced by behaviour tests.
    - Incident, no damage: run against the old code, the new hive-delete test stubbed only the new delete calls, so the old code's PowerShell path was live; the old code refused (non-recursive: "has 16 sub-keys"; recursive: HKCU's keys all intact, AppEvents first in order untouched; session not elevated). Then, under the new code, four old tests that stubbed only PowerShell wrote a real `HKCU\Software\T` (value "b"); `Software\Test` never existed. Rule added to CLAUDE.md.

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

- [x] R6-10 **One fuzzy-matching library.**
  - [x] a. Unit: a table of app and window names (short, long, zero-width space, near-duplicates) picks today's matches (passes before and after the switch).
  - [x] b. Switch the window and app name matching import from `fuzzywuzzy` to `thefuzz` (same functions; its scores come from `rapidfuzz` and may differ slightly).
  - [x] c. Remove `fuzzywuzzy` from `pyproject.toml`.
  - [x] d. Remove `python-levenshtein` from `pyproject.toml` (only `fuzzywuzzy` used it).
  - [~] e. Refresh the lock with `uv lock --offline` (done), then `uv sync --extra dev` (partial: see below).
  - [x] f. Correct CLAUDE.md: fuzzy matching is for window and app names; element names match as a case-ignored part of the name (a native substring search, not "exact then partial").
  - **Verify:** `pytest` green including a.; Live App `launch name=Notepad` and `switch name=Notepad` pick the same window as before.
  - **Done 2026-09-29:**
    - `tests/test_fuzzy_matching.py` (12 window names, 8 app names) passed on the old code except the "uses thefuzz" check, and all pass after. `pytest` 1698 passed, ruff clean.
    - Live, read-only (no input sent): old and new picks compared on this PC's 5 open windows (47 names from their titles, 26 matching something) and 222 Start-menu apps (19 names incl. Notepad): identical every time. The old library ran from a temp copy with a stand-in for python-Levenshtein 0.27 (itself a rapidfuzz wrapper; the real one was not in uv's offline cache). No App switch/launch was sent: the choice of window is what changed, the switching code did not.
    - Found, unchanged (both libraries): `launch name="Notepad++"` picks "Notepad" when both are in the Start menu - the matcher drops "+", they tie at 100 and the first listed wins. Pinned in the test. A name made only of punctuation ("-") scores 0 against everything and logs a warning.
    - Sync: six windows-mcp servers from this `.venv` were running, so `uv sync --extra dev --offline --no-install-project` removed fuzzywuzzy but not Levenshtein (its `.pyd` is loaded). It left `Levenshtein/` with only the `.pyd` and two dist-info folders; nothing imports it. Run `uv sync --extra dev --offline` once those servers are stopped to clear it.

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
