---
Title: Windows-MCP open issues backlog - round 4 (2026-09-24)
Description: Findings of the round-4 real-work scenario test (all 21 tools driven through the connected server after the round-3 backlog, timed per call from Claude Code's MCP log), turned into a task file. Part A Bugs - 1 High (multi-line Type sends one key every 0.04 s: 622 characters took 26 s), 5 Medium (App launch names an older window; Snapshot word boxes include trailing spaces so word labels miss; WaitFor text_exists misses text inside documents; dialogs drawn inside an app's window are not noted; caret start/end work per line), 9 Low. Part B 7 improvements (Process list speed and output size, Snapshot word noise, fixed costs, reply boilerplate, list order, resize hint). Part C 2 new abilities (whole-field caret, FindText per window). Part D 31 guide, tool-description and test-skill corrections. Evidence is in docs/testing/windows-mcp-tool-test-report.md (Round 4). Status 2026-09-24: R4-1 fixed (622 multi-line characters in 0.87 s), R4-2 fixed (launch names the new window and its handle), R4-3 fixed (word boxes end at the word) R4-4 fixed (text_exists finds a phrase in a document) R4-5 fixed (in-window dialogs of XAML apps are noted) R4-6 fixed (caret start/end described as current line) and R4-7 fixed (Type/Scroll read-backs wait for the app), with D.3/D.4/D.5/D.9/D.10/D.12/D.20/D.22/D.27; all of Part D done (2026-09-25); R4-8 fixed (element=/label= clicks name the element found; 2026-09-25), guide ZIP rebuilt after it; R4-9 fixed (FindText keeps side-by-side windows apart); R4-10 fixed (timeouts reply ~0.25 s after the limit); R4-11 fixed (fast capture retried after a lost duplication; fallback says why); R4-12 fixed (maximized windows listed as their work area); next the Low bugs R4-13 to R4-15 and Parts B and C.
Total Tasks: 103
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

- [x] R4-3 **Medium - Snapshot word elements include trailing spaces.** Notepad's word boxes span the spaces after each word ("460" centre 337 vs drawn 317); a double-click on `label=` of "460" selected the gap.
  - [x] a. [User] Choose (design choice): trim word boxes to their text, or leave word elements out (see R4-I3). User chose trim (2026-09-24).
  - [x] b. Unit: a word range with trailing spaces yields a centre on its text.
  - [x] c. Apply the chosen change in the tree service.
  - **Verify:** Live - Click `label=` on a mid-line word in Notepad with `clicks=2` selects exactly that word (Ctrl+C, Clipboard get).
  - Result 2026-09-24: fixed in `uia/controls.py` (`_trim_trailing_space`, used by word boxes and word attributes): the box is cut by the share of trailing spaces, no extra COM calls. Live on a throwaway WPF TextBox (the harness WinForms box lists no words; Notepad was avoided because it restores the user's tabs): "North    460      units", the "460" centre moved from 317 (the word's right edge) to 296; Click `label=` then Type "X" gave "North    4X60      units". Verified with a single click + typed X instead of Ctrl+C, so the clipboard was never touched.

- [x] R4-4 **Medium - WaitFor `text_exists` misses text inside a text box or document.** "North leads the week" (in the Notepad document value) timed out; "leads" matched.
  - [x] a. Unit: `text_exists` matches a phrase inside an element's value (ValuePattern / TextPattern text).
  - [x] b. Search element values as well as names.
  - [x] c. Unit: the timeout error names the active window.
  - [x] d. Add the active window to the `text_exists` timeout error.
  - **Verify:** Live - `text_exists text="North leads the week"` on a Notepad holding it returns in under 0.5 s; a missing phrase's error names the window.
  - Result 2026-09-24: root cause - with `window_name`, nodes were matched on name or value but only their names were compared again, so a phrase inside a document's value never matched (without `window_name` it already worked). Fixed in `tools/input.py`; the timeout error now ends "the active window was '...'". Live (throwaway WPF TextBox, read-only): `window_name` 0.40 s, no `window_name` 0.29 s, missing phrase error names the window. Test-window note: a WPF window whose only content is a TextBox reports the box's text as its UIA Name; wrap it in a Grid.

