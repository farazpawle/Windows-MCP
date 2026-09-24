---
Title: Windows-MCP open issues backlog - round 4 (2026-09-24)
Description: Findings of the round-4 real-work scenario test (all 21 tools driven through the connected server after the round-3 backlog, timed per call from Claude Code's MCP log), turned into a task file. Part A Bugs - 1 High (multi-line Type sends one key every 0.04 s: 622 characters took 26 s), 5 Medium (App launch names an older window; Snapshot word boxes include trailing spaces so word labels miss; WaitFor text_exists misses text inside documents; dialogs drawn inside an app's window are not noted; caret start/end work per line), 9 Low. Part B 7 improvements (Process list speed and output size, Snapshot word noise, fixed costs, reply boilerplate, list order, resize hint). Part C 2 new abilities (whole-field caret, FindText per window). Part D 31 guide, tool-description and test-skill corrections. Evidence is in docs/testing/windows-mcp-tool-test-report.md (Round 4). Status 2026-09-24: R4-1 fixed (622 multi-line characters in 0.87 s) and R4-2 fixed (launch names the new window and its handle), with D.4/D.5/D.20; next in the user's fix order is Part D.
Total Tasks: 95
---
# Windows-MCP open issues - round 4

**Fix order (user, 2026-09-24):** R4-1 (multi-line Type), R4-2 (launch reply), then Part D (guide corrections); the rest after.

Evidence for every item: `docs/testing/windows-mcp-tool-test-report.md`, section "Round 4". Each item: finding, then single-action fix subtasks, then its own Verify line. "Unit" = test written first and seen failing; "Live" = `windows-mcp-live-test` harness (or a real app started by the test), checked a second way. Times are end to end from Claude Code's MCP log.

# Part A - Bugs

- [x] R4-1 **High - multi-line Type is typed one key at a time.** Text with `\n`, `\t`, `{` or `}` goes through `uia.SendKeys(..., interval=0.04)` (`desktop/service.py` ~1153-1160): 177 characters 7.5 s, 622 characters 26.2 s; single-line text 26-35 ms.
  - [x] a. Unit: a multi-line text is sent as Unicode runs with an Enter key between lines, not through `SendKeys`.
  - [x] b. Unit: a text containing `{` / `}` is typed literally through the Unicode path.
  - [x] c. Split the text on `\n` / `\t`, send each run with `SendUnicodeText` and press Enter / Tab between runs.
  - [x] d. Keep `\r\n` as one line break.
  - **Verify:** Live - Type of the 622-character report into the harness text box takes under 1 s and `<log>.text` matches exactly (line breaks, a tab and braces included).
  - Result 2026-09-24: 622 characters (9 lines, 9 tabs, braces) in 0.87 s end to end, text matched exactly; `tests/test_type_direct.py` 3 new tests; harness text box now `AcceptsTab`. The reply's read-back said 575 characters (typed before the box settled) - that is R4-7.

- [x] R4-2 **Medium - App `launch` names an older window.** `_wait_for_launched_window` (`desktop/service.py` ~815-839) takes the first visible window whose title contains the name: `launch name=Notepad` replied "\*report.txt - Notepad launched." while the new window was "Untitled - Notepad".
  - [x] a. Unit: a window that existed before the launch is not accepted when a new one appears.
  - [x] b. Record the visible window handles before launching.
  - [x] c. Accept only handles not in that set (keep the PID match for `launch_executable`).
  - [x] d. Reply "launched, window not detected yet" when only old windows match.
  - **Verify:** Live - with a Notepad window open, App `launch name=Notepad` names the new window's title and handle.
  - Result 2026-09-24: live PASS - with a Notepad window open, the reply was "Untitled - Notepad launched (handle 592836)." (the new window) in 2.72 s. Added: when no new window appears but an old window of the app comes to the front (Notepad opening a tab there), the reply names it as possibly reused. Replies now carry the handle. Found: Notepad restores the user's earlier tabs, so a test must never close its window (live-test skill updated).

- [ ] R4-3 **Medium - Snapshot word elements include trailing spaces.** Notepad's word boxes span the spaces after each word ("460" centre 337 vs drawn 317); a double-click on `label=` of "460" selected the gap.
  - [ ] a. [User] Choose (design choice): trim word boxes to their text, or leave word elements out (see R4-I3).
  - [ ] b. Unit: a word range with trailing spaces yields a centre on its text.
  - [ ] c. Apply the chosen change in the tree service.
  - **Verify:** Live - Click `label=` on a mid-line word in Notepad with `clicks=2` selects exactly that word (Ctrl+C, Clipboard get).

