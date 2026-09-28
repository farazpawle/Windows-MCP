---
Title: Windows-MCP open issues - round 5
Description: Findings of the round-5 re-test (2026-09-26, all 21 tools through the connected server after the round-4 backlog, timed from Claude Code's MCP log), as a task file. Every round-4 fix held. Part A Bugs - 1 Medium (Scrape use_dom drops table text), 3 Low (Registry list stray carriage return; Snapshot lists Notepad's document twice and 100.1% scroll; FindText window= crop misses a phrase the full screen finds). Part B 4 improvements (Scroll 0.7 s, Click element= in Edge 1.5 s, App list front marker when a system panel is in front, a paste option for long text into Notepad). Part D 4 guide corrections. Evidence in docs/testing/windows-mcp-tool-test-report.md (Round 5). Not fixed yet: the user makes the fix plan.
Total Tasks: 25
---

# Windows-MCP open issues - round 5

Evidence for every item: `docs/testing/windows-mcp-tool-test-report.md`, section "Round 5". Each item: finding, then single-action fix subtasks, then its own Verify line. "Unit" = test written first and seen failing; "Live" = `windows-mcp-live-test` harness (or a real app started by the test), checked a second way. Times are end to end from Claude Code's MCP log.

Work order: these items are slotted into the round-6 order (`Plan/windows-mcp-round6-speed-accuracy-plan.md`, "Order"); R5-I1, R5-I2, R5-2 and D5-1 to D5-4 are done there as R6-5, R6-4, R6-6 and R6-12.

# Part A - Bugs

- [ ] R5-1 **Medium - Scrape `use_dom` leaves out table text.** A local page (heading, paragraph, 3-row table, button) returned only the heading and paragraph. WaitFor `text_exists use_dom=true` found the table's "405", so the text is in the tree; the "Informative Check" in `tree/service.py` (~1041-1079) keeps only `INFORMATIVE_CONTROL_TYPE_NAMES` and links, so table cells (and the button label) never reach `dom_informative_nodes`.
  - [ ] a. Find which UIA control types Edge gives the table cells' text (DataItem / Text inside a Table) on a throwaway page.
  - [ ] b. Unit: a table cell's text inside a browser document is added to `dom_informative_nodes`.
  - [ ] c. Add the cell text in the informative check.
  - [ ] d. Unit: the page text keeps table rows in order, one row per line.
  - **Verify:** Live - Scrape `use_dom=true` on a throwaway Edge page with a table returns every cell ("North 460", "South 405").

- [ ] R5-2 **Low - Registry `list` reply has a stray carriage return** after the last value ("Revenue : 5000000000\r\n\nSub-Keys").
  - [ ] a. Unit: the `list` reply holds no `\r`.
  - [ ] b. Strip the PowerShell output's line ends before building the reply.
  - **Verify:** Live - Registry `list` on a test key with 6 values: no `\r` in the reply.

- [ ] R5-3 **Low - Snapshot lists Notepad's document twice and a scroll of 100.1%.** One `document "Text editor"` entry has the value, a second at the same point has `[v:100.1%]`. With `use_vision=true` the value's bare `\r` line breaks run the lines together ("Week 39Region").
  - [ ] a. Unit: an element that is both informative and scrollable is listed once, with value and scroll position.
  - [ ] b. Merge the two entries.
  - [ ] c. Unit: a scroll percent above 100 is shown as 100.
  - [ ] d. Clamp the percent.
  - [ ] e. Unit: a value with `\r` line breaks is shown with `\n`.
  - [ ] f. Normalise the value's line breaks.
  - **Verify:** Live - Snapshot of a Notepad test tab scrolled to the end: one document entry, `v:100%`, value lines separate.

- [ ] R5-4 **Low - FindText `window=` misses a phrase the full screen finds.** The window crop (31,26)-(1031,628) makes OCR read "North 460 12.50" as "North 12.50", so "North 460" is not found; a region 5 px larger reads it. The same miss with `region` = the window rectangle, so the window filter is fine; the engine is sensitive to the crop.
  - [ ] a. Measure on a saved screenshot which padding (e.g. 8-16 px of margin, or 4x instead of 3x) reads the row every time.
  - [ ] b. Unit: `window=` reads a padded rectangle and still keeps only matches whose centre shows that window.
  - [ ] c. Pad the window crop.
  - **Verify:** Live - FindText `window=<test Notepad>` "North 460" finds the row the full-screen search finds.

# Part B - Improvements

- [ ] R5-I1 **Scroll takes 0.68-0.72 s** a call (round 4 0.27-0.56 s; guide ~0.5 s), apparently the settle wait added for R4-7.
  - [ ] a. Profile one Scroll in Notepad and in the harness (wheel, settle wait, read-back).
  - [ ] b. Shorten the settle wait where the position is already stable.
  - **Verify:** Live - three Scrolls in a Notepad test tab: each under 0.5 s, each "now" equal to the next "was".

- [x] R5-I2 **Click `element=` in Edge took 1.5 s** the first time (Notepad 0.27-0.30 s).
  - [x] a. Profile Click `element="button:Got it"` on a fresh throwaway Edge window.
  - **Verify:** Live - the profile names where the 1.5 s goes; fix only if one step dominates.
  - **Done 2026-09-28 in round-6 R6-4:** the time went to finding the window by name, slowed PC-wide while the throwaway Edge profile starts and syncs (with an everyday Edge, 0.06-0.08 s). No code change (user decision); see R6-4's findings.

- [ ] R5-I3 **App `list` shows no "(front)"** when the foreground is not a listed window (the taskbar's hidden-icons panel was open).
  - [ ] a. Unit: when the foreground is not listed, the header names what is in front.
  - [ ] b. Add that line.
  - **Verify:** Live - with the hidden-icons panel open, App `list` says what is in front.

- [ ] R5-I4 **Long text into Notepad is still unusable by typing** (361 of 622 characters, repeated letters; the reply warns). A clipboard paste of the same text was exact in 0.1 s.
  - [ ] a. [User] Decide (design choice): add a Type option that pastes (backing up and restoring the clipboard), or keep the guide's FileSystem / Clipboard workaround only.
  - **Verify:** per the decision - Live, 622 characters into a Notepad test tab arrive exactly, clipboard restored.

# Part D - Guide corrections

- [ ] D5-1 `SKILL.md` timings: "Scroll ~0.5 s" -> ~0.7 s (until R5-I1); "Click ~0.15 s" -> ~0.2 s; add "Click `element=` in a browser can take ~1.5 s the first time".
- [ ] D5-2 `references/web.md` "What comes back": say `use_dom` leaves out table text; read tables with WaitFor `text_exists use_dom=true` or FindText. Add the same to `known-gaps.md` as R5-1.
- [ ] D5-3 `references/known-gaps.md` R4-16: give the working alternative - back up the clipboard, Clipboard `set` the text, click the document, Ctrl+V, restore the clipboard (exact in 0.1 s in round 5).
- [ ] D5-4 Rebuild the Claude Desktop guide ZIP after D5-1 to D5-3.

# Implementation verification

- Every item's Verify done live, checked a second way (harness text file, TextPattern, raw registry, Shell API), with times from the MCP log.
- `pytest`, `ruff check .` and `ruff format --check .` clean with zero warnings.
- Guide and tool descriptions updated with each fix (CLAUDE.md "Skills and Keeping Them Current"); `known-gaps.md` lines removed for fixed items.