- [x] R4-5 **Medium - the new-window note misses dialogs drawn inside an app's window.** Notepad's "Do you want to save changes ...?" (a dialog inside the Notepad window) was not named by the next input reply; a separate WinForms message box was.
  - [x] a. [User] Approve the shape (design choice): report a modal dialog element (UIA `IsDialog` / window-type child with `IsModal`) that appeared in the front window, in the same note. User approved (2026-09-24), limited to XAML apps for speed.
  - [x] b. Unit: a dialog element that appears inside the front window is named once in the next input reply.
  - [x] c. Implement the chosen detection in `tools/_new_windows.py`.
  - **Verify:** Live - Ctrl+W on a modified Notepad tab, then any input call: the reply names the "save changes" dialog; the ~0.17 s click time holds.
  - Result 2026-09-24: findings - the question is a UIA element (Window type, class `Popup`, `IsDialog` and `WindowIsModal` true) inside Notepad's window; no window is created or changed (win32 cannot see it). A full-window `IsDialog` search took 20-30 ms in a fresh Notepad, ~100 ms in a Notepad with several tabs and 183 ms in an Excel sheet, so (user's choice) only windows with a XAML host child (`Microsoft.UI.Content.DesktopChildSiteBridge`, `Windows.UI.Core.CoreWindow`, `Windows.UI.Composition.DesktopWindowContentBridge`) are searched. Live: the Ctrl+W reply itself (0.09 s) ended `Note: a dialog is open: "Notepad" in "*x - Notepad": "Do you want to save changes to x.txt?".`; the following hovers (0.03 s) did not repeat it. Not covered: in-window dialogs of non-XAML apps (web pages, some WPF apps).

- [x] R4-6 **Medium - `caret_position` start/end act on the current line.** They press Home/End (`service.py` ~1140-1143); "start" put text at the start of the last line. The description says "'start' (beginning)".
  - [x] a. Reword the Type description: start/end of the current line (Home/End).
  - [x] b. Link the whole-field option to R4-N1.
  - **Verify:** Stdio handshake test green; description reads "current line".
  - Result 2026-09-24: Type description now reads "'start' or 'end' (start or end of the current line: Home/End) ...; for the start or end of a whole multi-line field, send Shortcut ctrl+home or ctrl+end first" (the workaround until R4-N1); stdio handshake test green; the in-process server lists the new text. input.md says the same (D.3).

- [x] R4-7 **Low - read-backs taken before the app settles.** Type "now reads ... (213 characters)" while Notepad had 215; Scroll "now at 87.3%" / "83.8%" then "was 100%" / "was 62%".
  - [x] a. Unit: the Scroll read-back waits until two readings ~50 ms apart agree (capped at ~0.3 s).
  - [x] b. Apply the same settle to Type's field read-back.
  - **Verify:** Live - Scroll in Notepad: the reported "now" equals the next call's "was" three times out of three.
  - Result 2026-09-25: `_settled` in `tools/input.py` reads again every 0.05 s until two readings agree (cap 0.3 s), for Type's field read-back and Scroll's position. Live: Type of the 622-character text reported 631 characters (the box stores 9 line breaks as CR LF), i.e. the whole text, where the old reply said 575; three Scrolls on the harness box (filled by WM_SETTEXT) reported 8.3/16.6/24.9%, each equal to the next call's "was" and to an independent reading 0.5 s later. Cost: Scroll 0.5-0.7 s (was ~0.3 s), Type +0.05 s; guide timings updated.

