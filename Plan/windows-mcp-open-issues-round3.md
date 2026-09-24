---
Title: Windows-MCP open issues backlog - round 3 (2026-09-24)
Description: Findings of the round-3 real-work scenario test (all 21 tools driven through the connected server at the PC, plus a per-tool timing pass), turned into a task file. Part A Bugs - 2 High (windows that cannot be maximized are missing from the window list; a full-screen capture misses some front windows such as Avast's alert), 2 Medium (false "covered"/"screen changed" refusals; screen_changed misses small changes), 5 Low. Part B Improvements (fixed 0.5 s pauses and other latency, encoded PowerShell command lines, App Paths lookup, OCR column gaps, process command lines, window positions in App list). Part C one new ability (pop-up detection, needs the user's design approval). Part D restructures the tool guide into a short main file plus references (next session), then the user installs it in Claude Desktop once it is verified. Details and evidence are in docs/testing/windows-mcp-tool-test-report.md (Round 3). Not fixed yet: the user makes the fix plan in a later session.
Total Tasks: 56
---
# Windows-MCP open issues - round 3

Evidence for every item: `docs/testing/windows-mcp-tool-test-report.md`, section "Round 3". Each item: finding, then single-action fix subtasks, then its own Verify line. "Unit" = test written first and seen failing; "Live" = `windows-mcp-live-test` harness, checked a second way.

# Part A - Bugs

- [x] R3-1 **High - windows that cannot be maximized are missing from the window list.** `Desktop.get_windows` (`desktop/service.py`) keeps only windows whose WindowPattern has CanMinimize and CanMaximize, so fixed-size dialogs, Avast's alert and an app showing a modal question vanish from App `list`, and `switch`/`close`/`resize` by name and Click `window=` say "not found".
  - [x] a. Unit: a fake fixed-size top-level window (CanMaximize False) appears in `get_windows`.
  - [x] b. Replace the CanMinimize-and-CanMaximize filter with a top-level-window test (visible, not a tool window, has a title or is the foreground window).
  - [x] c. Check the Snapshot "Opened Windows" list still leaves out helper windows.
  - **Verify:** Live - a WinForms FixedDialog form is listed by App `list`, closed by `close name=...`, and Click `element=... window=...` reaches it.
  - Result (2026-09-24): rule is WindowPattern present and (foreground, or titled and not WS_EX_TOOLWINDOW); `tests/test_get_windows_filter.py`. Live: old and new lists identical on the working desktop (no helpers added); a `fixed_dialog=True` harness window was listed, Click `element="button:Alpha" window=...` logged `click Alpha`, `close name=...` closed it.

- [x] R3-2 **High - a full-screen capture can miss a window that is in front.** `DxcamBackend.is_available` (`desktop/screenshot.py`) returns False without a region, so full captures use GDI (pillow), which missed Avast's alert.
  - [x] a. Unit: `auto` picks dxcam for a full capture of one display when dxcam is available.
  - [x] b. Let dxcam take a full-display capture (region None) on single-display setups, falling back to pillow as now.
  - [x] c. For several displays, capture each display with dxcam and stitch, or keep pillow and say so in the reply.
  - **Verify:** Live - a layered/DirectComposition test window (or an Avast alert) is in the full Screenshot image.
  - Result (2026-09-24): `_resolve_region(None)` resolves to the only output; several displays keep pillow (the reply's "Screenshot Backend" line already says which, and the guide warns). Live: full capture now reports dxcam, 1920x1080, ~4 ms vs pillow ~30 ms. A WinForms Opacity 0.97 (layered) window was in both images, so it does not reproduce the Avast miss; the Avast alert itself was shown by dxcam in round 3. Not re-proved against a real Avast alert.

- [x] R3-3 **Medium - false refusals from the "still at its spot" check.** `element_still_at` (`tree/utils.py`) walks up from `ControlFromPoint`; in an embedded web page it gets the page pane, and over Explorer's Address Bar it gets a path button drawn on top.
  - [x] a. Unit: an element whose point resolves to a sibling drawn over it, in the same window, is accepted.
  - [x] b. Accept when the top-level window at the point is the element's own window and `ControlFromPoint` returns an ancestor or a sibling inside the element's rectangle.
  - [x] c. Word the refusal by cause: "another window covers it" vs "the element moved".
  - **Verify:** Live - Click `element=` on a button in a WebView2/CEF test page and Type `label=` on Explorer's Address Bar both act.
  - Result (2026-09-24): (b) changed on live evidence. Accepting a sibling drawn over the centre let Type act, but the click hit the path button and the text went to the folder view. Now: a container of the element in its own window counts (`element_still_at`, `_around`); a part drawn over the centre makes `spot_on_element` try 24 points inside the element's box and act on the first that is the element (Explorer's edit answers only in its last ~6%). Refusals name the covering window or say it moved (`covering_window`). Live: Edge `--app` page, Click `element="button:Press me"` changed the page title (second try; Chromium exposes elements lazily); Explorer Type `label=` "Address Bar" typed at (961,264) and the edit read back the text. Not re-proved on Avast's own alert (not reproducible on demand); Edge may answer with the button itself, so the container rule is proved by unit test only.