- [ ] R4-4 **Medium - WaitFor `text_exists` misses text inside a text box or document.** "North leads the week" (in the Notepad document value) timed out; "leads" matched.
  - [ ] a. Unit: `text_exists` matches a phrase inside an element's value (ValuePattern / TextPattern text).
  - [ ] b. Search element values as well as names.
  - [ ] c. Unit: the timeout error names the active window.
  - [ ] d. Add the active window to the `text_exists` timeout error.
  - **Verify:** Live - `text_exists text="North leads the week"` on a Notepad holding it returns in under 0.5 s; a missing phrase's error names the window.

- [ ] R4-5 **Medium - the new-window note misses dialogs drawn inside an app's window.** Notepad's "Do you want to save changes ...?" (a dialog inside the Notepad window) was not named by the next input reply; a separate WinForms message box was.
  - [ ] a. [User] Approve the shape (design choice): report a modal dialog element (UIA `IsDialog` / window-type child with `IsModal`) that appeared in the front window, in the same note.
  - [ ] b. Unit: a dialog element that appears inside the front window is named once in the next input reply.
  - [ ] c. Implement the chosen detection in `tools/_new_windows.py`.
  - **Verify:** Live - Ctrl+W on a modified Notepad tab, then any input call: the reply names the "save changes" dialog; the ~0.17 s click time holds.

- [ ] R4-6 **Medium - `caret_position` start/end act on the current line.** They press Home/End (`service.py` ~1140-1143); "start" put text at the start of the last line. The description says "'start' (beginning)".
  - [ ] a. Reword the Type description: start/end of the current line (Home/End).
  - [ ] b. Link the whole-field option to R4-N1.
  - **Verify:** Stdio handshake test green; description reads "current line".

- [ ] R4-7 **Low - read-backs taken before the app settles.** Type "now reads ... (213 characters)" while Notepad had 215; Scroll "now at 87.3%" / "83.8%" then "was 100%" / "was 62%".
  - [ ] a. Unit: the Scroll read-back waits until two readings ~50 ms apart agree (capped at ~0.3 s).
  - [ ] b. Apply the same settle to Type's field read-back.
  - **Verify:** Live - Scroll in Notepad: the reported "now" equals the next call's "was" three times out of three.

- [ ] R4-8 **Low - Click names the element under an in-window flyout.** Clicks on Notepad's "Replace all" / "Exit Find and Replace" were reported as `document "Text editor"`; Edge's sign-in notice button `in ""`.
  - [ ] a. Unit: with `element=`, the reply names the matched element, not the one read at the point.
  - [ ] b. Name the matched element for `element=` / `label=` clicks.
  - [ ] c. Fall back to the owner window's title when the element's window has no name.
  - **Verify:** Live - Click `element="button:Replace all"` in Notepad's panel replies `button "Replace all"`.

- [ ] R4-9 **Low - FindText joins lines across windows.** Full screen: ".venv North 460 units" (VS Code side bar + Notepad).
  - [ ] a. Unit: two OCR lines on one baseline with a gap wider than ~3 average character widths are not joined.
  - [ ] b. Limit the row join in `_rows` to nearby lines.
  - **Verify:** Live - full-screen FindText of a phrase in a table does not include text from the window beside it; "North 460 units" still found.

- [ ] R4-10 **Low - PowerShell timeout replies ~2.4 s late.** timeout=1 -> 3.45 s, timeout=2 -> 4.36 s.
  - [ ] a. Profile where the 2.4 s goes (kill, pipe drain, wait) before changing anything.
  - [ ] b. Unit: a timed-out command replies within timeout + 0.5 s.
  - [ ] c. Fix the measured cause.
  - **Verify:** Live - `timeout=2` with `Start-Sleep 8` replies in under 2.6 s with status -1.

- [ ] R4-11 **Low - a full Screenshot fell back to pillow after the PC sat idle.** First full capture after ~1.5 h idle: `Screenshot Backend: pillow` on one display; later ones dxcam.
  - [ ] a. Unit: a failed dxcam grab is retried once with a fresh capture object before falling back.
  - [ ] b. Say in the reply why pillow was used ("dxcam failed: ...").
  - **Verify:** Live - lock and unlock the screen, then a full Screenshot reports dxcam.