- [x] R4-8 **Low - Click names the element under an in-window flyout.** Clicks on Notepad's "Replace all" / "Exit Find and Replace" were reported as `document "Text editor"`; Edge's sign-in notice button `in ""`.
  - [x] a. Unit: with `element=`, the reply names the matched element, not the one read at the point.
  - [x] b. Name the matched element for `element=` / `label=` clicks.
  - [x] c. Fall back to the owner window's title when the element's window has no name.
  - **Verify:** Live - Click `element="button:Replace all"` in Notepad's panel replies `button "Replace all"`.
  - Result 2026-09-25: root cause - Notepad's Find panel does not answer UIA hit-tests, so the point read returned the document under it (the spot check passed through its container rule). `element=` and `label=` clicks now name the element they found (`name_element` in `tree/utils.py`; `Desktop.label_node` split out of the label lookup); `loc` clicks still read the point. A title-less pop-up is named after its root owner window (`GA_ROOTOWNER`). Live on a new Notepad window (test tab closed with Don't save): `clicked button "Replace all" in "*x - Notepad"` and `button "Exit Find and Replace"`. Owner fallback unit-tested only (no Edge notice at hand). 4 new unit tests; also fixed `test_focused_window_outside_region_is_still_named`, which read the real screen size and failed on a 1366x768 Remote Desktop session.

