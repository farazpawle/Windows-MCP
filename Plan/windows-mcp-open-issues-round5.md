---
Title: Windows-MCP open issues - round 5
Description: Findings of the round-5 re-test (2026-09-26, all 21 tools through the connected server after the round-4 backlog, timed from Claude Code's MCP log), as a task file. Every round-4 fix held. Part A Bugs - 1 Medium (Scrape use_dom drops table text), 3 Low (Registry list stray carriage return; Snapshot lists Notepad's document twice and 100.1% scroll; FindText window= crop misses a phrase the full screen finds). Part B 4 improvements (Scroll 0.7 s, Click element= in Edge 1.5 s, App list front marker when a system panel is in front, a paste option for long text into Notepad). Part D 4 guide corrections. Evidence in docs/testing/windows-mcp-tool-test-report.md (Round 5). Fixes run in round 6 (Plan/windows-mcp-round6-speed-accuracy-tasks.md); done as of 2026-09-28: R5-1, R5-2, R5-3, R5-4, R5-I1, R5-I2, R5-I3.
Total Tasks: 25
---

# Windows-MCP open issues - round 5

Evidence for every item: `docs/testing/windows-mcp-tool-test-report.md`, section "Round 5". Each item: finding, then single-action fix subtasks, then its own Verify line. "Unit" = test written first and seen failing; "Live" = `windows-mcp-live-test` harness (or a real app started by the test), checked a second way. Times are end to end from Claude Code's MCP log.

Work order: these items are slotted into the round-6 order (`Plan/windows-mcp-round6-speed-accuracy-plan.md`, "Order"); R5-I1, R5-I2, R5-2 and D5-1 to D5-4 are done there as R6-5, R6-4, R6-6 and R6-12.

# Part A - Bugs

- [x] R5-1 **Medium - Scrape `use_dom` leaves out table text.** A local page (heading, paragraph, 3-row table, button) returned only the heading and paragraph. WaitFor `text_exists use_dom=true` found the table's "405", so the text is in the tree; the "Informative Check" in `tree/service.py` (~1041-1079) keeps only `INFORMATIVE_CONTROL_TYPE_NAMES` and links, so table cells (and the button label) never reach `dom_informative_nodes`.
  - [x] a. Find which UIA control types Edge gives the table cells' text (DataItem / Text inside a Table) on a throwaway page.
  - [x] b. Unit: a table cell's text inside a browser document is added to `dom_informative_nodes`.
  - [x] c. Add the cell text in the informative check.
  - [x] d. Unit: the page text keeps table rows in order, one row per line.
  - **Verify:** Live - Scrape `use_dom=true` on a throwaway Edge page with a table returns every cell ("North 460", "South 405").
  - **Done 2026-09-28 (round 6):** Edge gives a row as a nameless DataItem holding DataItem cells named with their text; the words inside are non-control TextControls, so nothing reached the page text. A row now becomes one line of its cells joined by " | " (`tree/service.py`, after the children are read). Live on a throwaway Edge `--app` page (heading, paragraph, header row + 4 rows, one cell a link): Scrape `use_dom` returned "Region | Total", "North | 460", "South | 405", "East | 512", "West | 300" in page order, 0.24-0.57 s. Found on the way: the first read right after the page opens comes from the IA2 fallback (Chromium's UIA tree not built yet), which already gave every cell, one per line; that is likely why the table text was missing only sometimes. A link in a cell also gets its own line (kept: dropping it could lose a same-named link elsewhere). Subtask d is covered by the ordered-rows unit test.

- [x] R5-2 **Low - Registry `list` reply has a stray carriage return** after the last value ("Revenue : 5000000000\r\n\nSub-Keys").
  - [x] a. Unit: the `list` reply holds no `\r`.
  - [x] b. Strip the PowerShell output's line ends before building the reply. (Superseded: R6-6 builds the reply in Python, no PowerShell output.)
  - **Verify:** Live - Registry `list` on a test key with 6 values: no `\r` in the reply.
  - **Done 2026-09-28 by R6-6** (`Plan/windows-mcp-round6-speed-accuracy-tasks.md`): live `list` of a 15-value test key has no `\r`.

- [x] R5-3 **Low - Snapshot lists Notepad's document twice and a scroll of 100.1%.** One `document "Text editor"` entry has the value, a second at the same point has `[v:100.1%]`. With `use_vision=true` the value's bare `\r` line breaks run the lines together ("Week 39Region").
  - [x] a. Unit: an element that is both informative and scrollable is listed once, with value and scroll position.
  - [x] b. Merge the two entries.
  - [x] c. Unit: a scroll percent above 100 is shown as 100.
  - [x] d. Clamp the percent.
  - [x] e. Unit: a value with `\r` line breaks is shown with `\n`.
  - [x] f. Normalise the value's line breaks.
  - **Verify:** Live - Snapshot of a Notepad test tab scrolled to the end: one document entry, `v:100%`, value lines separate.
  - **Done 2026-09-28 (round 6):** fixed where the tree text is written (`tree/views.py`), the data lists are unchanged: an input entry and a scroll entry of the same element (same window, type, name and box) are printed as one line, the input entry's label and point, with the scroll position; percents are capped at 0-100 (also in Scroll's reply, `tree/utils.py` `_scroll_percent`); a value's line breaks print as `\n`. Live on a Notepad file tab (158 lines) scrolled to the end through UIA, one Snapshot with the merge switched off and one with it: without, `[label:27] document "Text editor" ... [value:...]` and `[label:100] document "Text editor" ... [v:100.0%]`; with, one line `[label:27] ... [value:"Week 1\nRegion North 401..."]  [v:100.0%]`. Printed as `100.0%` (the style of every other percent), not `100%`. The tab was closed through its own Close button.

