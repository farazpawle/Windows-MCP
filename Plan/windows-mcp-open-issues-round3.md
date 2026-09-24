---
Title: Windows-MCP open issues backlog - round 3 (2026-09-24)
Description: Findings of the round-3 real-work scenario test (all 21 tools driven through the connected server at the PC, plus a per-tool timing pass), turned into a task file. Part A Bugs - 2 High (windows that cannot be maximized are missing from the window list; a full-screen capture misses some front windows such as Avast's alert), 2 Medium (false "covered"/"screen changed" refusals; screen_changed misses small changes), 5 Low. Part B Improvements (fixed 0.5 s pauses and other latency, encoded PowerShell command lines, App Paths lookup, OCR column gaps, process command lines, window positions in App list). Part C one new ability (pop-up detection, needs the user's design approval). Part D restructures the tool guide into a short main file plus references (next session), then the user installs it in Claude Desktop once it is verified. Details and evidence are in docs/testing/windows-mcp-tool-test-report.md (Round 3). Status 2026-09-24 (end of day): Parts A, B and C done and proved (live where the item asks), plus bug R3-10 found and fixed on the way; the guide split (D.1) is done. Only D.2 remains, which needs the user (install the guide in Claude Desktop).
Total Tasks: 62
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

- [x] R3-4 **Medium - WaitFor `screen_changed` misses small real changes.** `MIN_CHANGED_PIXELS = 100` (`tools/_screen_wait.py`) is fixed; a clock digit in an 80x30 region stayed below it.
  - [x] a. Unit: a 40-pixel change in an 80x30 region counts; a 40-pixel change on a full screen does not.
  - [x] b. Scale the floor with the region area (e.g. the smaller of 100 and 1% of the pixels, minimum ~20).
  - **Verify:** Live - `screen_changed` on the taskbar clock returns at the next minute.
  - Result (2026-09-24): floor = max(20, min(100, 1% of the region's pixels)). Live: WaitFor `screen_changed` on an 80x30 region of the taskbar clock returned at 11:03:01 (started 11:03:00) with a 6x7 px change box, under the old 100-pixel floor.

- [x] R3-5 **Low - identical duplicates can't be picked** (Explorer menu "Copy as path" twice).
  - [x] a. Unit: two same-name, same-type matches where one is covered or off-screen pick the visible one.
  - [x] b. Prefer the match on top at its centre; refuse only when both are visible.
  - **Verify:** Live - Click `element="Copy as path"` in Explorer's context menu copies the paths.
  - Result (2026-09-24): measured live, the two "Copy as path" entries have the same box (851,538,1167,570), both on top, so "refuse when both visible" alone still refused. `pick_element` takes the one shown at its centre, or the first when all shown copies share one spot. Live: right-click on a test file, Click `element="Copy as path"` clicked it in "Pop-upHost" and the clipboard held the file's quoted path (clipboard was empty before, emptied after).

- [x] R3-6 **Low - "Also matched ..." after an exact title.**
  - [x] a. Unit: an exact (case-ignored) title match gives no "Also matched" note.
  - [x] b. Skip the note when the name equals the chosen window's title.
  - **Verify:** Unit only.
  - Result (2026-09-24): `_find_windows_by_name` returns only whole-title matches when there are any, so the exact window is picked even if listed after a partial one, and the note names only same-titled windows (still useful). `test_exact_title_wins_without_a_note`.

- [x] R3-7 **Low - Notification reply doubles a full stop.**
  - [x] a. Unit: a message ending in "." gives one full stop in the reply.
  - [x] b. Strip a trailing "." before adding the reply's own.
  - **Verify:** Unit only.
  - Result (2026-09-24): the reply adds its "." only when the message does not already end in ".", "!" or "?" (keeps "Wait..." intact, unlike stripping). `test_reply_ends_the_message_with_one_stop`.

- [x] R3-8 **Low - FileSystem `info` on a folder shows the entry size (4 KB), not the contents.**
  - [x] a. Unit: a folder with 407 bytes of files reports 407 bytes (or is labelled "entry size").
  - [x] b. Sum the file sizes for a folder (cap the walk, say when capped).
  - **Verify:** Unit only.
  - Result (2026-09-24): `_folder_size` sums every file (os.walk, links not followed, unreadable parts skipped) up to `MAX_SIZE_WALK` = 10,000 files; a "Size note" line says total or capped. Smoke: `src` 2.5 MB instantly; C:\Windows capped at 10,000 files in 1.4 s.

- [x] R3-9 **Low - Registry Binary shown two ways** (`get` hex, `list` `{1, 2, 255}`).
  - [x] a. Unit: `list` shows a Binary value as hex like `get`.
  - [x] b. Format Binary values as hex in `list`.
  - **Verify:** Unit only.
  - Result (2026-09-24): `get` and `list` share `_FORMAT_VALUE` (hex bytes, JSON string list); `list` drops Format-List for `name : value` lines. Smoke on a throwaway `HKCU:\Software\WMCP-Test\R39` (deleted after): Binary `01,02,ff` and MultiString `["a","b c"]` identical in both.

# Part B - Improvements

- [x] R3-I1 **Fixed pauses.** Click 0.56 s and Move hover 0.52 s each carry a fixed 0.5 s wait; Scroll 1.1 s; MultiSelect ~0.8 s a click; MultiEdit ~2.3 s a field.
  - [x] a. [User] Approve the approach (design choice): shorter fixed settle (e.g. 0.1 s) or no settle with WaitFor `screen_idle` recommended in the guide.
  - [x] b. Apply it to Click, Move, Scroll, MultiSelect, MultiEdit.
  - **Verify:** Timing pass - each under 0.3 s; harness still logs every click and key.
  - Result (2026-09-24): user chose a 0.1 s settle; `Desktop._SETTLE` replaces every 0.5 s wait in click, move, wheel, multi_select and type's click/clear (drag unchanged). `test_no_input_waits_more_than_100ms`. Live (two rounds, harness text box): Click 0.16 s, Move 0.11 s, Scroll 0.28 s, MultiSelect 0.36 s for 2 clicks, MultiEdit 0.68/1.18 s a field; 9/9 clicks, 2/2 wheels logged, text exact. MultiEdit misses 0.3 s: the rest is the short-text SendKeys path (R3-I2).

- [x] R3-I2 **Short Type slower than long** (10 chars 1.11 s, 60 chars 0.70 s).
  - [x] a. Unit: plain text under 20 characters goes through the Unicode path.
  - [x] b. Send all plain text through `SendUnicodeText`; keep SendKeys only for `\n`, `\t`, `{`, `}`.
  - **Verify:** Timing pass - Type 10 chars under 0.3 s; harness text exact.
  - Result (2026-09-24): `_LONG_TEXT_THRESHOLD` removed; `test_short_plain_text_is_typed_as_unicode`, and the section-6 test that pinned SendKeys (and would have typed for real) now mocks `SendUnicodeText`. Live: Type 10 chars 0.02-0.04 s; "abcdefghij", "a+b^c%~(x)" and "héllo 🌍 ok" each arrived exact.
  - [x] Follow-up (new finding): MultiEdit is still ~0.95 s a field with typing now instant. Not measured where; suspect the clear's UIA focus read (`_finish_clear`). Profile one field before changing anything.
  - Result (2026-09-24): profiled live: `_finish_clear` took 0.51 s only when Ctrl+A left text, all of it `ValuePattern.SetValue`'s default 0.5 s wait. Now `waitTime=0.05`; `test_clear_fallback_does_not_wait_half_a_second`. Live: 0.44-0.49 s a field (was 0.94), text exact; the rest is click 0.15 s, settle 0.1 s, Ctrl+A/Back ~0.17 s.

- [x] R3-I3 **Process list 1.6 s.**
  - [x] a. Unit: `sort_by="memory"` makes no CPU sampling call.
  - [x] b. Sample CPU only for `sort_by="cpu"`.
  - **Verify:** Timing pass - memory list under 0.3 s.
  - Result so far (2026-09-24): CPU sampled (and the CPU% column shown) only for `sort_by="cpu"`; `test_other_sorts_do_not_sample_cpu`. Real run: memory 0.60 s, name 0.60 s, cpu 1.77 s. Verify not met: profiling shows 0.58 s of the 0.60 s is psutil `memory_info` on the 161 of 473 processes it cannot open, where it falls back to a whole-system snapshot per process (312 openable ones take 0.004 s in total).
  - [x] c. [User] Decide (design choice): read every process's memory from one system snapshot (`NtQuerySystemInformation` via ctypes, ~30 lines) or accept ~0.6 s. User (2026-09-24): accept ~0.6 s; the 0.3 s target is dropped.

- [x] R3-I4 **Encoded PowerShell command lines look like malware.**
  - [x] a. Run scripts from a temp `.ps1` with `-File` instead of `-EncodedCommand`, deleting it afterwards. (Replaced by the stdin runner below.)
  - **Verify:** Unit - the command line has no `-EncodedCommand`; suite green; OCR still works live.
  - Attempt (2026-09-24), reverted, not committed: (a) rejected - `-File` fails under an AllSigned policy and exits 0 when the last command failed. Tried instead: fixed `-Command` `$s = [IO.StreamReader]::new([Console]::OpenStandardInput(), [Text.Encoding]::UTF8).ReadToEnd(); try { $b = [scriptblock]::Create($s) } catch { [Console]::Error.WriteLine($_.Exception.InnerException.Message); exit 1 }; . $b`, the script passed as `input=` bytes with `\nif (-not $?) { exit 1 }` appended. A side-by-side of 16 cases on pwsh and powershell 5.1 matched the encoded way in output and exit code (Unicode, failed last command, native exit 3, `exit 7`, throw, multi-line, syntax error); stderr became plain text instead of CLIXML. Suite green (1525) with 12 new tests; live PowerShell, Registry get/list, Notification and FindText (ran; title not found in the given region) worked. Stopped on App launch: one run raised COMError -2146233083 (UIA timeout in the post-launch window search, `service.py` ~798-806), one run said "Calculator launched", and several live-test runs printed nothing (output lost, not diagnosed) and left Calculator windows open. The user stopped the slow Calculator loop (2026-09-24).
  - [x] b. Before retrying: make the live-test script's output reliable (print with flush, run with `2>&1` into a file) and learn why runs printed nothing; then compare App launch old vs new 3 times each.
  - Result (2026-09-24, retry): a diagnostic run logging to a file (with a faulthandler stack dump at 40 s) finished in 18 s. App launch fails the same way on old and new code: COMError -2146233083 from `WalkControl` → `GetNextSiblingControl` in the post-launch window search, after ~15 s. That is not caused by this change and is now R3-10. The stdin runner is committed with `tests/test_powershell_stdin.py` (12 tests, real pwsh and powershell 5.1). OCR read "Ocr probe North 460 units" exactly from a drawn test image; PowerShell, Registry get/list and Notification worked live; Avast logged nothing during the runs.

- [x] R3-10 **Low - App `launch` reports an error although the app opened.** New finding 2026-09-24, on old and new code alike: launching Calculator (Start Menu app, no PID) takes ~15 s, then fails with COMError -2146233083 (UIA timeout) from the `RegexName` window search walking top-level windows (`WalkControl` → `GetNextSiblingControl`, `desktop/service.py` ~801-806). Calculator was open, so an agent that retries gets a second copy.
  - [x] a. Unit: a sibling walk that raises a UIA timeout on one window still finds the launched window, or reports "launched, window not detected yet" (never an error).
  - [x] b. Catch the timeout in the post-launch search and fall back to the "not detected yet" reply; consider a faster lookup (new top-level window from `get_windows` before/after).
  - **Verify:** Live - App `launch name=Calculator` replies success within ~5 s, measured with the file-logging diagnostic script.
  - Result (2026-09-24): the UIA search is gone. `_wait_for_launched_window` polls win32 `EnumWindows` every 0.2 s for up to `_LAUNCH_WAIT` = 10 s: a visible, titled window of the launched PID or with the app name in its title (case ignored, as the old regex). No window gives the "not detected yet" reply, never an error. `tests/test_app_launch_window_wait.py`; the section-5 test now checks the name passed to the wait. Live: "Calculator launched." in 2.3 s (was ~15 s and an error), closed after.

- [x] R3-I5 **`launch_executable` bare names miss App Paths** (msedge.exe).
  - [x] a. Unit: a bare name found only under `HKLM/HKCU\...\App Paths` resolves.
  - [x] b. Look up App Paths after PATH.
  - **Verify:** Live - `launch_executable executable="msedge.exe"` opens a tab.
  - Result (2026-09-24): `_from_app_paths` reads the default value of `App Paths\<name>.exe` (HKCU, then HKLM), strips quotes and expands variables; `.exe` is optional. Tests in `test_app_replies.py`. Against this PC's real registry: `msedge.exe` and `msedge` resolve to Edge's install path, `notepad.exe` still resolves through PATH. Live (2026-09-24, after the warnings work): App `launch_executable executable="msedge.exe"` with a throwaway `--user-data-dir` returned PID 3652 at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` in 0.75 s; that PID was among the 14 processes of the throwaway profile, all closed after (0 left), stderr empty.

- [x] R3-I6 **FindText phrase across table columns.**
  - [x] a. Unit: two OCR lines on one baseline match a phrase that spans them.
  - [x] b. Join lines whose boxes share a baseline before matching.
  - **Verify:** Live - "North 460 units" found in a column-aligned Notepad text.
  - Result (2026-09-24): `_rows` joins OCR lines whose vertical centres are within half a line height, words left to right. Found on the way: Windows OCR returned `TextAngle` 1.5 for level text drawn in columns and gave word boxes in that tilted frame (one row's words 18 px apart, click points off), so the script now prints the angle and `_turn_back` turns each box centre back about the image centre. Tests use the real engine numbers. Real OCR on a drawn table (Arial 30): rows "North 460 units" / "South 215 units", match centre x 402 = drawn 402; "units South" not found. Consolas 22: the engine misses the lone "460" (reading gap, noted in the guide). Live: harness text box with columns typed, FindText "North 460 units" found once at (286,240) on the first row, "units South" not found, stderr empty.

- [x] R3-I7 **Right-click menu appears ~1 s after Click returns.**
  - [x] a. Say in the Click description and guide to WaitFor before reading a menu (no code change), or wait for a menu after a right click.
  - **Verify:** Guide/description updated.
  - Result (2026-09-24): the Click description now says a context menu can appear up to ~1 s after the reply and to WaitFor `element_exists` or `screen_idle` first; `references/input.md` already said so.

- [x] R3-I8 **Snapshot tree lists empty `window ""` lines.**
  - [x] a. Unit: a window with no name and no listed children is left out of the printed tree.
  - [x] b. Skip such windows when printing.
  - **Verify:** Unit only.
  - Result (2026-09-24): `_prune_structural` also drops unnamed windows with no children (named empty windows and unnamed ones with content stay). `tests/test_semantic_prune.py`.

- [x] R3-I9 **FindText description says ~2.5 s full screen; measured 1.24 s.**
  - [x] a. Update the FindText and WaitFor descriptions.
  - **Verify:** Stdio handshake test still green.
  - Result (2026-09-24): re-measured on today's screen, full 1.53-1.74 s, 400x200 region 0.58-0.63 s (PowerShell start is the same ~0.21 s with the stdin runner and the old encoded way, so the change from 1.24 s is screen content). FindText and WaitFor descriptions, the OCR module docstring and the guide now say ~1.6 s / ~0.6 s. Suite green including the stdio handshake.

- [x] R3-I10 **Process list cannot tell which program is behind a process.** Tracing the Avast alert needed a separate PowerShell `Win32_Process` query: the only clue was a hidden `powershell.exe` whose command line named another app's tray script.
  - [x] a. Unit: `list` with a new `details=true` shows each process's command line (secrets hidden via `action_log.redact`) and start time.
  - [x] b. Add the option to Process `list`.
  - **Verify:** Live - `list name=pwsh details=true` shows the command line of a known test process.
  - Result (2026-09-24): `details=true` adds Started (local time) and Command line (`subprocess.list2cmdline`, then `redact`; `-` when access is denied); a plain list reads no command lines. Tests in `test_process_self_cpu.py`. Live: a hidden `pwsh -NoProfile -Command "Start-Sleep 30 # wmcp-r3i10 -Token fakesecret123"` was listed with its start time and command line, the token shown as [hidden]; stderr empty; the test process was killed after. Note: `redact` also eats a closing quote right after a hidden value (cosmetic).

- [x] R3-I11 **App `list` gives no window position.** Clicking the Avast alert safely needed its rectangle from a separate script; `list` shows handle, PID, state and title only.
  - [x] a. Unit: each `list` line includes the window's position and size in caller coordinates.
  - [x] b. Add it to `format_list`.
  - **Verify:** Live - the listed rectangle of a test window matches `GetWindowRect`.
  - Result (2026-09-24): lines end `at (left,top) size WxH`, the visible window in screen pixels (DWM extended frame, as Snapshot's window list). Live, the verify as written does not hold by design: GetWindowRect (300,250) 640x360 listed as (307,250) 626x353, the 7 px being Windows 11's invisible resize borders. That showed `resize` meant the outer rect (700x400 gave a visible 686x393; window_loc 400,300 put it at 407,300). User decision (2026-09-24): positions mean the visible window everywhere, so `resize_app` now adds the borders back before MoveWindow. Live after: size-only 700x400 gave visible (307,250) 700x400 twice with no drift, loc 400,300 size 500x300 gave exactly that. Tests in `test_app_window_modes.py` and `test_app_replies.py`.

# Part C - New tools / abilities

- [x] R3-N1 **Pop-up detection.** Both surprises this round (Notepad's question, Avast's alert) were found by accident.
  - [x] a. [User] Approve the shape (design choice): WaitFor `condition="new_window"`, or a line in every input reply when the foreground window changed to one the call did not target. User (2026-09-24): the automatic note in input replies.
  - [x] b. Implement the chosen shape.
  - **Verify:** Live - opening a dialog during a WaitFor/after a Click is reported.
  - Result (2026-09-24): `tools/_new_windows.py`, `@note_new_windows` inside `@with_analytics` on Click, Type, Scroll, Move, Shortcut, MultiSelect and MultiEdit. After each call it lists visible, titled, uncloaked, non-tool top-level windows (EnumWindows, ~1.3 ms) and names those not seen after the previous input call, so a pop-up that came up after a reply is named on the next one; each once. Tests in `test_new_windows_note.py`; `conftest.py` fixes the list for all other tests. Live: a window opened between two Clicks was named on the second reply with its handle, PID and program, and not again on the third; clicks still ~0.17 s. Limit: a window hidden and re-shown under the same handle is not "new".

# Part D - Tool guide restructure (user decision 2026-09-24: do it next session)

- [x] D.1 **Split the tool guide into a short main file plus references.** Today it is one file of 127 lines / 34,000 characters, 18 lines over 600 characters (longest 2,074), mixing how-to, PyPI differences (65 mentions) and dated test evidence (32 dates). The user already moved it from `Skills/Skill.md` to `Skills/windows-mcp/Skill.md` (uncommitted at the end of the 2026-09-24 session).
  - [x] a. Commit the user's move to `Skills/windows-mcp/` on its own (`git mv` history kept).
  - [x] b. Rename the main file to `SKILL.md` (the skill-folder convention), keeping its frontmatter `name`/`description`.
  - [x] c. Write the main file: golden rules, which tool for which job, the UI workflow, and a one-line pointer to each reference.
  - [x] d. Write `references/observe.md` (Screenshot, Snapshot, FindText, WaitFor, Wait, DisplayInventory).
  - [x] e. Write `references/input.md` (Click, Type, MultiEdit, MultiSelect, Scroll, Move, Shortcut, coordinates, shrunk screenshots).
  - [x] f. Write `references/apps-windows.md` (App modes).
  - [x] g. Write `references/system-tools.md` (PowerShell, FileSystem, Registry, Process, Clipboard, Notification).
  - [x] h. Write `references/web.md` (Scrape).
  - [x] i. Write `references/pypi-differences.md` holding every "PyPI" note, taken out of the pages above.
  - [x] j. Write `references/known-gaps.md` holding the round-3 warnings (R3-1, R3-2, R3-3, ...) with workarounds; each fix removes its entry.
  - [x] k. Drop test dates and evidence from the guide (the test report keeps them); keep only facts an agent acts on.
  - [x] l. Check nothing was lost: every fact in the old file maps to one line in the new files (a side-by-side checklist).
  - [x] m. Update links to the old path in `CLAUDE.md`, `.claude/skills/windows-mcp-live-test/SKILL.md` and this file.
  - **Verify:** the checklist in (l) has no unmapped fact; the main file is short enough to read in one pass (target under 150 lines, no line over 300 characters); a fresh agent given only the main file finds the right reference for five sample tasks.
  - Result (2026-09-24): main `SKILL.md` 103 lines, longest line 216 characters; 7 references (18-130 lines each). `Plan/windows-mcp-guide-split-checklist.md` maps every old fact, none unmapped; two facts corrected (screen_text speed, PowerShell AppID) and a few added. Known gaps kept: several-screen captures (R3-2), OCR columns, App Paths, process command lines, window positions, pop-ups, empty window lines. A fresh agent given only `SKILL.md` routed 5/5 sample tasks correctly; its one ambiguity (closing one of several same-named windows vs kill by PID) got a line in golden rule 3.
- [ ] D.2 **[User] Install the finished guide in Claude Desktop's skill folder** - only after D.1 is verified and the guide is judged 100% correct (user's condition, 2026-09-24). Needs the user: it is their Claude Desktop setup. The agent prepares the folder and says exactly what to copy where.

# Implementation verification

- Each item ticked only when its subtasks are done and its Verify passed; one-line result under the item.
- Tests first (Rule 7); after each item `pytest -q`, `ruff check .`, `ruff format --check .` clean.
- Live checks use the `windows-mcp-live-test` harness, never a tree read of a VS Code-family window.
- Tool-guide warnings (`Skills/windows-mcp/`, gaps in `references/known-gaps.md`) removed or updated in the same change as each fix.