- [x] R4-9 **Low - FindText joins lines across windows.** Full screen: ".venv North 460 units" (VS Code side bar + Notepad).
  - [x] a. Unit: two OCR lines on one baseline in different windows are not joined (changed from "a gap wider than ~3 character widths": R3-I6's table columns are gaps that wide, so a gap limit would undo it).
  - [x] b. Join rows in `_rows` only within the window under each line (`top_level_window_at` at the line's first word).
  - **Verify:** Live - full-screen FindText of a phrase in a table does not include text from the window beside it; "North 460 units" still found.
  - Result 2026-09-25: two throwaway WPF windows on one row (".venv" | "North    460      units"), full-screen FindText: "North 460 units" found alone (row text "North 460 units"), ".venv North" not found. The same run on the old code read the row as "> references .venv d: North 460 units" (VS Code's side bar joined in) and found ".venv North". 3 new unit tests; guide: observe.md note reworded, known-gaps entry removed.

- [x] R4-10 **Low - PowerShell timeout replies ~2.4 s late.** timeout=1 -> 3.45 s, timeout=2 -> 4.36 s.
  - [x] a. Profile where the 2.4 s goes (kill, pipe drain, wait) before changing anything. Measured (debug log, pwsh and powershell alike): the CTRL_BREAK_EVENT never stopped the child, so the full 2.0 s grace period was spent every time, then taskkill ~0.2 s. The child has its own hidden console (CREATE_NO_WINDOW), which a console control event from the server cannot reach.
  - [x] b. Unit: a timed-out command replies within timeout + 0.5 s.
  - [x] c. Fix the measured cause: `run_with_graceful_timeout` kills the tree (taskkill /T /F) at once; `grace_period` now only bounds reading the killed process's last output. User approved after the CRITICAL blast-radius warning (every PowerShell-backed feature; timeout path only).
  - **Verify:** Live - `timeout=2` with `Start-Sleep 8` replies in under 2.6 s with status -1.
  - Result 2026-09-25: in-process server, PowerShell `Write-Output ...; Start-Sleep 8`: timeout=1 1.29 s, timeout=2 2.24 / 2.25 / 2.24 s, status -1, the output printed before the timeout kept, no process left running. Guide: system-tools.md timing, known-gaps entry removed.

- [x] R4-11 **Low - a full Screenshot fell back to pillow after the PC sat idle.** First full capture after ~1.5 h idle: `Screenshot Backend: pillow` on one display; later ones dxcam.
  - [x] a. Unit: a failed dxcam grab is retried once with a fresh capture object before falling back.
  - [x] b. Say in the reply why pillow was used ("dxcam failed: ...").
  - **Verify:** Live - lock and unlock the screen, then a full Screenshot reports dxcam.
  - Result 2026-09-25: cause (dxcam 0.3.0 source) - on a lost duplication (DXGI_ERROR_ACCESS_LOST, as after a lock or display power-off) dxcam rebuilds it but that grab returns its cached frame only for the same region, else None, and None sent the capture to pillow; a still screen with no new frame for a new region does the same. `_DxcamBackend.capture` now releases the camera and grabs once more with a new one (a new duplication's first grab is the current screen). The backend name carries each failure (`pillow (dxcam failed: ...)`), shown on the reply's Screenshot Backend line. Live on the real DXGI output, access loss reported once by the duplicator (dxcam's own ACCESS_LOST path): full capture stayed dxcam, 107 ms; the old code gave pillow in the same run. 2 new unit tests, 8 fallback tests now also check the reason. Guide: observe.md, known-gaps entry removed.
  - [ ] c. [User] Optional real lock/unlock check (needs the user: over Remote Desktop a lock ends the session view and only the user can sign back in): press Win+L, sign back in, then ask Claude for a full Screenshot; its Backend line should read dxcam.

- [x] R4-12 **Low - some maximized windows are listed with their outer frame.** FactsERP: `Maximized at (-8,-8) size 1936x1048`; others `(0,0) 1920x1032`.
  - [x] a. Unit: a maximized window whose DWM frame equals its outer rect is reported clipped to its monitor's work area.
  - [x] b. Clip maximized windows' rectangles to the work area in `format_list` and Snapshot's window list. Done once in `Desktop._window_box`, which both lists (and the active window) use.
  - **Verify:** Live - App `list` shows FactsERP (read only, never touched) at (0,0) 1920x1032.
  - Result 2026-09-25: live (in-process server, App `list`, read only) on a 1366x768 Remote Desktop screen: FactsERP `Maximized at (0,0) size 1366x720`, its DWM frame (the old value) (-8,-8) 1382x736; the five other maximized windows unchanged at (0,0) 1366x720. The clip uses the window's monitor work area (MonitorFromWindow + GetMonitorInfo). 2 new unit tests; guide: apps-windows.md, known-gaps entry removed.

- [ ] R4-13 **Low - Snapshot lists elements hidden under an in-window panel.** Words under Notepad's open Find & Replace panel were listed.
  - [ ] a. Unit: an element whose centre hit-tests to another element of the same window that is not its ancestor or descendant is left out.
  - [ ] b. Apply the check to leaf elements only (cost).
  - **Verify:** Live - Snapshot with the Find panel open lists no word under the panel; Snapshot time stays under 0.35 s.
  - Finding 2026-09-25 (probe, new Notepad window): a UIA hit test cannot do (a) - the panel does not answer ControlFromPoint (R4-8), and words have no UIA element. But the panel is its own child HWND: `Microsoft.UI.Content.DesktopChildSiteBridge` (275,179)-(943,295) > InputSiteWindowClass > Popup > LandmarkTarget > ScrollViewer > the buttons, layered over the document's `NotepadTextBox` child HWND (110,179)-(1108,673) (document `RichEditD2DPT`). So the check can be win32 `WindowFromPoint(word centre)`: keep the word only when the child window hit is the document's host window or inside it. No COM call, microseconds per word.

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

- [ ] R4-16 **High (new, 2026-09-25) - long multi-line Type into Windows 11 Notepad came out garbled.** Found while probing R4-13 over Remote Desktop: Type (no loc, focused document) of 15 lines x 75 characters (1,130 characters) left 830 characters: "Line 1 alpha bravo Charlie jjjjjjjj...juliet oooooooo..." (a letter repeated many times, text lost, "charlie" capitalised). R4-1's 622 characters were exact in the WinForms harness text box, never checked in Notepad.
  - [ ] a. Reproduce: the same text into the harness text box and into a new Notepad window, once each; note which garbles.
  - [ ] b. Find the cause from evidence (input timing per run, Notepad's own features such as autocorrect or spell check, the Remote Desktop session) before changing anything.
  - [ ] c. Unit test for the measured cause, then fix.
  - **Verify:** Live - the 1,130-character text typed into a new Notepad window reads back exactly (twice), and the 622-character harness case still takes under 1 s.
  - Findings 2026-09-25 (three live runs, new Notepad windows over Remote Desktop, each closed with Don't save; text read back through TextPattern):
    - Harness text box, 1,130 characters, current code (32-character Unicode bursts, 10 ms apart): exact in 0.82 s. Notepad, same: garbled at character 19-27 every time, also with 50 ms between bursts, 8-character bursts, and made-up words.
    - 2 lines into Notepad: old per-key SendKeys (10 ms a key) exact apart from Notepad's own autocorrect ("charlie" -> "Charlie"); Unicode one character per SendInput (10 ms) the same but 1 of 149 characters lost; bursts with no spaces kept line 1 and garbled right after the first Enter; bursts as today garbled right after "charlie ".
    - Word-by-word bursts with 5, 15 or 30 ms after each word and 30-50 ms after each line: all garbled right after "Charlie " (repeated "o", text lost or extra).
    - So: once Notepad has autocorrected a word or started a new line, any multi-character SendInput burst is garbled, whatever the pause before it; single characters survive. Cause inside Notepad not established. Autocorrect itself is Notepad's setting and changes words at any speed.
    - Run 4 (user chose option 1, confirmed before coding): one character per SendInput, full 1,130 characters: 10 ms a character 12.5 s, 15-24 characters wrong ("llliet lllo"); 15 ms 18 s, 2-3 characters lost ("iilo"), "juliet" also auto-capitalised. So pacing does not make Notepad exact; option 1 not built (it would slow every app 8-20x for no fix).
  - [ ] d. [User] Choose (design choice): (1) one character at a time everywhere, ~10 ms a character (622 characters ~6.5 s, was 0.87 s); (2) one at a time only in Notepad-like editors (focused element class `RichEditD2DPT`), fast bursts elsewhere; (3) keep as is, guide warns (done: known-gaps.md, input.md).

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
  - [x] a. [User] Decide together with R4-3a. Decided: keep word elements, trimmed (R4-3); only the size concern is left.
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

- [x] D.32 Rebuild the Claude Desktop skill ZIP: `windows-mcp-skill-2026-09-25.zip` (20.3 KB, the `Skills/windows-mcp` folder as `windows-mcp/...`) built in the user's Downloads folder on 2026-09-25; the older ZIP there was left as it was. Rebuilt in place after R4-8 (20.8 KB, same name, user's choice).
- [ ] D.33 [User] Upload the new ZIP in Claude Desktop (needs the user's Claude account): Customize > Skills > open the existing windows-mcp skill and replace it, or delete it and "+" > Create skill > Upload a skill > the ZIP; keep it toggled on.

- [x] D.1 (done: web.md opens pages with launch_executable msedge.exe (bare name), notes the throwaway-profile window) `references/web.md`: "To open a page, start `msedge.exe <url>` (full path: known-gaps.md). It opens a new tab" - outdated: bare `msedge.exe` works (App Paths, R3-I5), known-gaps has no Edge entry, and a throwaway `--user-data-dir` opens its own window. Rewrite.
- [x] D.2 (done: web.md and the live-test skill mention the sync notice and its Got it button) `references/web.md`: missing - a throwaway Edge profile signs itself into the Windows Microsoft account and shows a "now syncing" notice over the page; `use_dom` then returns the notice text (twice). Click "Got it" first.
- [x] D.3 (done with R4-6: input.md says current line and gives Ctrl+Home/Ctrl+End) `references/input.md`: "`caret_position`: `start` or `end`." - unclear: start/end of the current line (Home/End).
- [x] D.4 (done with R4-1: the cost is gone; input.md now says line breaks/tabs are key presses and 622 characters take under 1 s) `references/input.md`: "Text is sent as keystrokes and never touches the clipboard (2,000 characters arrived intact)." - missing: multi-line text costs ~0.04 s a character (622 characters 26 s) until R4-1; write long documents with FileSystem.
- [x] D.5 (done with R4-1: SKILL.md gives the multi-line time) `SKILL.md`: "Type without `loc` well under 0.1 s for short text" - add "single-line" and the multi-line cost.
- [x] D.6 (done: SKILL.md adds double click, Click element= and drag times) `SKILL.md`: "Move ~0.1 s, Click ~0.15 s, Scroll ~0.3 s" - missing: double click ~0.5 s, Click `element=` ~0.3 s, Move drag ~1.3 s.
- [x] D.7 (done: region Snapshot moved to ~0.2-0.3 s) `SKILL.md`: "Under 0.1 s: ... Snapshot of a region" - measured 0.18-0.32 s.
- [x] D.8 (done: SKILL.md and system-tools.md give the measured times and the System Idle Process line) `SKILL.md` "Process list ~0.6 s (~1.7 s sorted by CPU)" and `references/system-tools.md` "which takes ~1.7 s; memory and name sorts take ~0.6 s" - measured 0.85-1.06 s and 2.3-2.8 s with 622 processes; grows with the process count; the CPU list starts with System Idle Process.
- [x] D.9 (done with R4-4: observe.md says which conditions name the active window) `references/observe.md`: "on timeout it is an error that names the window actually active." - not for `text_exists` (until R4-4).
- [x] D.10 (done with R4-4: text_exists now matches a phrase in documents; observe.md says so) `references/observe.md`: "`text_exists` searches the active window, or the windows matching `window_name`, including plain labels" - missing: it matches one element's name, not a phrase inside a text box or document; use `screen_text` or a single word.
- [x] D.11 (done: observe.md says the window list is filtered too) `references/observe.md`: "`region` keeps only elements inside the rectangle and reads only windows visible in it" - add: the Opened Windows list also shows only those windows.
- [x] D.12 (done with R4-3: boxes now cover the word; observe.md says so) `references/observe.md` Snapshot: missing - documents list one element per word, with boxes that include the spaces after the word; do not click a word label's centre (use FindText or `loc`).
- [x] D.13 (done: observe.md FindText note, plus known-gaps R4-9) `references/observe.md` FindText: missing - a full-screen search can join text of neighbouring windows into one line; give a `region`.
- [x] D.14 (done: observe.md idle pillow note, plus known-gaps R4-11) `references/observe.md`: "On one screen, full captures use the same method as `region` captures (header "Screenshot Backend: dxcam")" - once, after the PC sat idle, it was pillow: check the Backend line and capture again when a pop-up is expected.
- [x] D.15 (done: system-tools.md says Write-Warning can come back inline) `references/system-tools.md`: "they follow the output under an `Errors and messages:` heading, with any warning, verbose and debug lines" - a `Write-Warning` line came back inline in the output; only the error was under the heading.
- [x] D.16 (done: system-tools.md and known-gaps R4-10) `references/system-tools.md`: "On timeout it is a tool error ... and the command really is stopped." - add: the reply comes ~2.4 s after the timeout (until R4-10).
- [x] D.17 (done: copy and move both create target folders) `references/system-tools.md`: "`move` also renames and creates target folders." - `copy` creates target folders too.
- [x] D.18 (done: get and list expanded, raw read and type via PowerShell (command checked)) `references/system-tools.md`: "`list` shows ExpandString values already expanded" - `get` does too, and neither names the type; read the raw value with PowerShell.
- [x] D.19 (done: Contents is top level only, Size includes subfolders) `references/system-tools.md` FileSystem `info`: "size, dates, counts" - "Contents" counts the top level only, while Size includes subfolders.
- [x] D.20 (done with R4-2: the guide now says the reply names the new window and handle) `references/apps-windows.md`: "The reply names the window found, with its real title ("Calculator launched.")." - it can name an older window whose title contains the name (R4-2); check App `list` for the new handle.
- [x] D.21 (done: apps-windows.md list order and outer-frame note, plus known-gaps R4-12) `references/apps-windows.md` `list`: missing - lines are not in front-to-back order; a few apps' maximized windows show their outer frame (-8,-8).
- [x] D.22 (done with R4-5: input.md now describes the in-window dialog note and what it misses) `references/input.md`: "Every input reply ... ends with `Note: a new window appeared: ...` when a window opened since the previous input action" - missing: a dialog drawn inside the app's own window (Notepad's "save changes?") is not reported; take a Screenshot after closing or saving.
- [x] D.23 (done: known-gaps.md points at round 4 and the completed round-3 file) `references/known-gaps.md`: "Each entry names its backlog item (Plan/windows-mcp-open-issues-round3.md)" - point to this file.
- [x] D.24 (done: known-gaps.md lists open R4-8 to R4-13 with workarounds (R4-14/R4-15 are not agent-facing)) `references/known-gaps.md`: add any still-open round-4 bug with its workaround (R4-1 to R4-6 are fixed, so none of those).
- [x] D.25 (done: two rows added to the tool table) `SKILL.md` "Which tool for which job": add rows "Write a document or report -> FileSystem `write` (not typing)" and "Check text inside a document -> Ctrl+A, Ctrl+C then Clipboard `get`, or WaitFor `text_exists`" (R4-4 fixed: `text_exists` finds a phrase in a document).
- [x] D.26 (done: Snapshot description no longer mentions system language or 'Always call this first') Snapshot tool description (`tools/`): "Captures complete desktop state including: system language" (no language line is returned) and "Always call this first" (the guide says Screenshot first) - reword.
- [x] D.27 (done with R4-4: the description says text_exists matches names and text inside text boxes and documents) WaitFor tool description (`tools/`): say `text_exists` matches element names (until R4-4).
- [x] D.28 (done: tester skill describes Notepad's document and word elements and the restored-tabs warning) `.claude/skills/windows-mcp-tool-tester/SKILL.md`: "Modern Windows 11 Notepad's text editing area is **not** exposed as an interactive element" - outdated: it is `document "Text editor"` with a label, and its words are listed too.
- [x] D.29 (done: tester skill: Type never uses the clipboard; App's ten modes) `.claude/skills/windows-mcp-tool-tester/SKILL.md`: "(Clipboard set, Type of 20+ characters, copy shortcuts)" and "App - Modes: launch, resize, switch." - Type never uses the clipboard; App has ten modes.
- [x] D.30 (done: tester skill gives the MCP log timing (path checked; lines read 'completed successfully in N ms')) `.claude/skills/windows-mcp-tool-tester/SKILL.md` Step 3 timing (PowerShell timestamps, ~3-5 s overhead): add the millisecond timings in Claude Code's MCP log (`%LOCALAPPDATA%\claude-cli-nodejs\Cache\<project>\mcp-logs-windows-mcp\*.jsonl`, "Calling MCP tool" to "Tool ... completed"; calls to the same tool in parallel cannot be paired).
- [x] D.31 (done: ReadWrite, Delete for the Avast log; Edge sync notice in the Edge --app note) `.claude/skills/windows-mcp-live-test/SKILL.md`: "open with FileShare ReadWrite" for Avast's `detections.log` - failed ("being used by another process"); `ReadWrite, Delete` works. Also add the Edge auto sign-in notice to its Edge `--app` note.

# Implementation verification

- Each item ticked only when its subtasks are done and its Verify passed; one-line result under the item.
- Tests first (Rule 7); after each item `pytest -q`, `ruff check .`, `ruff format --check .` clean, with no warnings.
- Live checks use the `windows-mcp-live-test` harness or a real app the test started; never a tree read of a VS Code-family window.
- Guide entries (`Skills/windows-mcp/`, `references/known-gaps.md`) updated in the same change as each fix; the Claude Desktop ZIP rebuilt once Part D is done.
- A final round-5 scenario re-runs the steps that failed here (multi-line Type timing, launch reply, word labels, text_exists, in-window dialog note, caret) and times every call from the MCP log.