- [ ] R3-4 **Medium - WaitFor `screen_changed` misses small real changes.** `MIN_CHANGED_PIXELS = 100` (`tools/_screen_wait.py`) is fixed; a clock digit in an 80x30 region stayed below it.
  - [ ] a. Unit: a 40-pixel change in an 80x30 region counts; a 40-pixel change on a full screen does not.
  - [ ] b. Scale the floor with the region area (e.g. the smaller of 100 and 1% of the pixels, minimum ~20).
  - **Verify:** Live - `screen_changed` on the taskbar clock returns at the next minute.

- [ ] R3-5 **Low - identical duplicates can't be picked** (Explorer menu "Copy as path" twice).
  - [ ] a. Unit: two same-name, same-type matches where one is covered or off-screen pick the visible one.
  - [ ] b. Prefer the match on top at its centre; refuse only when both are visible.
  - **Verify:** Live - Click `element="Copy as path"` in Explorer's context menu copies the paths.

- [ ] R3-6 **Low - "Also matched ..." after an exact title.**
  - [ ] a. Unit: an exact (case-ignored) title match gives no "Also matched" note.
  - [ ] b. Skip the note when the name equals the chosen window's title.
  - **Verify:** Unit only.

- [ ] R3-7 **Low - Notification reply doubles a full stop.**
  - [ ] a. Unit: a message ending in "." gives one full stop in the reply.
  - [ ] b. Strip a trailing "." before adding the reply's own.
  - **Verify:** Unit only.

- [ ] R3-8 **Low - FileSystem `info` on a folder shows the entry size (4 KB), not the contents.**
  - [ ] a. Unit: a folder with 407 bytes of files reports 407 bytes (or is labelled "entry size").
  - [ ] b. Sum the file sizes for a folder (cap the walk, say when capped).
  - **Verify:** Unit only.

- [ ] R3-9 **Low - Registry Binary shown two ways** (`get` hex, `list` `{1, 2, 255}`).
  - [ ] a. Unit: `list` shows a Binary value as hex like `get`.
  - [ ] b. Format Binary values as hex in `list`.
  - **Verify:** Unit only.

# Part B - Improvements

- [ ] R3-I1 **Fixed pauses.** Click 0.56 s and Move hover 0.52 s each carry a fixed 0.5 s wait; Scroll 1.1 s; MultiSelect ~0.8 s a click; MultiEdit ~2.3 s a field.
  - [ ] a. [User] Approve the approach (design choice): shorter fixed settle (e.g. 0.1 s) or no settle with WaitFor `screen_idle` recommended in the guide.
  - [ ] b. Apply it to Click, Move, Scroll, MultiSelect, MultiEdit.
  - **Verify:** Timing pass - each under 0.3 s; harness still logs every click and key.

- [ ] R3-I2 **Short Type slower than long** (10 chars 1.11 s, 60 chars 0.70 s).
  - [ ] a. Unit: plain text under 20 characters goes through the Unicode path.
  - [ ] b. Send all plain text through `SendUnicodeText`; keep SendKeys only for `\n`, `\t`, `{`, `}`.
  - **Verify:** Timing pass - Type 10 chars under 0.3 s; harness text exact.

- [ ] R3-I3 **Process list 1.6 s.**
  - [ ] a. Unit: `sort_by="memory"` makes no CPU sampling call.
  - [ ] b. Sample CPU only for `sort_by="cpu"`.
  - **Verify:** Timing pass - memory list under 0.3 s.

- [ ] R3-I4 **Encoded PowerShell command lines look like malware.**
  - [ ] a. Run scripts from a temp `.ps1` with `-File` instead of `-EncodedCommand`, deleting it afterwards.
  - **Verify:** Unit - the command line has no `-EncodedCommand`; suite green; OCR still works live.

- [ ] R3-I5 **`launch_executable` bare names miss App Paths** (msedge.exe).
  - [ ] a. Unit: a bare name found only under `HKLM/HKCU\...\App Paths` resolves.
  - [ ] b. Look up App Paths after PATH.
  - **Verify:** Live - `launch_executable executable="msedge.exe"` opens a tab.

- [ ] R3-I6 **FindText phrase across table columns.**
  - [ ] a. Unit: two OCR lines on one baseline match a phrase that spans them.
  - [ ] b. Join lines whose boxes share a baseline before matching.
  - **Verify:** Live - "North 460 units" found in a column-aligned Notepad text.