- [ ] R4-12 **Low - some maximized windows are listed with their outer frame.** FactsERP: `Maximized at (-8,-8) size 1936x1048`; others `(0,0) 1920x1032`.
  - [ ] a. Unit: a maximized window whose DWM frame equals its outer rect is reported clipped to its monitor's work area.
  - [ ] b. Clip maximized windows' rectangles to the work area in `format_list` and Snapshot's window list.
  - **Verify:** Live - App `list` shows FactsERP (read only, never touched) at (0,0) 1920x1032.

- [ ] R4-13 **Low - Snapshot lists elements hidden under an in-window panel.** Words under Notepad's open Find & Replace panel were listed.
  - [ ] a. Unit: an element whose centre hit-tests to another element of the same window that is not its ancestor or descendant is left out.
  - [ ] b. Apply the check to leaf elements only (cost).
  - **Verify:** Live - Snapshot with the Find panel open lists no word under the panel; Snapshot time stays under 0.35 s.

- [ ] R4-14 **Low - uv warning on every server start** ("The `extra-build-dependencies` option is experimental ...", from `[tool.uv.extra-build-dependencies]` in `pyproject.toml`).
  - [ ] a. Check whether `pyperclip` still needs setuptools at build time (`uv lock --offline`, fresh venv).
  - [ ] b. Remove the section if not needed, or pass the preview flag in the documented launch command.
  - **Verify:** A server start writes no warning to stderr (Claude Code MCP log).

- [ ] R4-15 **Low - cosmetic replies.**
  - [ ] a. Unit: `redact` keeps a closing quote after a hidden value.
  - [ ] b. Fix `redact`.
  - [ ] c. Unit: WaitFor writes window titles as plain text (no `​` escape).
  - [ ] d. Fix the WaitFor title output.
  - [ ] e. Unit: folder info says "1 file" and states that Contents counts the top level.
  - [ ] f. Fix the Contents wording.
  - **Verify:** Unit only.

# Part B - Improvements

- [ ] R4-I1 **Process list speed and CPU sort.** Memory 0.85-1.06 s, CPU 2.3-2.8 s with 622 processes; "System Idle Process" tops the CPU list.
  - [ ] a. [User] Decide (design choice): read memory from one system snapshot (`NtQuerySystemInformation`, declined in R3-I3 at 473 processes) or accept the cost.
  - [ ] b. Unit: `sort_by="cpu"` leaves out PID 0.
  - [ ] c. Leave out System Idle Process from the CPU list.
  - **Verify:** Timing pass - list by memory with 600+ processes; CPU list starts with a real process.

- [ ] R4-I2 **Process `details=true` output size.** A 5-row list was ~10,000 characters, mostly padding.
  - [ ] a. Unit: command lines longer than 200 characters are cut with "…" and the table is not padded to them.
  - [ ] b. Shorten command lines in the details view.
  - **Verify:** Live - `list details=true limit=5` stays under 2,000 characters.

- [ ] R4-I3 **Snapshot word elements.** A 20-line Notepad text is 134 `word` elements; the document already holds the text as its value.
  - [ ] a. [User] Decide together with R4-3a.
  - [ ] b. Implement the choice.
  - **Verify:** Live - the same Notepad Snapshot lists under 40 elements, or word centres are exact.

- [ ] R4-I4 **Fixed costs left.** Move drag 1.29 s, Click double 0.48 s, Notification 1.2 s.
  - [ ] a. Profile Move drag (one call) before changing anything.
  - [ ] b. Profile Click `clicks=2`.
  - [ ] c. Profile Notification.
  - **Verify:** Timing pass - drag under 0.6 s, double click under 0.3 s, each still acting correctly on the harness.

- [ ] R4-I5 **Screenshot reply boilerplate.** Empty "Active Desktop / All Desktops / Focused Window skipped / Opened Windows skipped" tables (~450 characters a reply).
  - [ ] a. Unit: a screenshot-only reply has no skipped-section tables.
  - [ ] b. Drop them (keep the one "UI Tree: Skipped" line).
  - **Verify:** Unit; Screenshot reply text under 400 characters.