- [x] R5-4 **Low - FindText `window=` misses a phrase the full screen finds.** The window crop (31,26)-(1031,628) makes OCR read "North 460 12.50" as "North 12.50", so "North 460" is not found; a region 5 px larger reads it. The same miss with `region` = the window rectangle, so the window filter is fine; the engine is sensitive to the crop.
  - [x] a. Measure on a saved screenshot which padding (e.g. 8-16 px of margin, or 4x instead of 3x) reads the row every time.
  - [-] b. Unit: `window=` reads a padded rectangle and still keeps only matches whose centre shows that window. Replaced: padding does not help (see findings); unit test instead that the enlargement uses Lanczos.
  - [-] c. Pad the window crop. Replaced: enlarge with Lanczos instead of Pillow's default bicubic (`ocr/service.py` `find_on_screen`, used by FindText and WaitFor `screen_text`).
  - **Verify:** Live - FindText `window=<test Notepad>` "North 460" finds the row the full-screen search finds.
  - **Findings 2026-09-28 (round 6):** one screenshot of a Notepad tab with a sales table, read offline at many crops. The engine does not return the word "460" at all for some crops, with or without margin: exact window crop jittered by up to 4 px missed "North 460" in 2 of 9, the same with a 12 px margin in 1 of 8. It is the pixel alignment after the 3x enlargement, so it hits full-screen reads too. Enlargement filter at 3x over 20 crops: bicubic (today) 1 crop with a miss, Lanczos 0, nearest 16; at 4x bicubic 4, Lanczos 0. Over 60 crops jittered by up to 8 px with 22 phrases (table, status bar, tabs, menu): bicubic missed "North 460" 6 times and "View" once, Lanczos neither; both missed "Total units: 1677" (54) and "UTF-8" (59-60), unrelated to the filter; 0.60 vs 0.64 s a read.
  - **Done 2026-09-28:** live on the Notepad table tab: FindText "North 460" with `window=<handle>` 1.13 s, `window="Weekly Sales Report"` 0.76 s, full screen 1.57 s, each found "North 460 12.50" at the same point. The first attempt stopped before searching (the tab was not in front); nothing was sent.

