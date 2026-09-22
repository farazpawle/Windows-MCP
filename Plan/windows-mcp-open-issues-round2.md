---
Title: Windows-MCP open issues backlog - round 2 (2026-09-22)
Description: Findings of the second round of live testing of all 20 windows-mcp tools on 2026-09-22, turned into a task file. Part A Bugs - 7 High (registry paths act as wildcards and reach the file system; WaitFor renumbers Snapshot labels; off-screen points are clamped and clicked; an on-top unfocused window gets no Snapshot elements; pop-up menus don't hide covered elements; region clipping moves a click point under a covering window), 16 Medium, 27 Low. Part B Improvements to reach Claude Cowork computer-use behaviour. Part C New tools/abilities (each needs the user's design approval first). Part D Skills/Skill.md corrections and one optional [User] high-DPI test. Every item keeps its finding, then lists single-action fix subtasks and its own Verify line; the file ends with the overall verification rules.
Total Tasks: 177
---
# Windows-MCP open issues - round 2

Source: live tests on 2026-09-22 (Windows 11 Pro 26200, one 1920x1080 display at 100%, Avast), driven from Claude Code against the local repo on branch `fix/open-issues-backlog`. Every result was checked a second way (WinForms harness event log and state file, a key-state poller using `GetAsyncKeyState`, a foreground-window logger, PowerShell file/registry/process reads, screenshots, and a separate FastMCP script client for empty inputs and error flags). Full results: `docs/testing/windows-mcp-tool-test-report.md` (round 2 section).

**Reference for "works like Claude Cowork":** Anthropic's computer-use toolset (`platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool`, read 2026-09-22): 17 actions - screenshot, zoom, left/right/middle/double/triple click with optional modifiers (`shift`, `ctrl`, `alt`, `super`), left_click_drag, mouse_move, left_mouse_down/up, cursor_position, scroll (with modifiers), type (at current focus), key (repeat 1-100), hold_key (up to 300 s), wait (up to 300 s). It requires: coordinates in the pixel space of the screenshot the model saw (the host scales), an error result for coordinates outside the display, and failures returned with `is_error: true`.

**No freeze or crash** happened this round. VS Code sat under every Snapshot region and was listed by name only.

## How to use this file