- [ ] R4-I6 **App `list` order.** Not front-to-back, front window not marked.
  - [ ] a. Unit: `list` is in z-order and marks the front window.
  - [ ] b. Sort by z-order and add a marker.
  - **Verify:** Live - the switched-to window is first and marked.

- [ ] R4-I7 **Resize refusal hint.** "Restore it first (e.g. Shortcut win+down)".
  - [ ] a. Point the hint to App `mode="restore"`.
  - **Verify:** Unit - the refusal text names `mode="restore"`.

# Part C - New tools / abilities

- [ ] R4-N1 **Caret to the start/end of the whole field** in Type.
  - [ ] a. [User] Approve the shape (design choice): new `caret_position` values ("field_start" / "field_end", Ctrl+Home / Ctrl+End) or change "start"/"end".
  - [ ] b. Unit: the chosen value sends Ctrl+Home / Ctrl+End.
  - [ ] c. Implement it.
  - **Verify:** Live - text typed with the whole-field start lands before line 1 in a multi-line box.

- [ ] R4-N2 **FindText limited to one window.**
  - [ ] a. Unit: `window=` (name or handle) restricts the search to that window's rectangle and drops matches under other windows.
  - [ ] b. Implement `window=`.
  - **Verify:** Live - with Notepad and the chat both showing "North 460 units", `window=` Notepad finds one match.

# Part D - Guide, tool-description and test-skill corrections

Guide = `Skills/windows-mcp/`. Rebuild the Claude Desktop ZIP (round-3 D.2) after these.