# Part B - Improvements

- [x] R5-I1 **Scroll takes 0.68-0.72 s** a call (round 4 0.27-0.56 s; guide ~0.5 s), apparently the settle wait added for R4-7.
  - [x] a. Profile one Scroll in Notepad and in the harness (wheel, settle wait, read-back).
  - [x] b. Shorten the settle wait where the position is already stable.
  - **Verify:** Live - three Scrolls in a Notepad test tab: each under 0.5 s, each "now" equal to the next "was".
  - **Done 2026-09-28 in round-6 R6-5:** Notepad 0.50-0.54 s (its own ~0.3 s scroll animation is waited out on purpose), harness 0.22 s; see R6-5.

- [x] R5-I2 **Click `element=` in Edge took 1.5 s** the first time (Notepad 0.27-0.30 s).
  - [x] a. Profile Click `element="button:Got it"` on a fresh throwaway Edge window.
  - **Verify:** Live - the profile names where the 1.5 s goes; fix only if one step dominates.
  - **Done 2026-09-28 in round-6 R6-4:** the time went to finding the window by name, slowed PC-wide while the throwaway Edge profile starts and syncs (with an everyday Edge, 0.06-0.08 s). No code change (user decision); see R6-4's findings.

- [x] R5-I3 **App `list` shows no "(front)"** when the foreground is not a listed window (the taskbar's hidden-icons panel was open).
  - [x] a. Unit: when the foreground is not listed, the header names what is in front.
  - [x] b. Add that line.
  - **Verify:** Live - with the hidden-icons panel open, App `list` says what is in front.
  - **Done 2026-09-28:** a line under the header, `In front, not listed: handle=N class C "title"`, or "Nothing is in front" when there is no foreground window. Live (in-process server, Win+B then Enter): with the tray focused it named `Shell_TrayWnd`, with the panel open `TopLevelWindowForOverflowXamlIsland "System tray overflow window."`, each equal to `GetForegroundWindow`, no line marked `(front)`, 0.045-0.05 s; with VS Code in front the reply was unchanged.

- [ ] R5-I4 **Long text into Notepad is still unusable by typing** (361 of 622 characters, repeated letters; the reply warns). A clipboard paste of the same text was exact in 0.1 s.
  - [ ] a. [User] Decide (design choice): add a Type option that pastes (backing up and restoring the clipboard), or keep the guide's FileSystem / Clipboard workaround only.
  - **Verify:** per the decision - Live, 622 characters into a Notepad test tab arrive exactly, clipboard restored.

# Part D - Guide corrections

- [x] D5-1 `SKILL.md` timings: "Scroll ~0.5 s" -> ~0.7 s (until R5-I1); "Click ~0.15 s" -> ~0.2 s; add "Click `element=` in a browser can take ~1.5 s the first time". Done in round-6 R6-12 with round-6 timings (Click ~0.16 s, Scroll ~0.2/~0.5 s, the 1.5 s traced to a new browser profile).
- [x] D5-2 Superseded by the R5-1 fix: `references/web.md` "What comes back" now says how tables come back instead; no known-gaps entry needed.
- [x] D5-3 `references/known-gaps.md` R4-16: give the working alternative - back up the clipboard, Clipboard `set` the text, click the document, Ctrl+V, restore the clipboard (exact in 0.1 s in round 5). Done in round-6 R6-12.
- [x] D5-4 Rebuild the Claude Desktop guide ZIP after D5-1 to D5-3. Done in round-6 R6-12 (`windows-mcp-skill-2026-09-29.zip`).

# Implementation verification

- Every item's Verify done live, checked a second way (harness text file, TextPattern, raw registry, Shell API), with times from the MCP log.
- `pytest`, `ruff check .` and `ruff format --check .` clean with zero warnings.
- Guide and tool descriptions updated with each fix (CLAUDE.md "Skills and Keeping Them Current"); `known-gaps.md` lines removed for fixed items.