- [ ] R3-I7 **Right-click menu appears ~1 s after Click returns.**
  - [ ] a. Say in the Click description and guide to WaitFor before reading a menu (no code change), or wait for a menu after a right click.
  - **Verify:** Guide/description updated.

- [ ] R3-I8 **Snapshot tree lists empty `window ""` lines.**
  - [ ] a. Unit: a window with no name and no listed children is left out of the printed tree.
  - [ ] b. Skip such windows when printing.
  - **Verify:** Unit only.

- [ ] R3-I9 **FindText description says ~2.5 s full screen; measured 1.24 s.**
  - [ ] a. Update the FindText and WaitFor descriptions.
  - **Verify:** Stdio handshake test still green.

- [ ] R3-I10 **Process list cannot tell which program is behind a process.** Tracing the Avast alert needed a separate PowerShell `Win32_Process` query: the only clue was a hidden `powershell.exe` whose command line named another app's tray script.
  - [ ] a. Unit: `list` with a new `details=true` shows each process's command line (secrets hidden via `action_log.redact`) and start time.
  - [ ] b. Add the option to Process `list`.
  - **Verify:** Live - `list name=pwsh details=true` shows the command line of a known test process.

- [ ] R3-I11 **App `list` gives no window position.** Clicking the Avast alert safely needed its rectangle from a separate script; `list` shows handle, PID, state and title only.
  - [ ] a. Unit: each `list` line includes the window's position and size in caller coordinates.
  - [ ] b. Add it to `format_list`.
  - **Verify:** Live - the listed rectangle of a test window matches `GetWindowRect`.

# Part C - New tools / abilities

- [ ] R3-N1 **Pop-up detection.** Both surprises this round (Notepad's question, Avast's alert) were found by accident.
  - [ ] a. [User] Approve the shape (design choice): WaitFor `condition="new_window"`, or a line in every input reply when the foreground window changed to one the call did not target.
  - [ ] b. Implement the chosen shape.
  - **Verify:** Live - opening a dialog during a WaitFor/after a Click is reported.

# Part D - Tool guide restructure (user decision 2026-09-24: do it next session)

- [ ] D.1 **Split the tool guide into a short main file plus references.** Today it is one file of 127 lines / 34,000 characters, 18 lines over 600 characters (longest 2,074), mixing how-to, PyPI differences (65 mentions) and dated test evidence (32 dates). The user already moved it from `Skills/Skill.md` to `Skills/windows-mcp/Skill.md` (uncommitted at the end of the 2026-09-24 session).
  - [x] a. Commit the user's move to `Skills/windows-mcp/` on its own (`git mv` history kept).
  - [ ] b. Rename the main file to `SKILL.md` (the skill-folder convention), keeping its frontmatter `name`/`description`.
  - [ ] c. Write the main file: golden rules, which tool for which job, the UI workflow, and a one-line pointer to each reference.
  - [ ] d. Write `references/observe.md` (Screenshot, Snapshot, FindText, WaitFor, Wait, DisplayInventory).
  - [ ] e. Write `references/input.md` (Click, Type, MultiEdit, MultiSelect, Scroll, Move, Shortcut, coordinates, shrunk screenshots).
  - [ ] f. Write `references/apps-windows.md` (App modes).
  - [ ] g. Write `references/system-tools.md` (PowerShell, FileSystem, Registry, Process, Clipboard, Notification).
  - [ ] h. Write `references/web.md` (Scrape).
  - [ ] i. Write `references/pypi-differences.md` holding every "PyPI" note, taken out of the pages above.
  - [ ] j. Write `references/known-gaps.md` holding the round-3 warnings (R3-1, R3-2, R3-3, ...) with workarounds; each fix removes its entry.
  - [ ] k. Drop test dates and evidence from the guide (the test report keeps them); keep only facts an agent acts on.
  - [ ] l. Check nothing was lost: every fact in the old file maps to one line in the new files (a side-by-side checklist).
  - [ ] m. Update links to the old path in `CLAUDE.md`, `.claude/skills/windows-mcp-live-test/SKILL.md` and this file.
  - **Verify:** the checklist in (l) has no unmapped fact; the main file is short enough to read in one pass (target under 150 lines, no line over 300 characters); a fresh agent given only the main file finds the right reference for five sample tasks.
- [ ] D.2 **[User] Install the finished guide in Claude Desktop's skill folder** - only after D.1 is verified and the guide is judged 100% correct (user's condition, 2026-09-24). Needs the user: it is their Claude Desktop setup. The agent prepares the folder and says exactly what to copy where.

# Implementation verification

- Each item ticked only when its subtasks are done and its Verify passed; one-line result under the item.
- Tests first (Rule 7); after each item `pytest -q`, `ruff check .`, `ruff format --check .` clean.
- Live checks use the `windows-mcp-live-test` harness, never a tree read of a VS Code-family window.
- `Skills/Skill.md` warnings for R3-1, R3-2, R3-3 and the others removed in the same change as each fix.