- [ ] D.1 `references/web.md`: "To open a page, start `msedge.exe <url>` (full path: known-gaps.md). It opens a new tab" - outdated: bare `msedge.exe` works (App Paths, R3-I5), known-gaps has no Edge entry, and a throwaway `--user-data-dir` opens its own window. Rewrite.
- [ ] D.2 `references/web.md`: missing - a throwaway Edge profile signs itself into the Windows Microsoft account and shows a "now syncing" notice over the page; `use_dom` then returns the notice text (twice). Click "Got it" first.
- [ ] D.3 `references/input.md`: "`caret_position`: `start` or `end`." - unclear: start/end of the current line (Home/End).
- [x] D.4 (done with R4-1: the cost is gone; input.md now says line breaks/tabs are key presses and 622 characters take under 1 s) `references/input.md`: "Text is sent as keystrokes and never touches the clipboard (2,000 characters arrived intact)." - missing: multi-line text costs ~0.04 s a character (622 characters 26 s) until R4-1; write long documents with FileSystem.
- [x] D.5 (done with R4-1: SKILL.md gives the multi-line time) `SKILL.md`: "Type without `loc` well under 0.1 s for short text" - add "single-line" and the multi-line cost.
- [ ] D.6 `SKILL.md`: "Move ~0.1 s, Click ~0.15 s, Scroll ~0.3 s" - missing: double click ~0.5 s, Click `element=` ~0.3 s, Move drag ~1.3 s.
- [ ] D.7 `SKILL.md`: "Under 0.1 s: ... Snapshot of a region" - measured 0.18-0.32 s.
- [ ] D.8 `SKILL.md` "Process list ~0.6 s (~1.7 s sorted by CPU)" and `references/system-tools.md` "which takes ~1.7 s; memory and name sorts take ~0.6 s" - measured 0.85-1.06 s and 2.3-2.8 s with 622 processes; grows with the process count; the CPU list starts with System Idle Process.
- [ ] D.9 `references/observe.md`: "on timeout it is an error that names the window actually active." - not for `text_exists` (until R4-4).
- [ ] D.10 `references/observe.md`: "`text_exists` searches the active window, or the windows matching `window_name`, including plain labels" - missing: it matches one element's name, not a phrase inside a text box or document; use `screen_text` or a single word.
- [ ] D.11 `references/observe.md`: "`region` keeps only elements inside the rectangle and reads only windows visible in it" - add: the Opened Windows list also shows only those windows.
- [ ] D.12 `references/observe.md` Snapshot: missing - documents list one element per word, with boxes that include the spaces after the word; do not click a word label's centre (use FindText or `loc`).
- [ ] D.13 `references/observe.md` FindText: missing - a full-screen search can join text of neighbouring windows into one line; give a `region`.
- [ ] D.14 `references/observe.md`: "On one screen, full captures use the same method as `region` captures (header "Screenshot Backend: dxcam")" - once, after the PC sat idle, it was pillow: check the Backend line and capture again when a pop-up is expected.
- [ ] D.15 `references/system-tools.md`: "they follow the output under an `Errors and messages:` heading, with any warning, verbose and debug lines" - a `Write-Warning` line came back inline in the output; only the error was under the heading.
- [ ] D.16 `references/system-tools.md`: "On timeout it is a tool error ... and the command really is stopped." - add: the reply comes ~2.4 s after the timeout (until R4-10).
- [ ] D.17 `references/system-tools.md`: "`move` also renames and creates target folders." - `copy` creates target folders too.
- [ ] D.18 `references/system-tools.md`: "`list` shows ExpandString values already expanded" - `get` does too, and neither names the type; read the raw value with PowerShell.
- [ ] D.19 `references/system-tools.md` FileSystem `info`: "size, dates, counts" - "Contents" counts the top level only, while Size includes subfolders.
- [x] D.20 (done with R4-2: the guide now says the reply names the new window and handle) `references/apps-windows.md`: "The reply names the window found, with its real title ("Calculator launched.")." - it can name an older window whose title contains the name (R4-2); check App `list` for the new handle.
- [ ] D.21 `references/apps-windows.md` `list`: missing - lines are not in front-to-back order; a few apps' maximized windows show their outer frame (-8,-8).
- [ ] D.22 `references/input.md`: "Every input reply ... ends with `Note: a new window appeared: ...` when a window opened since the previous input action" - missing: a dialog drawn inside the app's own window (Notepad's "save changes?") is not reported; take a Screenshot after closing or saving.
- [ ] D.23 `references/known-gaps.md`: "Each entry names its backlog item (Plan/windows-mcp-open-issues-round3.md)" - point to this file.
- [ ] D.24 `references/known-gaps.md`: add R4-3 to R4-6 (R4-1, R4-2 fixed) with their workarounds; remove each when fixed.
- [ ] D.25 `SKILL.md` "Which tool for which job": add rows "Write a document or report -> FileSystem `write` (not typing)" and "Check text inside a document -> Ctrl+A, Ctrl+C then Clipboard `get`, or WaitFor `screen_text` (not `text_exists`)".
- [ ] D.26 Snapshot tool description (`tools/`): "Captures complete desktop state including: system language" (no language line is returned) and "Always call this first" (the guide says Screenshot first) - reword.
- [ ] D.27 WaitFor tool description (`tools/`): say `text_exists` matches element names (until R4-4).
- [ ] D.28 `.claude/skills/windows-mcp-tool-tester/SKILL.md`: "Modern Windows 11 Notepad's text editing area is **not** exposed as an interactive element" - outdated: it is `document "Text editor"` with a label, and its words are listed too.
- [ ] D.29 `.claude/skills/windows-mcp-tool-tester/SKILL.md`: "(Clipboard set, Type of 20+ characters, copy shortcuts)" and "App - Modes: launch, resize, switch." - Type never uses the clipboard; App has ten modes.
- [ ] D.30 `.claude/skills/windows-mcp-tool-tester/SKILL.md` Step 3 timing (PowerShell timestamps, ~3-5 s overhead): add the millisecond timings in Claude Code's MCP log (`%LOCALAPPDATA%\claude-cli-nodejs\Cache\<project>\mcp-logs-windows-mcp\*.jsonl`, "Calling MCP tool" to "Tool ... completed"; calls to the same tool in parallel cannot be paired).
- [ ] D.31 `.claude/skills/windows-mcp-live-test/SKILL.md`: "open with FileShare ReadWrite" for Avast's `detections.log` - failed ("being used by another process"); `ReadWrite, Delete` works. Also add the Edge auto sign-in notice to its Edge `--app` note.

# Implementation verification

- Each item ticked only when its subtasks are done and its Verify passed; one-line result under the item.
- Tests first (Rule 7); after each item `pytest -q`, `ruff check .`, `ruff format --check .` clean, with no warnings.
- Live checks use the `windows-mcp-live-test` harness or a real app the test started; never a tree read of a VS Code-family window.
- Guide entries (`Skills/windows-mcp/`, `references/known-gaps.md`) updated in the same change as each fix; the Claude Desktop ZIP rebuilt once Part D is done.
- A final round-5 scenario re-runs the steps that failed here (multi-line Type timing, launch reply, word labels, text_exists, in-window dialog note, caret) and times every call from the MCP log.