- Each numbered item is one finding: what was done, what happened, what should happen. Its box is ticked only when all its lettered subtasks are done **and** its **Verify** line passed.
- Lettered subtasks are single actions. Order inside an item is the order to do them.
- "Unit" in a Verify line = automated test written first and seen failing (Rule 7). "Live" = re-run against the real desktop and confirmed a second way (harness log/state, key-state poller, PowerShell read, screenshot).
- Items marked "Done together with X" share code with X; they are ticked when X is.
- `[User]` subtasks need the user (a design decision or something the agent can't do); the reason is on the same line.

# Part A - Bugs

## 1. High - can lose data or act on the wrong thing

- [X]  1.1 **Registry paths are treated as wildcard patterns.** Tool: Registry. Steps: create `HKCU:\Software\WMCP-Test\A1`, `\A2`, `\B1`, `\Br[ack]et`; call `delete` path `HKCU:\Software\WMCP-Test\A*` (no `recursive`), then again with `recursive=true`; call `list` on `...\B?`; call `set` on `...\Br[ack]et`. Actual: the first delete said "`A*` has 2 sub-key(s)" (it matched A1 and A2); with `recursive=true` it replied "Registry key [...\A*] deleted" and **both A1 and A2 were gone** (checked with `Get-ChildItem`). `list B?` showed B1 as a sub-key of `B?`. `set` on `Br[ack]et` failed with "A parameter cannot be found that matches parameter name 'Type'". Expected: the path is taken literally; `*`, `?`, `[ ]` are ordinary characters or refused. Why High: `HKCU:\Software\*` with `recursive=true` would wipe every application's settings.

  - [X]  a. `get_value`: pass the path with `-LiteralPath` to `Get-ItemProperty`.
  - [X]  b. `set_value`: use `-LiteralPath` in `Test-Path` and `Set-ItemProperty`; confirm `New-Item` treats the path literally (it has no `-LiteralPath`) and guard it if not. (The `Br[ack]et` "parameter 'Type'" error came from `Set-ItemProperty -Path` matching no key.)
  - [X]  c. `delete_entry`: use `-LiteralPath` in `Remove-ItemProperty`, `Get-ChildItem` and `Remove-Item`.
  - [X]  d. `list_key`: use `-LiteralPath` in `Get-ItemProperty` and `Get-ChildItem`.
  - [X]  e. `delete_entry`: refuse a path containing `*` or `?` before any PowerShell runs.

  - **Verify:** Unit - every registry command uses `-LiteralPath` and never `-Path` with the user's path; a delete with `*` or `?` returns an error and PowerShell is never called. Live (only inside `HKCU:\Software\WMCP-Test`) - recreate A1, A2, B1, `Br[ack]et`; `delete A*` with `recursive=true` is refused and `Get-ChildItem` still shows A1 and A2; `list B?` reports the key is missing (does not show B1); `set` on `Br[ack]et` succeeds and `Get-ItemProperty -LiteralPath` reads the value back.
  - **Result (2026-09-22):** done. 7 new unit tests failed first, then passed; full suite 799 passed; ruff clean on changed files (the repo's 60 older lint warnings are unchanged). Live, calling the fixed service against the real registry in `HKCU:\Software\WMCP-Test`: `delete A*` (plain and recursive) refused with A1/A2 still present; `list B?` = not found; `set`/`get`/`list`/delete value/delete key on `Br[ack]et` all worked; `New-Item` confirmed to treat brackets literally. Not yet re-run through the MCP tool itself - the running server loads the new code after its next restart.
- [X]  1.2 **The Registry tool works on file-system paths, including delete.** Tool: Registry. Steps: `list` with `path=""`; `delete` with `path=%TEMP%\wmcp-r2\fs\copy dir` and `recursive=true`. Actual: the empty path listed the server's working folder (the user's home: `.agents`, `.claude`, ...). The delete **removed the folder and its file** and replied "Registry key [C:\...\copy dir] deleted." (`Test-Path` = False). Expected: anything that is not a registry path is refused. Why High: a registry path typed without its hive (e.g. `Software\MyApp`) resolves relative to the home folder, and together with 1.1 a path like `C:\Users\*` would delete user files while reporting a registry change.

  - [X]  a. Write one path check: the path must start (case-insensitive) with `HKCU:`, `HKLM:`, `HKCR:`, `HKU:`, `HKCC:` or `Registry::`; empty or anything else is refused with a message listing the allowed starts. Note: only `HKCU:` and `HKLM:` exist as PowerShell drives by default, so `HKCR:`/`HKU:`/`HKCC:` must be rewritten to the `Registry::HKEY_...` form (or refused with that hint).
  - [X]  b. Call that check once in the Registry tool, before any mode (get/set/delete/list) runs.

  - **Verify:** Unit - `""`, `Software\MyApp`, `C:\Temp`, `%TEMP%\x`, `..\x` are refused without calling PowerShell; `hkcu:\Software`, `HKLM:\SOFTWARE`, `Registry::HKEY_CURRENT_USER\Software` are accepted; `HKCR:\...` works or gives the hint. Live - create `%TEMP%\wmcp-r2\fs\copy dir` with a file; `delete` it with `recursive=true` is refused and `Test-Path` is still True; `list` with `path=""` is refused.
  - **Result (2026-09-22):** done. Also accepts regedit-style names (`HKLM\X`, `HKEY_USERS\X`) by converting them to `Registry::HKEY_...` - without a colon PowerShell read them as folder paths (an existing test used `HKLM\X`). 6 new unit tests failed first, then passed; full suite 805 passed; changed files lint- and format-clean; repo lint warnings down from 60 to 54 (added `__all__` to the registry package). Live, through the real Registry tool in an in-process server: `delete` of `%TEMP%\wmcp-r2\fs\copy dir` with `recursive=true` refused and the folder and file still existed; `list` of `""` and `Software\MyApp` refused; `list HKCR:\.txt` and `HKEY_CURRENT_USER\...` worked; `delete A*` refused with A1/A2 still present; `HKCU\...\A1` and `HKCU:\...\A2` deleted exactly those keys.
- [X]  1.3 **Label ids are silently renumbered by WaitFor (and any other capture).** Tools: Snapshot, WaitFor, Click. Steps: Snapshot `region=[108,370,760,560]` on the harness - `[label:0]` = "ShowLater" button; call WaitFor (`element_exists` or `text_exists`, `window_name="WMCP Harness"`); call Click `label=0`. Actual: Click went to (1049,116), the window's **Close** button, and closed the harness (process gone). Reproduced safely with `clicks=0`: label 0 hovered (633,521) before the WaitFor and (1049,116) after it. Expected: a label keeps meaning what the last Snapshot showed, or the click is refused as stale.

  - [X]  a. Find every code path that replaces the stored label map (Snapshot, WaitFor, any internal capture).
  - [X]  b. Make only Snapshot write the label map; WaitFor and other internal captures use their own local tree. (A stale-label check at click time is part of B.9.)

  - **Verify:** Unit - after a WaitFor-style capture the stored label map is unchanged. Live - Snapshot `region=[108,370,760,560]`, then WaitFor on the harness, then Click `label=0` with `clicks=0`: the pointer lands on (633,521) (ShowLater), not (1049,116); the harness stays open.
  - **Result (2026-09-22):** done. The Desktop keeps a separate `label_tree_state` that only the Snapshot tool sets; label lookups (Click, Type, Scroll, Move, MultiSelect, MultiEdit) read it, so WaitFor, App, Scrape and Screenshot captures no longer renumber labels. Before any Snapshot, a label is refused with "call Snapshot first". 3 new unit tests failed first, then passed; one old test's setup updated; full suite 808 passed; lint unchanged at 54. Live (3 clean runs, in-process server with the fixed code, a scratch WinForms harness): Snapshot printed `[label:5] ShowLater`; label 5 hovered (468,401) before and after WaitFor; a real label click was logged by the harness as "click ShowLater" and the harness stayed open. Note: one earlier run with a broken test script (it misread the label from JSON-encoded text) ended with the harness closed; not reproduced in the 3 clean runs, cause not proven. Snapshot of an unfocused on-top harness returned no elements (bug 1.5), so the live script clicks the harness title bar first.
- [x]  1.4 **Off-screen coordinates are clamped to the screen edge and acted on; the reply names the original point.** Tools: Click, MultiEdit (likely Type, Move, Scroll too). Steps: Click `loc=[-50,99999]`, `modifiers="shift"`; MultiEdit `locs=[[253,391,"A..."],[99999,99999,"lost"],[253,461,"C-new"]]`. Actual: Click replied "Single left clicked at (-50,99999) holding shift" but the pointer was at (0,1079) and the click hit the taskbar corner. MultiEdit clicked (1919,1079) - the **show-desktop corner** - which minimised every window, typed "lost" onto the desktop, clicked the desktop at the third point and typed "C-new" there (desktop type-ahead selected the user's `Clear Ram.bat` icon; nothing was opened only because no Enter was sent). Field C stayed "oldC", yet the reply said all three were "Multi-edited". Expected: a point outside every display is refused before any input is sent.

  - [x]  a. Write one bounds check against the virtual-desktop bounds, reusing the check Screenshot `region` already does.
  - [x]  b. Call it in the shared input path for every `loc`, `locs` and `from_loc` (Click, Type, Scroll, Move, MultiSelect, MultiEdit).
  - [x]  c. MultiEdit and MultiSelect: check all targets before sending any input, and name each bad target in the refusal.
  - [x]  d. MultiEdit: if a field fails part-way, stop there and report which fields were done and which were not (instead of "Multi-edited" for all).

  - **Verify:** Unit - `[-50,99999]`, `[1920,0]`, `[0,1080]` refused with no input sent; `[0,0]` and `[1919,1079]` accepted; a mocked mid-run failure gives a done/not-done list. Live - Click `loc=[-50,99999]` refused and the cursor position (read with `GetCursorPos`) is unchanged; MultiEdit with the three targets above is refused, fields A and C keep their old text and no window is minimised (screenshot).
  - **Result (2026-09-22):** done. One check in the Desktop service (`_require_on_screen`) runs before Click (hover too), Type, Scroll, Move, Move `mouse_button`, drag (`loc` and `from_loc`), MultiSelect and MultiEdit send anything. It tests each display's own rectangle rather than the whole virtual-screen box, so a gap between two displays of different sizes is refused too (falls back to the virtual screen if monitors can't be listed). MultiSelect/MultiEdit check every target first and name each bad one ("target 2 (99999,99999) is outside every display"); MultiEdit stops at a failing field and lists done / not done. 35 new unit tests failed first (2 on-screen cases passed from the start), then passed; full suite 843 passed; lint unchanged at 54. Live (in-process server with the fixed code, scratch WinForms harness with three fields, checked with `GetCursorPos`, the harness state file and a list of minimised windows): Click `[-50,99999]` shift, `[1920,0]`, `[0,1080]` refused with the pointer unmoved; the three-target MultiEdit refused, fields stayed oldA/oldB/oldC, no window minimised; the same MultiEdit without the bad target set A-new and C-new. Note: a first live run launched the harness hidden, so its "valid targets" step clicked VS Code at (288,171)/(288,291) and sent Ctrl+A, Backspace and text there; nothing visible changed and the open plan file's text was unchanged (checked against git). The live script now refuses to type unless the harness is under the point.
- [x]  1.5 **Snapshot returns no elements for a visible always-on-top window that is not focused.** Tool: Snapshot. Steps: harness is TopMost at (100,100) but VS Code has focus; Snapshot `region=[108,100,1072,812]` (exactly the harness). Actual: "UI Tree: desktop" with nothing under it, "Focused Window: No active window found", and the 500-element truncation note. The cap was spent walking the maximised windows *behind* the harness (Settings, File Explorer, Edge, two Notepads), whose elements were then all dropped as hidden (fix 1.5 of round 1), leaving nothing. After clicking the harness title bar, the same Snapshot listed all 29 harness elements. Expected: the window that is actually visible in the region is read first.

  - [x]  a. Order windows by z-order (topmost first) instead of by focus before walking them.
  - [x]  b. Skip a window whose part inside the region is fully covered by windows above it, before walking it.
  - [x]  c. Count elements toward the 500 cap only after the hidden-element filter.

  - **Verify:** Unit - the ordering puts a topmost window before the focused one; a fully covered window is skipped. Live - harness TopMost, VS Code focused, Snapshot `region=[108,100,1072,812]` lists the 29 harness elements with no truncation note.
  - **Result (2026-09-22):** done. The tree walk now reads windows front to back (`z_order_rank` from `EnumWindows`); (the focused window's exemption from the hidden-element filter was removed later the same day - see Re-test). With a region, a window whose part in the region is covered at all 64 points of an 8x8 grid is skipped before its tree is read (`is_fully_covered`; a visible sliver thinner than 1/8 of that part can be missed - marked in the code). Elements dropped as hidden give their share of the 500 cap back. The test suite stubs the coverage check (conftest), since its made-up window handles would all read as covered on the real desktop. 5 new unit tests (3 failed first on behaviour, 2 helper checks); full suite 848 passed; lint unchanged at 54. Live (in-process server, scratch 3-button TopMost harness at (100,100)-(700,500), VS Code focused and confirmed with `GetForegroundWindow`, region `[108,100,692,492]`; this harness has 7 elements, not the 29 of the round-2 harness): fixed code listed all 7 in 0.17 s, no truncation note; the pre-fix code (a clean copy of the last commit) on the same setup gave 0 elements, the truncation note and 3.05 s - the original bug. Side note: in that pre-fix run Edge was in front, most likely because the user was working on the PC at the time.
  - **Re-test (2026-09-22, user hands-off):** same setup, focused window confirmed at capture time by the Snapshot header. Pre-fix code: VS Code focused - 0 harness elements, truncated, 15.0 s; Edge focused - 0 harness elements (only Edge's), truncated, 1.1 s. Fixed code: VS Code focused - 7 of 7, no note, 0.2 s; Edge focused - 7 of 7, no note, 0.6 s; harness itself focused - 7 of 7, 0.1 s. The Edge run also showed that the focused window was exempt from the hidden-element filter, so ~25 Edge items under the harness were listed. That exemption is removed (every window is now filtered, the focused one too; 1 more unit test, failed first; suite 848 passed), which brought it down to 13 - see 1.7 for the rest.
- [x]  1.6 **Elements covered by a pop-up (context) menu are still listed.** Tools: Snapshot, Click. Steps: right-click the harness text box (a context menu opens over the list box and scroll buttons); Snapshot `region=[400,150,800,450]`. Actual: the tree lists the menu ("window Context": Undo, Cut, Copy, Paste...) **and** the harness elements underneath it - e.g. `list item "Item1" (658,219)`, `button "Line up" (518,220)` - which sit under the menu's Cut/Copy entries (visible in the returned image). A label click on "Item1" would click a menu entry. Expected: elements under the menu are left out, as round-1 fix 1.5 does for normal windows.

  - [x]  a. Include pop-up menu windows (`#32768`, owned/topmost pop-ups) in the WindowFromPoint hit-test.

  - **Verify:** Live - with the context menu open, Snapshot `region=[400,150,800,450]` lists the menu entries but not "Item1" or "Line up"; after closing the menu (Escape) both are listed again.
  - **Result (2026-09-22):** done by the 1.5 change, no extra code. `WindowFromPoint` already returns the pop-up menu window (`#32768`), so the hit-test did see the menu; the gap was that the right-clicked window is the focused one, and the focused window was exempt from the hidden-element filter. 1.5 removed that exemption. Live (user hands-off; scratch TopMost harness with a text box and a 30-item list box; real right-click through the Click tool, menu window found at (208,161)-(480,445); Snapshot `region=[108,140,700,500]`): pre-fix code (clean copy of the last commit) listed Item1-Item18 under the menu as well as the menu entries; fixed code listed only the menu entries (Cut, Copy, Delete, ...) and the list box's scroll-bar parts at x=517, which lie right of the menu and are visible. After Escape (menu window gone), both versions listed Item1-Item18 again. Unit coverage: the 1.5 test that the focused window goes through the hidden-element filter.

- [x]  1.7 **Region Snapshot moves a partly covered element's click point onto the window covering it.** Found 2026-09-22 while re-testing 1.5. Tools: Snapshot, Click. Steps: Edge maximised and focused, the 3-button TopMost harness at (100,100)-(700,500) over it; Snapshot `region=[108,100,692,492]` (inside the harness). Actual: besides the 7 harness elements, 13 Edge elements are listed with label centres inside the harness (e.g. bookmarks, the chat list). Likely cause (from the code, not yet confirmed by printing the centres): the hidden-element check tests each element's real centre, which is visible outside the harness; the region filter (`_filter_tree_node_to_region` / `_filter_scroll_node_to_region`) then clips the box to the region and moves the centre into the clipped part, which the harness covers. A label click there would hit the harness. Same on the pre-fix code. Expected: an element whose in-region part is covered is left out, or keeps a click point that reaches it.
  - [x] a. Confirm the cause by printing the 13 elements' original and clipped centres.
  - [x] b. After clipping, hit-test the new centre against the element's own window and drop the element if another window is there.
  - **Verify:** Unit - a clipped element whose new centre is covered is dropped; an uncovered one is kept. Live - same setup: only the 7 harness elements are listed.
  - **Result (2026-09-22):** done. Cause confirmed live (user hands-off): all 13 had their real centre on Edge, just above or around the region, and a clipped centre on the harness - e.g. "Supersession Catalogs" (676,96) Edge -> (646,105) harness, "Google News" (215,96) -> (215,105), the WhatsApp pane (960,571) -> (400,303). Fix: when clipping to the region moves an element's centre, the element is kept only if the top-level window at the new centre is the same as at the original one (`_clip_moves_onto_other_window`, used for the interactive and scrollable lists and for interactive/scrollable nodes of the printed tree; window and structural nodes and the DOM node are not dropped this way). No window handle is needed: the hidden-element filter already proved the window at the original centre is the element's own. conftest stubs the lookup for tests with made-up coordinates. 3 new unit tests failed first, then passed; full suite 851 passed; lint unchanged at 54. Live, fixed code, same harness and region: Edge focused - 7 harness elements, 0 others, no note, 0.9 s; VS Code focused - 7/0, 0.3 s; harness focused - 7/0, 0.15 s. The "clipped point still on its own window is kept" case is covered by a unit test only.

## 2. Medium - wrong or misleading results

- [x]  2.1 **`modifiers="alt"` holds Ctrl+Alt.** Tools: Click, Scroll (Move drag likely too - same modifier code, not checked). Steps: Click `loc=ClickMe`, `modifiers="alt"` with a key-state poller running. Actual: harness logged `keydown ControlKey`, `keydown Menu`, `mousedown ... mods=Control, Alt`; the poller saw CTRL down 600 ms alongside ALT. Same on Scroll with alt (Ctrl and Alt key-ups logged). Expected: only Alt. Why it matters: Alt+click (column select, Explorer properties) becomes Ctrl+Alt+click, which is AltGr on many layouts.

  - [x]  a. Stop pressing Ctrl when Alt is a modifier.
  - [x]  b. Tap an unassigned key (VK 0xE8) just before releasing Alt, so the menu bar does not open (as AutoHotkey does).

  - **Verify:** Unit - the key sequence for `alt` contains no Ctrl and has the 0xE8 tap before Alt-up. Live - poller sees only ALT during Click and Scroll with alt; harness logs `mods=Alt`; in Notepad no menu bar is activated after the click.
  - **Result (2026-09-22):** done. Cause: nothing pressed Ctrl - `uia.core` sent every key with the ExtendedKey flag, so Alt went out as right Alt, which is AltGr on this PC's English (India) layout (00004009), and Windows adds a left Ctrl with AltGr. Fix: the `keybd_event` wrapper keeps ExtendedKey only for real extended keys (`_EXTENDED_VKS`: arrows, Home/End/PgUp/PgDn, Insert/Delete, Win, Apps, Break, PrintScreen, NumLock, numpad `/`, right Ctrl/Alt, media keys). Every key path goes through it (PressKey, ReleaseKey, SendKey, SendKeys), so Shortcut `alt+...` combinations are fixed too (same flag; not live-tested). `_keys_held` taps VK 0xE8 before releasing any Alt, which covers Click, Scroll, Move drag and Shortcut `hold`. 5 new unit tests failed first, then passed; full suite 859 passed; lint unchanged at 54. Live (user hands-off; fixed code called directly; scratch TopMost WinForms harness with a MenuStrip standing in for Notepad's menu bar; `GetAsyncKeyState` poller on L/R Ctrl and L/R Alt; WindowFromPoint guard): Click alt and Scroll alt - poller saw only LALT, harness logged `mousedown mods=Alt` / `wheel mods=Alt`, the 0xE8 tap, and no menu activation. Control: a bare Alt tap without the mask logged "menu activated", so the detector works. For 2.2: add `VK_LWIN`/`VK_RWIN` to `_ALT_KEYS`-style masking in `_keys_held`.
- [ ]  2.2 **`modifiers="win"` and Shortcut `hold` of `win` open the Start menu.** Tools: Click, Shortcut. Steps: Click `loc=[1000,700]`, `modifiers="win"`; separately Shortcut `win`, `hold=0.1`, then Shortcut `shift+/`. Actual: LWIN held correctly, then the Start menu opened (screenshot); after the hold, the next shortcut typed "?" into Start search, which ran a Bing web search. Expected: no Start menu when Win is only used as a held modifier.

  - [ ]  a. Tap VK 0xE8 before releasing Win in the modifier-release code (Click/Scroll/Move).
  - [ ]  b. Do the same in Shortcut `hold` when Win is held.

  - **Verify:** Unit - the release sequence for `win` has the 0xE8 tap. Live - after Click `modifiers="win"` and after Shortcut `win hold=0.1`, a screenshot shows no Start menu, and a following `shift+/` types nothing into Start search.
- [ ]  2.3 **Snapshot `use_dom=true` lists page elements that another window covers.** Tools: Snapshot, Click. Steps: Edge maximised with example.com; the TopMost harness covers (426,347); Snapshot `use_dom=true` lists `[label:1] (426,347) link "Learn more"`; Click `label=1`. Actual: the click hit the harness, not the link (WaitFor then reported the harness active). Expected: covered DOM elements left out, as in the normal tree.

  - [ ]  a. Apply the same WindowFromPoint hit-test to DOM-mode elements.

  - **Verify:** Live - harness covering "Learn more": Snapshot `use_dom=true` does not list it; harness moved away: it is listed again and a label click opens the link.
- [ ]  2.4 **Move `mouse_button` does not track the button state.** Tools: Move, Click. Steps: (a) `mouse_button="up"` with nothing held; (b) `mouse_button="down"` twice; (c) leave the button down, then Click ClickMe. Actual: (a) sends a stray button-up and replies "Released the left mouse button"; (b) accepted, second press sent; (c) the Click's press and release went to the drag pad that had captured the mouse, ClickMe never got a click (harness log), and Click replied "Single left clicked". Expected: (a) and (b) refused or reported as no-ops; (c) Click refuses, or releases the held button first and says so.

  - [ ]  a. Remember which mouse button is held in the desktop service.
  - [ ]  b. `up` with nothing held: send nothing and reply that no button was held.
  - [ ]  c. Refuse a second `down` while a button is held.
  - [ ]  d. Make other mouse actions (Click, Scroll, drag) release a held button first and say so in the reply.

  - **Verify:** Unit - state transitions for down/up/down-down/up-without-down. Live - harness log shows no stray mouse-up for (a), one mouse-down for (b), and for (c) a mouse-up to the drag pad followed by a real click on ClickMe, with the reply mentioning the release.
- [ ]  2.5 **Right and middle double/triple clicks are not real multi-clicks.** Tool: Click. Steps: `button="right"`, `clicks=2`; `button="middle"`, `clicks=2`. Actual: the two presses were 550 ms apart; Windows' double-click time here is 500 ms, so apps received two single clicks (WinForms `clicks=1` twice), while the reply said "Double right clicked". Left multi-clicks are 300 ms apart and work.

  - [ ]  a. Use the left-button spacing (well under `GetDoubleClickTime()`) for every button.

  - **Verify:** Live - harness logs `clicks=2` for right and middle double clicks and `clicks=3` for triple.
- [ ]  2.6 **Shortcut `repeat` is slow: about 0.52 s per press.** Tool: Shortcut. Steps: `left`, `repeat=20` (10 s); `shift+left`, `repeat=100` (~55 s). Every modifier click also keeps the keys down ~0.5 s after the mouse is released. Actual: counts are right when the window keeps focus (20 of 20), but a 100-press call blocks almost a minute. In the `repeat=100` run only 79 presses reached the harness: focus moved to VS Code for 7.6 s mid-run (about 14 presses went there); the other ~7 are unexplained. Expected: tens of milliseconds per press.

  - [ ]  a. Drop the per-action pause inside the repeat loop, keeping a 10-30 ms gap.
  - [ ]  b. Release modifiers straight after the mouse-up in modifier clicks (same change as B.14).

  - **Verify:** Unit - the repeat loop sleeps no more than 30 ms per press. Live - `left repeat=20` finishes in under 1 s with 20 of 20 presses logged; `shift+left repeat=100` logs 100 of 100 while the harness keeps focus; the poller sees Shift released within 100 ms of mouse-up on a modifier click.
- [ ]  2.7 **The orange capture border can leak into the next screenshot.** Tool: Screenshot. Steps: several region screenshots of the same area in quick succession. Actual: one capture showed the full orange glow from the previous capture; another had faint orange edges. Expected: never.

  - [ ]  a. Exclude the overlay window from capture with `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`, or wait until it is gone before the next capture.

  - **Verify:** Live - 10 region screenshots of the same area back to back; none contains the orange border (check the edge pixels of each image).
- [ ]  2.8 **App `switch` uses the window list from the last capture.** Tool: App. Steps: start a new harness window; App `switch` `name="WMCP Harness"`. Actual: "Application Wmcp Harness not found."; after one Snapshot the same call worked. Expected: a window opened since the last capture is found.

  - [ ]  a. Refresh the window list inside `switch`.
  - [ ]  b. Refresh the window list inside `resize` when a `name` is given.

  - **Verify:** Live - start a new harness, with no Snapshot call `switch name="WMCP Harness"` succeeds and the foreground-window logger shows it; same for `resize` with the name.
- [ ]  2.9 **FileSystem `read` refuses files over 10 MB even with `offset`/`limit`, and its message points to a tool that doesn't exist.** Steps: 11.5 MB log, `read` with `offset=1`, `limit=2`. Actual: "Error: File too large (11,500,000 bytes)... Use offset/limit parameters or the Shell tool". Expected: offset/limit read the requested lines.

  - [ ]  a. When `offset` or `limit` is given, stream the lines instead of checking the whole file size.
  - [ ]  b. Name the PowerShell tool (not "Shell") in the too-large message.

  - **Verify:** Unit - a >10 MB temp file with `offset=1, limit=2` returns exactly two lines; without them the refusal mentions PowerShell. Live - the 11.5 MB log in `%TEMP%` reads lines 1-2.
- [ ]  2.10 **No size cap on large replies.** Tools: PowerShell, FileSystem read, Process list. Steps: PowerShell `'a' * 300000`; FileSystem `read` of one 10,000-character line; Process `list` with `limit=-5` and `limit=0`. Actual: 300,043 characters returned (Claude Code had to spill it to a file); the whole 10,000-character line; all 424 processes for `-5`, and "No processes found." for `0`. Expected: a cap with a "truncated, N more" note; a limit below 1 refused.

  - [ ]  a. Write one shared cap helper (e.g. 50,000 characters) that adds "truncated - N more characters".
  - [ ]  b. Apply it to PowerShell output.
  - [ ]  c. Apply it to FileSystem `read`.
  - [ ]  d. Apply it to Process `list`.
  - [ ]  e. Refuse Process `list` `limit` below 1.

  - **Verify:** Unit - the helper keeps short text unchanged and cuts long text with the right N; `limit=0` and `-5` refused. Live - PowerShell `'a' * 300000` returns about 50,000 characters plus the note.
- [ ]  2.11 **Click `label=-1` clicks the last element.** Tool: Click. Steps: Snapshot, then Click `label=-1`. Actual: clicked ClickMe (the last label), reply "Single left clicked at (203,171)". Expected: refused. (Cause: Python negative indexing.)

  - [ ]  a. Reject labels below 0 before looking them up.

  - **Verify:** Unit - `label=-1` raises an error and sends no input. Live - Click `label=-1` refused; harness logs no click.
- [ ]  2.12 **Wait has no upper limit.** Tool: Wait. Steps: code reading only (not run, it would block the session): `_as_seconds` in `tools/input.py` has no maximum for `duration`. `Wait(1e9)` would block a server worker for ~31 years; a typo like `600` for `6.00` blocks 10 minutes.

  - [ ]  a. Cap `duration` at 300 s with a clear error, as `hold` does.

  - **Verify:** Unit - `301` and `1e9` refused; `300` and `0.5` accepted (the sleep is mocked, not run).
- [ ]  2.13 **Most tool failures are returned as successful results.** Tools: FileSystem, Registry, Process, App, PowerShell, Clipboard, Notification, Screenshot. Steps: a FastMCP script client called 13 failing operations (missing file, missing registry key, kill PID 4, unknown window/app, `exit 3`, PowerShell timeout, Clipboard set without text, bad app_id, display index 7, Click label 9999) and read `is_error`. Actual: 12 of 13 had `is_error=False` with the failure only in the text ("Error: File not found", "Status Code: 3", "Command execution timed out"); only Click raised a real error. Expected (and required by the computer-use reference): failures flagged `is_error: true`, so the client and the model can't mistake them for success.

  - [ ]  a. FileSystem: raise a tool error on failure.
  - [ ]  b. Registry: raise a tool error on failure.
  - [ ]  c. Process: raise a tool error on failure.
  - [ ]  d. App: raise a tool error on failure.
  - [ ]  e. PowerShell: raise a tool error on a non-zero exit code and on a timeout (keeping the output in the message).
  - [ ]  f. Clipboard: raise a tool error on failure.
  - [ ]  g. Notification: raise a tool error on failure.
  - [ ]  h. Screenshot: raise a tool error on failure (e.g. bad display index).

  - **Verify:** Unit - one failing case per tool asserts an error is raised. Live - re-run the 13-call FastMCP script client (with `SSLKEYLOGFILE` unset): all 13 return `is_error=True`, and the same calls' success cases still return `is_error=False`.
- [ ]  2.14 **Type with 20+ characters wipes non-text clipboard content.** Tool: Type. Steps: put an image on the clipboard; Type a 46-character text into a field. Actual: the text arrived, but afterwards the clipboard was **empty** (`ContainsImage()` False, no text). The guide promises the clipboard is restored; that only holds for text. Expected: the clipboard is left exactly as it was (an image, files, rich text).

  - [ ]  a. [User] Choose the approach (design choice): type with `SendInput` Unicode events and never touch the clipboard (B.7, recommended), or keep pasting but save/restore every clipboard format (via the `OleGetClipboard` data object).
  - [ ]  b. Implement the chosen approach.

  - **Verify:** Live - back up the user's clipboard first; put an image on the clipboard, Type 46 characters into a harness field: the text arrives and `ContainsImage()` is still True; repeat with a file list on the clipboard; restore the user's clipboard.
- [ ]  2.15 **The plus key can't be pressed by its name.** Tool: Shortcut. Steps: `+`, `ctrl++`, `ctrl+plus`. Actual: 'Unknown key name "}{"' (garbled) and 'Unknown key name "plus"'. `ctrl+=` and `ctrl+add` work, but nothing documents that. `{` alone gives '"{" or "{}" is not valid, use "{{}" for "{"...' (internal SendKeys syntax leaking out). Expected: `ctrl++` / `ctrl+plus` press Ctrl+Plus (zoom in - a very common shortcut).

  - [ ]  a. Treat a trailing `+` (as in `ctrl++` or `+`) as the plus key.
  - [ ]  b. Add the key names `plus`, `minus`, `equal`, `braceleft`, `braceright` (and similar punctuation names).
  - [ ]  c. Escape literal characters before handing them to SendKeys.

  - **Verify:** Unit - `ctrl++`, `ctrl+plus`, `+`, `{`, `}` all map to valid key sequences. Live - `ctrl+plus` in the harness logs Ctrl + Oemplus; `{` types `{` into a text field.
- [ ]  2.16 **Scrape is blocked by sites that refuse the default Python identity.** Tool: Scrape. Steps: `https://en.wikipedia.org/wiki/Windows_11`. Actual: "403 Client Error: Forbidden". The same URL returns 200 from PowerShell's Invoke-WebRequest, and 403 again when PowerShell sends `python-requests/2.32.3` as its User-Agent. Expected: common public pages load.

  - [ ]  a. Send a descriptive User-Agent (e.g. `windows-mcp/<version> (+repo URL)`), as Wikimedia's policy asks.

  - **Verify:** Unit - the request carries the new User-Agent. Live - Scrape of the Wikipedia URL returns page text.

## 3. Low - replies and usability

- [ ]  3.1 **Click `clicks=0` (hover) ignores `modifiers` but says it held them.** Reply "Hover left clicked at (204,171) holding win"; the poller saw no key down.

  - [ ]  a. Refuse `modifiers` together with `clicks=0` (simpler than the other option, pressing the keys during the hover).
  - [ ]  b. Word hover replies as "Moved to (x,y) (hover)".

  - **Verify:** Unit - hover + modifiers refused; hover reply wording. Live - poller sees no key down and the reply is refused.
- [ ]  3.2 **Scroll `wheel_times` 0 or negative is accepted.** `-3` replied "Scrolled vertical down by -3 wheel times" and nothing moved.

  - [ ]  a. Require `wheel_times` of 1 or more.

  - **Verify:** Unit - `0` and `-3` refused.
- [ ]  3.3 **Type without a location reports success when the focus can't take text.** Focus on a button; Type "abc" replied "Typed abc into the focused element."; nothing changed.

  - [ ]  a. Name the focused element and its type in the reply.
  - [ ]  b. Warn when the focused element has no ValuePattern/TextPattern.

  - **Verify:** Live - focus a harness button, Type "abc": the reply names the button and warns it can't take text.
- [ ]  3.4 **Shortcut error wording.** `hold=0` says "must be more than 0" while other hold errors say "must be 0 or more"; `shortcut=""` gives '"{" or "{}" is not valid...'; unknown keys give two different messages ('Unknown key name "x"' vs "Unknown key 'x'").

  - [ ]  a. Make the `hold` limit messages consistent.
  - [ ]  b. Reply "shortcut is empty" for an empty shortcut.
  - [ ]  c. Use one message for unknown keys.

  - **Verify:** Unit - each case returns the expected message.
- [ ]  3.5 **`modifiers` parsing.** `"ctrl, shift"` (comma list) is refused; `"control"` is accepted but not documented; the error repeats the whole input instead of the bad part.

  - [ ]  a. Accept commas and spaces as separators.
  - [ ]  b. List the accepted aliases (e.g. `control`) in the parameter description.
  - [ ]  c. Name only the bad token in the error.

  - **Verify:** Unit - `"ctrl, shift"` parses to ctrl+shift; `"ctrl+bogus"` error names `bogus`.
- [ ]  3.6 **FileSystem replies.** "Appended to ... (12 bytes)" gives the whole file size, not the bytes added; `write` to `trailingdot.` saves `trailingdot` but the reply keeps the dot; `write` onto a folder says "Permission denied ... may require an elevated (Administrator) terminal"; `offset=-1`, `limit=0` are silently ignored; `append=true` with `overwrite=true` silently appends (the two conflict); an empty `path` resolves to the Desktop folder and the error suggests "Set overwrite=True to replace it".

  - [ ]  a. Report the bytes added on append.
  - [ ]  b. Report the real saved file name.
  - [ ]  c. Say "is a folder" when writing onto a folder.
  - [ ]  d. Refuse `offset` below 1 and `limit` below 1.
  - [ ]  e. Refuse `append=true` together with `overwrite=true`.
  - [ ]  f. Refuse an empty `path`.

  - **Verify:** Unit - one test per case, run in a temp folder.
- [ ]  3.7 **Registry replies.** DWord with `value=""` is stored as 0 but the reply says set to ""; `get` of a Binary value returns decimal bytes one per line (`222\r\n173...`) instead of the hex format `set` accepts; a `0x` prefix is refused; MultiString can hold only one item (already in the guide).

  - [ ]  a. Refuse an empty value for DWord/QWord.
  - [ ]  b. Return Binary values from `get` as hex (the format `set` accepts).
  - [ ]  c. Accept a `0x` prefix for DWord/QWord.
  - [ ]  d. Accept a JSON list for MultiString.

  - **Verify:** Unit - each case. Live (in `HKCU:\Software\WMCP-Test`) - set then get a Binary, a `0x10` DWord and a two-item MultiString; values match `Get-ItemProperty`.
- [ ]  3.8 **Process `kill` with both `pid` and `name` silently uses the pid.**

  - [ ]  a. Refuse `pid` and `name` together.

  - **Verify:** Unit - the combination is refused and nothing is killed.
- [ ]  3.9 **App validation and replies.** `resize` accepted `window_size=[0,-5]` and replied "resized to 0x-5" (window became 122x32, its minimum) and accepted a fully off-screen `window_loc=[-3000,200]` without warning; a one-number `window_size` raises "not enough values to unpack"; replies re-capitalise window names ("Wmcp Harness", "Example Domain And 6 More Pages"); `switch` with a vague name ("h") picks one of many matches without saying so; `switch name=""` switched to an arbitrary window; `launch name=""` replies " not found in start menu."; `resize` of a maximised window replies "Calculator is maximized" as if it were a status, not a refusal; `launch_executable` does not search PATH (`notepad.exe` was looked up in the repo folder); the PID it returns can be a stub that hands off to an existing process (Notepad) and exits.

  - [ ]  a. Refuse `window_size` unless it is two positive numbers.
  - [ ]  b. Refuse a `window_loc` that puts the window fully off every display.
  - [ ]  c. Echo the real window title (no re-capitalising).
  - [ ]  d. In `switch`, list the other matches when the name matches several windows.
  - [ ]  e. Refuse an empty name in `switch`.
  - [ ]  f. Refuse an empty name in `launch`.
  - [ ]  g. Word the maximised-window `resize` reply as a refusal.
  - [ ]  h. Resolve bare `launch_executable` names with `shutil.which`.
  - [ ]  i. Note the PID hand-off (stub launchers) in `Skills/Skill.md`.

  - **Verify:** Unit - a, b, e, f, h. Live - resize the harness with `[0,-5]` refused; `switch name="h"` lists other matches; `launch_executable notepad.exe` starts Notepad.
- [ ]  3.10 **Screenshot/Snapshot header details.** "Cursor Position: None" when the pointer is outside the region; grid values 0 or negative are silently ignored and 5,000 lines turn the image solid grey; "Opened Windows" shows sizes clipped to the region (maximised windows as 500x40) and other captures show outer sizes where the visible frame is 14 px smaller; "Focused Window: No active window found" when the active window is a VS Code window that is only skipped; the 500-cap note appears even when every visible element in the region was listed.

  - [ ]  a. Print "outside region" instead of "None" for the cursor.
  - [ ]  b. Refuse grid values of 0 or less.
  - [ ]  c. Cap the number of grid lines.
  - [ ]  d. Show consistent window sizes (visible frame, not clipped to the region) in "Opened Windows".
  - [ ]  e. Name the skipped VS Code window as the focused window.
  - [ ]  f. Show the 500-cap note only when elements were actually dropped.

  - **Verify:** Unit - a, b, c, f. Live - region Screenshot with the pointer outside shows "outside region"; Snapshot with VS Code focused names it.
- [ ]  3.11 **PowerShell output details.** On timeout the output printed before it ("start") is lost; a warning runs straight into the next error with no line break ("WARNING: warn-streamException: boom"); `Write-Verbose -Verbose` output is dropped; an empty command runs and returns "Response: ".

  - [ ]  a. Keep the partial output on timeout.
  - [ ]  b. Join output streams with newlines.
  - [ ]  c. Include the verbose stream.
  - [ ]  d. Refuse an empty command.

  - **Verify:** Live - `'start'; Start-Sleep 10` with `timeout=2` returns "start" plus the timeout note; warning + error appear on separate lines; `Write-Verbose -Verbose x` returns x; `""` refused.
- [ ]  3.12 **Scrape `use_dom=true` drops link text.** example.com read through the DOM lacks "Learn more", which the HTTP read includes.

  - [ ]  a. Include link text in DOM extraction.

  - **Verify:** Live - Scrape example.com with `use_dom=true` contains "Learn more".
- [ ]  3.13 **Type's reply echoes the whole text but not what else it did** (1,097 characters came back; `clear=true` and `press_enter=true` are never mentioned).

  - [ ]  a. Echo the length and the first ~50 characters instead of the whole text.
  - [ ]  b. Add "cleared first" / "pressed Enter" when those options were used.

  - **Verify:** Unit - reply for a 1,097-character text with clear and Enter.
- [ ]  3.14 **Notification with an empty `app_id`** replies "Windows reports the setting ''".

  - [ ]  a. Refuse an empty `app_id` with "app_id is required".

  - **Verify:** Unit - empty `app_id` refused.
- [ ]  3.15 **WaitFor finds elements in an off-screen window** (harness moved to x=-3000) with no hint they can't be clicked.

  - [ ]  a. Add "(window is off-screen)" to the reply when the match is outside every display.

  - **Verify:** Live - harness at x=-3000, WaitFor on one of its elements shows the hint.
- [ ]  3.16 **Skills/Skill.md starts with a blank line before its `---` frontmatter.** Skill loaders expect the frontmatter on line 1, so the guide may not load as a skill.

  - [ ]  a. Delete line 1 of `Skills/Skill.md`.

  - **Verify:** Line 1 of the file is `---`.
- [ ]  3.17 **Scrape ignores `query` silently when summarising isn't available.** `query="which domains are reserved"` returned the whole raw page; the note mentions only the missing summary. Links stay relative (`/domains`).

  - [ ]  a. Say "query ignored" in the note (the keyword filter is B.12).
  - [ ]  b. Make links absolute.

  - **Verify:** Unit - relative links become absolute. Live - Scrape example.com with a query shows the note.
- [ ]  3.18 **Screenshot `region` details.** Text form `"100,100,300,200"` (allowed by the schema) fails with "Extra data: line 1 column 4 (char 3)"; `[0,0,1921,1080]` (1 px past the screen) is accepted although the description promises an error, and prints "image pixels are downscaled; multiply by 1.000521"; `use_annotation=true` is silently ignored on Screenshot.

  - [ ]  a. Parse comma-separated text for `region`.
  - [ ]  b. Refuse a region that goes past the display.
  - [ ]  c. Refuse `use_annotation` on Screenshot.

  - **Verify:** Unit - each case.
- [ ]  3.19 **Snapshot with `use_ui_tree=false` and `use_vision=false` returns nothing useful** ("UI Tree: No elements", no image) and tells you to "call Snapshot to list windows" - from inside Snapshot.

  - [ ]  a. Refuse that combination.

  - **Verify:** Unit - both false is refused.
- [ ]  3.20 **Annotated Snapshot image: badges sit outside their boxes and can hide each other.** Region of three stacked fields: badge "3" sat between EditA and EditB, "1" above EditC, and "2" was not visible at all.

  - [ ]  a. Draw each badge inside its box's top-left corner.
  - [ ]  b. Shift badges that would overlap another badge.

  - **Verify:** Live - annotated Snapshot of the three stacked harness fields shows badges 1-3 each inside its own field (screenshot check).
- [ ]  3.21 **App `launch_executable` error messages.** `args` as plain text ("-n 30 127.0.0.1", allowed by the schema) fails with "Expecting value: line 1 column 1 (char 0)"; a `.ps1` path gives the raw "[WinError 193] %1 is not a valid Win32 application".

  - [ ]  a. Accept `args` as a plain string, split with Windows command-line rules.
  - [ ]  b. For a non-executable (e.g. `.ps1`), reply "not an executable - run scripts through PowerShell".

  - **Verify:** Unit - both cases.
- [ ]  3.22 **PowerShell interactive prompts.** `Read-Host` silently returns an empty string; a confirmation prompt (Remove-Item of a folder with children, no `-Recurse`) fails with "Object reference not set to an instance of an object" at status 0 and deletes nothing.

  - [ ]  a. Run PowerShell with `-NonInteractive`.
  - [ ]  b. Report prompts as "interactive input is not available" with a non-zero status.

  - **Verify:** Live - `Read-Host x` and the folder Remove-Item (in `%TEMP%`) both return the clear error and a non-zero status; the folder still exists.
- [ ]  3.23 **Process `list` shows the server itself as a ~96% CPU process.** The windows-mcp server (PID 26072) appeared at 96-98% in every CPU-sorted list, yet used 0 CPU seconds over the next 8 s (62.7 s over 103 minutes in total): it measures itself while building the list. An agent could "fix" the apparently runaway process by killing its own server.

  - [ ]  a. Leave the server's own PID out of the CPU sample and mark it "(this server)".

  - **Verify:** Live - CPU-sorted Process `list` shows the server marked and not at the top.
- [ ]  3.24 **Common key names from computer use are unknown.** `Page_Down`, `KP_Enter`, `super`, `cmd` are refused ('Unknown key name'); `Return`, `BackSpace`, `Escape`, `pagedown` work. Models trained on computer use send xdotool-style names.

  - Done together with B.3.
  - **Verify:** see B.3.
- [ ]  3.25 **A registry key's (Default) value can't be set.** Registry `set` with `name=""` fails with "Cannot bind argument to parameter 'Name' because it is an empty string".

  - [ ]  a. Treat an empty name or `"(Default)"` as the key's default value in `set`.
  - [ ]  b. Do the same in `get`.

  - **Verify:** Live (in `HKCU:\Software\WMCP-Test`) - set then get the default value; `(Get-Item ...).GetValue('')` matches.
- [ ]  3.26 **Horizontal Scroll ignores `modifiers` but says it held them.** `type="horizontal"`, `modifiers="alt"` replied "... holding alt"; the harness logged no wheel event (the horizontal path uses UIA ScrollPattern, where held keys have no effect) - only the Ctrl/Alt key presses.

  - [ ]  a. Refuse `modifiers` on the horizontal ScrollPattern path (the other option - sending a real horizontal wheel when modifiers are given - can follow if needed).

  - **Verify:** Unit - horizontal + modifiers refused.
- [ ]  3.27 **Move `mouse_button="down"` without `loc` is undocumented.** It presses at the current pointer position (worked), but the description says only `up` may omit `loc`.

  - [ ]  a. Update the Move description to say `down` may omit `loc` too.

  - **Verify:** The tool description text says so.

# Part B - Improvements (to work like Claude Cowork)

Each item: what windows-mcp does today, what computer use / Cowork does, and the suggested change. Items that change behaviour start with a `[User]` design approval.

- [ ]  B.1 **Coordinates in screenshot space.** Today: when a screenshot is downscaled (screens above 1920x1080, or `WINDOWS_MCP_SCREENSHOT_SCALE` below 1), the model must multiply image coordinates itself using a printed scale factor. Cowork: the model always clicks in the pixel space of the image it saw and the host scales.

  - [ ]  a. [User] Approve the behaviour (design choice - changes what every coordinate means): scale automatically, with an opt-out for raw screen coordinates.
  - [ ]  b. Remember the last full screenshot's scale.
  - [ ]  c. Apply it to every `loc`, `from_loc` and `region`.
  - [ ]  d. Add the opt-out.

  - **Verify:** Unit - with a stored scale of 0.5, `loc=[100,100]` maps to (200,200); opt-out keeps (100,100). Live - `WINDOWS_MCP_SCREENSHOT_SCALE=0.5`, Screenshot, Click a harness button at its image coordinates: harness logs the click.
- [x]  B.2 **Refuse points outside the display.** Cowork returns an error result for coordinates outside the display.

  - Done together with 1.4.
  - **Verify:** see 1.4.
- [ ]  B.3 **Accept computer-use key names.** Today: Windows/SendKeys names (`pagedown`, `win`), no `super`, `cmd`, `Page_Down`, `KP_Enter`, no `+`. Cowork: xdotool names (`Return`, `Page_Down`, `super`, `ctrl+plus`...).

  - [ ]  a. Add an alias table for xdotool key names (`Page_Down`, `Page_Up`, `KP_Enter`, `KP_Add`...).
  - [ ]  b. Map `super`, `cmd`, `meta` to Win.
  - [ ]  c. Use the table in Shortcut.
  - [ ]  d. Use the table in every `modifiers` parameter.

  - **Verify:** Unit - each alias resolves. Live - Shortcut `Page_Down` and `KP_Enter` are logged by the harness; Click `modifiers="super"` holds Win.
- [ ]  B.4 **Zoom enlarges small areas.** Today: Screenshot `region` returns the area at native size (a 20x10 region came back as a 20x10 image). Cowork's `zoom`: the region is captured at full resolution and scaled up to the usual screenshot size so small text is legible, while later coordinates stay in full-screen space.

  - [ ]  a. [User] Approve the shape (design choice): a `zoom=true` option on Screenshot `region` (recommended) or a separate Zoom tool.
  - [ ]  b. Upscale the captured region to fit about 1280 px.
  - [ ]  c. Keep reported coordinates in full-screen space.

  - **Verify:** Unit - a 20x10 region with zoom returns a ~1280-px-wide image. Live - zoomed region of small harness text is readable.
- [ ]  B.5 **Longer holds and a bounded wait.** Today: Shortcut `hold` up to 10 s; Wait has no limit. Cowork: `hold_key` and `wait` both up to 300 s.

  - [ ]  a. Raise the Shortcut `hold` limit to 300 s.

  - Wait cap: done together with 2.12.
  - **Verify:** Unit - `hold=300` accepted, `301` refused.
- [ ]  B.6 **Fast key repeat.** Today: ~0.52 s per repeated press. Cowork's `key` with `repeat` fires the presses back to back.

  - Done together with 2.6.
  - **Verify:** see 2.6.
- [ ]  B.7 **Type without the clipboard.** Today: 20+ characters are pasted through the clipboard (bug 2.14). Cowork's `type` sends the characters.

  - Decided and built under 2.14 (`SendInput` Unicode events, chunked, clipboard untouched; paste kept only as an opt-in for very long text).
  - **Verify:** see 2.14, plus a 2,000-character text arrives intact.
- [ ]  B.8 **Errors as errors.** Cowork requires `is_error: true` on any failure.

  - Done together with 2.13.
  - **Verify:** see 2.13.
- [ ]  B.9 **Stable element references.** Today: `label=N` is an index into whatever tree was captured last (bugs 1.3, 2.11).

  - [ ]  a. [User] Approve the approach (design choice): labels tied to a Snapshot id (`snapshotId:N`), or element name/role resolved at click time (C.5).
  - [ ]  b. Implement the chosen approach.
  - [ ]  c. Refuse a label whose element no longer has the name/role Snapshot printed.

  - **Verify:** Unit - a stale label is refused. Live - Snapshot, change the harness layout, Click the old label: refused, no click logged.
- [ ]  B.10 **Verified replies.** Today: replies repeat the request ("Typed ...", "Single left clicked ...") even when nothing happened (bugs 1.4, 2.4, 2.5, 3.1, 3.3).

  - [ ]  a. [User] Approve the reply format (design choice - adds a little time to each action).
  - [ ]  b. Click: report the element under the pointer, e.g. "Clicked button 'ShowLater' at (633,521)".
  - [ ]  c. Type: report the field's value after typing.
  - [ ]  d. Scroll: report the scroll position after scrolling.

  - **Verify:** Live - each reply names the real element/value/position seen in the harness state file.
- [ ]  B.11 **Output caps everywhere.**

  - PowerShell, FileSystem read, Process list: done together with 2.10.

  - [ ]  a. Apply the shared cap to Scrape.
  - [ ]  b. Apply the shared cap to Snapshot text.

  - **Verify:** Unit - a long Scrape and a long Snapshot text are cut with the note.
- [ ]  B.12 **Scrape robustness.**

  - User-Agent: done with 2.16. Absolute links: done with 3.17. DOM link text: done with 3.12.

  - [ ]  a. Keyword filter of paragraphs for `query` when summarising isn't possible.

  - **Verify:** Unit - a page with a matching paragraph returns only matching paragraphs plus a note.
- [ ]  B.13 **Hit-testing everywhere.** Any listed element should be really clickable.

  - Done together with 1.5 (always-on-top windows), 1.6 (pop-up menus) and 2.3 (DOM mode).
  - **Verify:** see 1.5, 1.6, 2.3.
- [ ]  B.14 **Faster modifier release.** Today: modifier keys stay down ~0.5 s after each click. Cowork holds modifiers "only for the duration of that click".

  - Done together with 2.6 (subtask b).
  - **Verify:** see 2.6.

# Part C - New tools / abilities

Each is a new feature: the first subtask is the user's approval of the design.

- [ ]  C.1 **Cursor position.** Cowork has `cursor_position`. Today the position appears only in a Screenshot header, and shows "None" when the pointer is outside the captured region; Move with no arguments is refused.

  - [ ]  a. [User] Choose the shape (design choice): Move with no `loc`/`label` returns the position (recommended - no new tool), or a new `CursorPosition` tool.
  - [ ]  b. Return the current `[x, y]`.

  - **Verify:** Live - the returned position matches `GetCursorPos`.
- [ ]  C.2 **Release everything (panic button).** No tool can release stuck keys or buttons after a failed sequence (bug 2.4 shows how a held button spoils the next action).

  - [ ]  a. [User] Choose the shape (design choice): a `ReleaseInputs` tool, or Shortcut `release_all=true`.
  - [ ]  b. Send key-up for every modifier.
  - [ ]  c. Send button-up for every mouse button.
  - [ ]  d. Report what was held.

  - **Verify:** Live - Move `mouse_button="down"`, then release: poller and harness show all keys and buttons up; the reply names the left button.
- [ ]  C.3 **Window management.** App has launch/switch/resize only. Missing: minimise, maximise, restore, close (gracefully), move a window to another monitor, list windows with handle, PID and state (a window list with PIDs also allows killing by PID after App `launch`, which returns no PID).

  - [ ]  a. [User] Approve the modes and names (design choice).
  - [ ]  b. Add `mode="minimize"`.
  - [ ]  c. Add `mode="maximize"`.
  - [ ]  d. Add `mode="restore"`.
  - [ ]  e. Add `mode="close"` (graceful close message, not a kill).
  - [ ]  f. Add a window list with handle, PID and state.
  - [ ]  g. Add moving a window to another monitor.

  - **Verify:** Live - each mode on the harness, confirmed by the window's state; the list shows the harness PID; the monitor move is checked on the virtual second monitor (see memory note on the temporary 2nd screen).
- [ ]  C.4 **Clipboard beyond text.** Clipboard reads and writes text only; non-text is reported as "empty or non-text".

  - [ ]  a. [User] Approve the scope (design choice).
  - [ ]  b. `get` reports the formats present (image, files, HTML).
  - [ ]  c. `set` can put an image file on the clipboard.
  - [ ]  d. `set` can put a list of files on the clipboard.
  - [ ]  e. `get` can save a clipboard image to a file.

  - **Verify:** Live - back up the user's clipboard first; round-trip an image and a file list; restore the user's clipboard.
- [ ]  C.5 **Click an element by name.** A `Click` target like `element="button:Save"` (window optional) resolved at click time - avoids stale labels (1.3) and extra Snapshots. Cowork has no accessibility tree, so this is an extra that windows-mcp is uniquely able to offer.

  - [ ]  a. [User] Approve the syntax (design choice; ties in with B.9).
  - [ ]  b. Resolve the element by role and name at click time.
  - [ ]  c. Refuse with the candidate list when zero or several elements match.

  - **Verify:** Live - Click `element="button:ClickMe"` is logged by the harness; an ambiguous name is refused with candidates.
- [ ]  C.6 **Find text on screen (OCR) for canvas apps.** Games, remote desktops and canvas UIs expose no accessibility tree; WaitFor and Snapshot see nothing there.

  - [ ]  a. [User] Approve the shape (design choice): `WaitFor condition="screen_text"` and/or a `FindText` tool.
  - [ ]  b. Read on-screen text with Windows' built-in OCR (`Windows.Media.Ocr`, no new dependency).
  - [ ]  c. Wire it into the chosen tool.

  - **Verify:** Live - find a harness label's text by OCR and get its position within a few pixels of the UIA position.
- [ ]  C.7 **Wait for the screen to change or settle.** For apps without accessibility data, to replace fixed Waits after clicks.

  - [ ]  a. [User] Approve the conditions and defaults (design choice).
  - [ ]  b. Add `WaitFor condition="screen_changed"` over a region (pixel difference).
  - [ ]  c. Add `WaitFor condition="screen_idle"` over a region.

  - **Verify:** Live - ShowLater in the harness triggers `screen_changed`; a static region returns `screen_idle` quickly.
- [ ]  C.8 **Action log (audit trail).** The project notes say there is no audit log or rollback. Goal: a user can see afterwards exactly what an agent did.

  - [ ]  a. [User] Approve location, format and what is redacted (design choice).
  - [ ]  b. Write an opt-in append-only log (tool name, arguments, result, time) to a file.
  - [ ]  c. Redact secrets in logged arguments.
  - [ ]  d. Hook it in at the tool boundary, like `@with_analytics`.

  - **Verify:** Unit - a call with a secret-looking argument is logged redacted. Live - with the log on, three tool calls appear in the file in order.

# Part D - Guide corrections and open items

## 4. Skills/Skill.md corrections

- [ ]  4.1 **Warn about this round's unfixed bugs in `Skills/Skill.md`.** Wrong or missing today: Snapshot row (an on-top window that is not focused can get no elements; "region only reads windows visible in it" really means windows *overlapping* it, covered or not; DOM mode is not hit-tested; **labels change after WaitFor or any other capture - re-Snapshot right before a label click**); App switch (works from the last capture's window list; a vague name picks one window silently); resize (accepts invalid sizes and off-screen positions); Click row (alt also holds Ctrl, win opens Start, hover ignores modifiers, right/middle double clicks don't register, off-screen points are clamped and clicked); MultiEdit (a bad target is clamped to the screen corner and later fields may silently fail); Scroll (`wheel_times` below 1 does nothing); Move (a forgotten `down` turns the next Click into a drag); Shortcut (`repeat` takes ~0.5 s per press); Wait (no upper limit); PowerShell (no output cap); FileSystem read (10 MB limit applies even with offset/limit); Registry (**never use `*`, `?` or `[ ]` in a path, and always start with `HKCU:\`/`HKLM:\` - other paths reach the file system**); Type (the clipboard is restored for text only - an image or files on it are lost); Shortcut (use `ctrl+=` for Ctrl+Plus; `super`, `Page_Down`, `KP_Enter` are unknown; holding `win` alone opens Start); Snapshot (elements under an open context menu are still listed); PowerShell (each call is a fresh session starting in the home folder; prompts can't be answered); Scrape (some sites such as Wikipedia refuse it - use PowerShell `Invoke-WebRequest`); most tools report failures inside a normal reply, so read the text, not just the success flag. Confirmed correct this round: every other claim in the file.

  - [ ]  a. Add the warnings above for every bug not yet fixed.
  - [ ]  b. With each fix, remove its warning in the same change (part of that item's work, not a separate pass).

  - **Verify:** Each warning in the guide matches a still-open item in this file; no warning remains for a ticked item.

## 5. Not tested / needs a person

- [ ]  5.1 [User] **True high-DPI test (125% / 150% scaling).** Needs the display scaling changed and a sign-out/sign-in, which would end the agent's session. Optional: change scaling, sign back in, then ask the agent to re-run the coordinate checks (Click, Move, Screenshot region, Snapshot centres).
  - **Verify:** At 125% and 150%, a Click on each harness button is logged by the harness, and Snapshot centres fall inside the buttons on a screenshot.

## Round-1 fixes that held (no action)

FileSystem overwrite refusal and yes/no/on/off booleans; Process kill by exact name (near-miss name survived); Registry recursive guard (for literal paths); hidden elements left out of the normal Snapshot tree; PowerShell errors at status 0, `timeout` below 1 refused, real timeout; Registry binary hex/list input; Notification unknown-app refusal and on-screen display (Unicode and `<&>` shown literally); Screenshot "Skipped (screenshot-only)" wording and grid lines; Scrape "summary unavailable" note and SSRF blocking (loopback, IPv6-mapped, metadata address, loopback DNS name, redirect to loopback); Click `clicks` 0-3 and refusal of others; `[label:N]` in the text tree and label clicks; App switch by substring and program name, restore from minimised, launch by name, resize to exact outer size, maximised refused; Snapshot region speed (1.4 s); screenshot backends dxcam/pillow/mss/bogus; VS Code guard; emoji typing and long-text paste with the user's clipboard restored; Shortcut `hold` accuracy (0.5 s -> 0.54 s, 10 s -> 10.03 s) and `repeat` counts; drag pixel-exact; decimal Wait.

# Implementation verification

- **Per item:** an item is ticked only when all its subtasks are done and its own Verify line passed; the result is written in one line under the item (date, what was checked).
- **Tests first:** each code fix gets a failing test first, then passes (Rule 7).
- **Whole suite:** after every item, `.venv/Scripts/python.exe -m pytest -q` is green and `ruff check .` and `ruff format --check .` are clean.
- **Live, checked twice:** each fix is re-checked on the real desktop against the WMCP harness, and confirmed a second way (harness log/state file, key-state poller, foreground-window logger, PowerShell read, screenshot). Live tests use a small test window, never a full-desktop tree read (VS Code freezes).
- **Safety:** items 1.1, 1.2, 3.7 and 3.25 are re-tested only inside `HKCU:\Software\WMCP-Test` and `%TEMP%`; the user's clipboard is backed up before any test overwrites it and restored after.
- **Guide:** `Skills/Skill.md` warnings are kept in step with this file (4.1).
- **Acceptance:** every item above is fixed and ticked, or explicitly declined by the user (the decline is noted under the item).
