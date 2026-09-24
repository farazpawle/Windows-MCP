---
Title: Windows-MCP tool test report (2026-09-22 to 2026-09-24)
Description: Live test results for all 20 windows-mcp tools on the maintainer's Windows 11 PC, run from Claude Code against the local repo on 2026-09-22. Round 1 - a verdict per tool, the ten bugs found and fixed, and post-restart re-tests. Round 2 (after every round-1 item was fixed) - per-tool verdicts again, confirmation that all round-1 fixes held, and 49 new bugs (6 High - registry paths act as wildcards and reach the file system, Snapshot labels renumbered by WaitFor, off-screen points clamped and clicked, an on-top unfocused window gets no Snapshot elements, pop-up menus don't hide covered elements; 16 Medium; 27 Low), plus a comparison with Claude Cowork computer use giving 14 improvements and 8 new-tool ideas, with how each was verified. Round-2 backlog (all done) - Plan/completed/windows-mcp-open-issues-round2.md. Round 3 (2026-09-24) - all 21 tools in a real-work scenario plus per-tool timings: 2 High bugs (windows that cannot be maximized missing from the window list; a full-screen capture missing Avast's front alert), 2 Medium, 5 Low, 9 improvements, 1 new ability; an Avast alert traced to another app; backlog Plan/windows-mcp-open-issues-round3.md. Round 4 (2026-09-24, after the round-3 backlog) - the same scenario with per-call timings from Claude Code's MCP log: 1 High bug (multi-line Type ~42 ms per character), 5 Medium (App launch names an old window, Snapshot word boxes include trailing spaces, text_exists misses document text, in-window dialogs not noted, caret start/end per line), 9 Low, 7 improvements, 2 new abilities, 31 guide and skill corrections; backlog Plan/windows-mcp-open-issues-round4.md.
Tags: testing, qa, windows-mcp
Updated: 2026-09-24
---

# Windows-MCP tool test report

**Setup:** Windows 11 Pro 26200, one 1920x1080 display, Avast antivirus, Python 3.14.0. The server ran from the local repo (`uv --directory ... run windows-mcp serve`), driven from Claude Code.

**Method:** every change a tool made was checked with something other than the tool under test. For input tools this was a WinForms test window that logged each mouse and key event and saved its control state as UTF-8 JSON every 300 ms. For system tools it was PowerShell, the registry, the process list or a file read. Destructive tests ran only in `%TEMP%`, `HKCU:\Software\WMCP-Test` and processes the test launched itself.

## Verdicts

| Tool | Verdict | Notes |
|---|---|---|
| DisplayInventory | Pass | |
| Screenshot | Pass, with notes | "No windows found" means the window list was not checked. Grid lines do not render. |
| Snapshot | Pass, with notes | The text tree shows no label ids; `label=N` is an index readable only from the annotated image. A region keeps elements of windows hidden behind the top window (see Open issues). Busy editors fill the 500-element cap. |
| Click | Pass | Left, right and middle clicks, and clicks 0, 1, 2 and 3, verified by event log. `clicks=-1` silently single-clicks and replies "None left clicked". |
| Type | Pass after fixes | Caret start/end, press_enter, accents and CJK verified. Emoji, empty text and clear on legacy boxes fixed. |
| MultiEdit | Pass | Replaces existing text in each field. |
| MultiSelect | Pass | Ctrl-select picked 3 items; without Ctrl the last click wins. The reply says "multi-selected" either way. |
| Scroll | Pass after fix | Vertical: 3 wheel notches = 360 px. Horizontal fixed (was scrolling vertically in native apps). |
| Move | Pass | Hover, drag with `from_loc`, and drag from the current position with `duration`, all pixel-exact. |
| Shortcut | Pass after fix | Combos and single keys verified. An unknown key name used to leave Ctrl held down. |
| Wait | Pass | `Wait(3)` measured at 3.4 s including call overhead. |
| WaitFor | Pass after fix | Each condition answered in ~0.2 s with a frozen app open; timeout returns cleanly. `text_exists` fixed. |
| App | Pass | `launch_executable` verified; `switch` needs a long title fragment. |
| PowerShell | Pass, with notes | Non-terminating errors are dropped when the exit code is 0. `timeout=0` fails every command. |
| FileSystem | **Fail (open)** | `write` overwrites an existing file even with `overwrite=false`. A string `"yes"` counts as false. |
| Registry | Pass, with notes | Binary takes a single byte only. Deleting a key without `name` wipes all sub-keys without confirmation. |
| Process | Pass, with notes | The name filter is fuzzy ("pwsh" matched ShellExperienceHost). Kill by PID. |
| Clipboard | Pass | Unicode and multi-line text round-trip. Uses pywin32, so it was never affected by the emoji paste bug. |
| Notification | **Fail (unconfirmed display)** | The call reported success, but the user saw no toast. It also reports success for a fake `app_id`. |
| Scrape | Pass after fixes | HTTPS aborted the whole server, then failed certificate checks under Avast (both fixed). Verified: a real page loads, an expired certificate is refused, loopback is blocked. `use_dom` checked only for its "page not open" reply (see Post-restart re-tests). |

## Bugs fixed (uncommitted, tests added)

| Bug | Cause | Fix | Tests |
|---|---|---|---|
| Snapshot/WaitFor/App hang forever on a "Not Responding" app | The legacy CUIAutomation has no call timeout | CUIAutomation8 with 2 s / 5 s timeouts; hung windows skipped | `test_uia_timeouts.py`, `test_hung_windows.py` |
| Emoji typed as a wrong character | `SendUnicodeChar` sent one UTF-16 unit for non-BMP chars | Send the surrogate pair | `test_key_input.py` |
| Emoji cut in half in long typed text | `SetClipboardText` sized the buffer in code points and dropped the NUL | Size in UTF-16 units | `test_key_input.py` |
| `Type(text="")` cleared the box, then raised "string index out of range" | `SendKeys("")` indexed `text[0]` | Empty text is a no-op | `test_key_input.py` |
| Bad shortcut left Ctrl held down | `SendKeys` pressed Ctrl, then failed on the unknown key | Unknown `{Name}` keys are rejected before any key is sent | `test_key_input.py` |
| Horizontal scroll moved content down | Shift+wheel is only a browser/Explorer convention | UIA ScrollPattern of the nearest horizontally scrollable element; real horizontal wheel as fallback | `test_scroll_horizontal.py` |
| `WaitFor text_exists` never saw plain labels and ignored `window_name` | The tree keeps only interactive/scrollable nodes outside browsers | Case-insensitive substring `FindFirst` per target window (25–50 ms); `window_name` respected | `test_find_text.py`, `test_wait_for_tool.py` |
| `Type(clear=true)` deleted one character in legacy edit boxes | Win32 EDIT without visual styles ignores Ctrl+A | Empty any leftover text through ValuePattern | `test_type_clear.py` |
| First HTTPS request aborted the server ("OPENSSL_Uplink … no OPENSSL_Applink") | Avast injects `SSLKEYLOGFILE=\\.\aswMonFltProxy\…`; this OpenSSL build aborts on it | The server drops `SSLKEYLOGFILE` at startup | `test_ssl_keylog_env.py` |
| Scrape HTTPS rejected under Avast ("Basic Constraints of CA cert not marked critical") | Python 3.13+ strict X.509 checks reject Avast's re-signing root | Scrape verifies through the Windows certificate store via `truststore` (new direct dependency, 0.10.4; no known advisories). Scoped to Scrape because truststore is client-only | `test_scrape_tls.py` |

Every fix was also checked live against the real desktop. The full suite passes (634 tests).

## Open issues

1. **Notification toasts not seen.** The call succeeds but no toast appeared for the user; Do Not Disturb may be the cause. Not investigated.
2. **FileSystem `write` ignores `overwrite=false`.** Not fixed yet.
3. **Hidden elements in the tree.** Snapshot lists elements of background windows even where another window covers them, so clicking one hits the covering window. This is not region-specific.
4. **Minor replies.** `Click` with `clicks` outside 0–2 replies "None … clicked"; negative values single-click. `MultiSelect` says "multi-selected" even without Ctrl.

## Post-restart re-tests (session 3, 2026-09-22)

Run against the restarted server (local repo, truststore installed):

- **Type, emoji.** Short text `Hi 😀👍🏽 café ✓` (typed key by key) and a 43-unit mixed emoji/CJK string (clipboard paste path) both arrived exactly, compared UTF-16 unit by unit through the harness. The user's clipboard was restored after the paste test.
- **Scrape HTTP/HTTPS.** `http://` and `https://example.com` load with `use_sampling=false`; `expired.badssl.com` is refused with a Windows certificate-store error (truststore active). The server stayed up.
- **Scrape sampling.** With the default `use_sampling=true`, Claude Code does not support MCP sampling, so the tool silently returns the raw page. Expected fallback, but the reply does not say the summary was skipped.
- **Scrape `use_dom`.** With no tab on the URL, it returns a clean "open the page in the browser first" message. A full DOM read was not possible: a browser-lock extension on the user's Edge replaces new windows with an error page.

# Round 2 (2026-09-22, after the round-1 backlog was fixed)

**Setup:** same PC and display; server from the local repo on branch `fix/open-issues-backlog` (Click offered `modifiers`, Move offered `mouse_button`, so the live tools ran the current code). Driven from Claude Code.

**Method:** the round-1 WinForms harness, extended to log the modifier state at every mouse press, key-up events and wheel events. Two new background checkers: a key-state poller (`GetAsyncKeyState` every 5 ms, reporting each key or button seen down and for how long) and a foreground-window logger. System tools were checked with PowerShell reads (`reg query`, `Get-ChildItem`, `Get-Process`, byte-level file reads). Empty-string inputs and the screenshot backends were driven through a separate FastMCP client starting a private server, because the Claude Code client cannot send an empty string. Destructive work stayed in `%TEMP%\wmcp-r2` and `HKCU:\Software\WMCP-Test`; processes were ended by PID; Notepad and Edge were used only in the agent's own tabs, closed with Ctrl+W. All of it was removed afterwards and the user's clipboard text restored.

## Verdicts

| Tool | Verdict | Notes |
|---|---|---|
| DisplayInventory | Pass | Not re-tested beyond round 1. |
| Screenshot | Pass, with notes | Grid lines work. The orange border sometimes leaks into the next capture. Grid values are not validated. |
| Snapshot | **Fail (open)** | An on-top window without focus got no elements (cap spent on covered windows). DOM mode lists covered elements. Labels are renumbered by WaitFor. |
| Click | **Fail (open)** | Alt also holds Ctrl; Win opens Start; off-screen points are clamped and clicked; `label=-1` clicks the last element; right/middle double clicks don't register. Shift/Ctrl and combos correct and released. |
| Type | Pass, with notes | No-location typing, caret, clear, Enter, 1,097-char paste with emoji, clipboard preserved. Claims success when focus is a button. |
| MultiEdit | **Fail (open)** | A bad target was clamped to the show-desktop corner, minimised every window and typed onto the desktop; the reply said all fields were edited. |
| MultiSelect | Pass | Reply wording by mode correct. |
| Scroll | Pass, with notes | Ctrl/Shift wheel correct. `wheel_times` 0 or negative accepted and reported as scrolled. |
| Move | Pass, with notes | Drag with modifiers pixel-exact; down/steer/up works. No held-button tracking (forgotten `down` turns the next Click into a drag). |
| Shortcut | Pass, with notes | `repeat` counts exact, `hold` accurate, bad values refused, nothing left held. ~0.52 s per repeated press. |
| Wait | Pass, with notes | Decimals accurate; bad values refused; no upper limit. |
| WaitFor | Pass, with notes | All conditions fast; but it replaces Snapshot's label map. |
| App | Pass, with notes | Launch, restore-and-switch, resize, maximised refused. Switch uses a stale window list; resize accepts invalid sizes/off-screen positions. |
| PowerShell | Pass, with notes | Errors at status 0, timeout, Unicode fine. No output cap; partial output lost on timeout. |
| FileSystem | Pass, with notes | Overwrite guard and booleans hold; Unicode/space paths fine. 10 MB limit blocks offset/limit reads. |
| Registry | **Fail (open)** | Paths are wildcards (a `*` delete removed two keys) and file-system paths are accepted (a delete removed a folder). |
| Process | Pass, with notes | Exact-name kill held (near-miss survived). Negative `limit` dumps every process. |
| Clipboard | Pass | Unicode/emoji/tabs round-trip; empty text works (script client). |
| Notification | Pass | Unknown app refused; toasts shown, `<&>` literal. Toasts can appear a few seconds late. |
| Scrape | Pass | Summary note, SSRF blocks (incl. IPv6-mapped, metadata, loopback DNS, redirect), DOM read of own tab. DOM text drops link text. |

## Round-1 fixes re-checked

All held: FileSystem overwrite and yes/no booleans, Process exact-name kill, Registry recursive guard (literal paths), hidden elements (normal tree), PowerShell errors/timeout/`timeout=0`, Registry binary input (read back with `reg query`), Notification checks, Screenshot wording and grid, Scrape note, Click counts, `[label:N]` ids, App switch/launch/resize, Snapshot region speed (1.4 s), screenshot backends (dxcam, pillow, mss -> pillow with warning, bogus -> auto), VS Code guard (listed by name only under every region Snapshot; VS Code stayed responsive).

## New issues

49 bugs, all recorded with steps, actual/expected, severity and a suggested fix in `Plan/completed/windows-mcp-open-issues-round2.md` (Part A), plus improvements (Part B) and new tools (Part C) measured against Claude Cowork's computer use. The first five High ones:

1. Registry paths are treated as wildcards: `delete HKCU:\Software\WMCP-Test\A*` with `recursive=true` deleted keys A1 and A2; `[ ]` in a key name makes it unwritable.
2. The Registry tool accepts file-system paths: `delete` on a `%TEMP%` folder removed the folder and its file, replying "Registry key ... deleted"; an empty path lists the home folder.
3. WaitFor replaces Snapshot's label map: `label=0` meant ShowLater before a WaitFor and the window's Close button after it; the click closed the window.
4. Off-screen points are clamped to the screen edge and acted on: MultiEdit with `[99999,99999]` hit the show-desktop corner, minimised all windows and typed onto the desktop, and reported success.
5. A visible always-on-top window that is not focused got no elements in a Snapshot of its own area (the 500-element cap was spent on the covered windows behind it).

## Environmental notes

- Focus moved to VS Code during one 55-second `repeat=100` run; 21 key presses went to the VS Code editor (caret moves only; `git status` showed no change). From then on the harness was clicked before every keyboard test.
- A 1.1 s left-button press and a hover were seen that no tool sent (the user touching the mouse). No effect on results.
- The Claude Code client cannot send an empty string argument; empty inputs were tested through a separate FastMCP client.
- Not tested: true high-DPI scaling (needs a sign-out; left as a `[User]` item).

## Continued testing (same day, after the first write-up)

The user asked for more testing plus improvement and new-tool suggestions measured against Claude Cowork. Reference: Anthropic's computer-use toolset docs (17 actions; coordinates in screenshot space; errors for off-display points; `is_error` on failures; hold_key and wait up to 300 s; zoom upscales).

Passed: Scroll/Move/Type/MultiSelect by label; WaitFor `focused_element`, `element_enabled`, missing-element timeout; FileSystem list of a file, missing search root, `../` pattern, folder info; DisplayInventory; Process sort by name/cpu, protected PIDs refused, negative PID refused; App `launch_executable` with a missing `cwd` refused; long notification; Scrape of a normal page; Snapshot annotated image with grid.

New bugs (details in the backlog):
- Pop-up menus don't hide the elements under them (High 1.6).
- 12 of 13 failing calls return `is_error=False` (Medium 2.13), checked with a FastMCP script client.
- A long Type wiped an image from the clipboard (Medium 2.14).
- The plus key can't be named (`+`, `ctrl++`, `plus`); `ctrl+=` works (Medium 2.15).
- Scrape gets 403 from Wikipedia because of the default Python User-Agent; PowerShell reproduces it with that User-Agent (Medium 2.16).
- Holding `win` alone opens Start; the next key typed into Start search (added to Medium 2.2).
- Low: Scrape ignores `query` silently; Screenshot region text form, 1-px out-of-bounds accepted, `use_annotation` ignored; Snapshot with tree and image both off; overlapping annotation badges; `launch_executable` error texts; PowerShell prompts; the server listing itself at ~96% CPU (it used 0 CPU seconds over 8 s); computer-use key names (`Page_Down`, `KP_Enter`, `super`, `cmd`) unknown.

Tester's error: the clipboard-image test overwrote the user's clipboard without a fresh backup (the round-2 backup had already been restored and deleted). Windows clipboard history is on, so the earlier text remains available through Win+V.

# Round 3 (2026-09-24, real-work scenario, all 21 tools)

**Setup:** at the PC (console session, one 1920x1080 display, 100%), the windows-mcp server Claude Code is connected to (local repo, branch `fix/open-issues-backlog`, round-2 backlog complete). The user was mostly hands-off but used the PC during an Avast interruption.

**Method:** one office job driven through the connected tools the way an agent works: files and settings for a weekly sales report (FileSystem, Registry, PowerShell), research (Scrape over HTTP and from a new Edge tab), writing and editing the report in Notepad, filling a small WinForms "Report details" form, picking and copying files in File Explorer, a toast, then clean-up. Each result was checked a second way (PowerShell reads of files, registry, clipboard, processes and window state; screenshots; the form's saved output). A separate timing pass called every tool 3 times through an in-process server against a guarded test window (`windows-mcp-live-test` harness) and took the median. The user's clipboard (an image) was saved with Clipboard `save_image` before the first overwrite and restored with `set image` (checked 726x271).

## Verdicts

| Tool | Verdict | Notes |
|---|---|---|
| DisplayInventory | Pass | Bounds, work area, DPI. |
| Screenshot | Pass, with a gap | Region, zoom, grid correct. **A full-screen capture missed Avast's alert that was in front** (bug R3-2). |
| Snapshot | Pass, with notes | Region, DOM, labels, annotation correct. Tree lists many empty `window ""` entries. |
| FindText | Pass, with notes | Positions exact to the pixel. A phrase across table columns is not found (OCR splits the line). |
| WaitFor | Pass, with notes | active_window, element_exists, text_exists, screen_idle all fast. `screen_changed` missed a clock change (R3-4). |
| Wait | Pass | 0.1 s = 0.10 s. |
| Click | Pass, with notes | Left/right/shift/hover/element by name correct. False refusals with `element=` / labels in some apps (R3-3). |
| Type | Pass | 294-char multi-line report exact; type-into-selection; Enter in Explorer's address bar. |
| MultiEdit | Pass | Three form fields replaced; values saved exactly. Slow (~2.3 s a field). |
| MultiSelect | Pass | Ctrl-selected exactly 3 files. |
| Scroll | Pass | Position reported (76.9% -> 0% -> 46.2%); Ctrl+wheel zoom 120%; bad axis refused. |
| Move | Pass | Drag and down/steer/up selected exact lines; cursor readout exact. |
| Shortcut | Pass | repeat 20 in 0.85 s; save, copy, paste, Ctrl+L, Win+N. |
| App | **Fail (open)** | Launch/switch/resize/min/max/restore/move/close work, but windows that cannot be maximized are missing (R3-1). |
| PowerShell | Pass | Errors as tool errors, timeout status -1, `success_exit_codes`, Read-Host refused clearly. |
| FileSystem | Pass, with notes | Overwrite/recursive guards held; offset/limit exact. Folder `info` size is the entry, not contents. |
| Registry | Pass | String/DWord/Binary/MultiString(JSON)/ExpandString stored right; literal paths; sub-key guard; hive-less path refused. |
| Process | Pass, with notes | Kill by PID, protected PID refused, limit 0 refused. List takes ~1.6 s. |
| Clipboard | Pass | Image backup/restore, file lists, Unicode+emoji text; files read back by PowerShell. |
| Notification | Pass | Delivered to the notification centre (Do Not Disturb on, as the reply warned); fake app refused. |
| Scrape | Pass | HTTP + query filter (2 of 119 paragraphs), Wikipedia OK, loopback blocked, DOM mode read the new tab. |

## Timing (median of 3, in-process, seconds)

Under 0.1: DisplayInventory, Screenshot full 0.07 / region 0.01, Snapshot region 0.08, App list/switch 0.05, Shortcut 0.04, FileSystem, Clipboard, Click hover. 0.1-0.5: Snapshot full desktop 0.18, WaitFor 0.17-0.18, Scrape 0.11, PowerShell 0.27, Registry 0.29, FindText region 0.42. 0.5-1.2: Move hover 0.52, Click 0.56, Click element 0.63, Type 60 chars 0.70, Notification 0.82, Shortcut repeat 20 0.85, Click double 0.88, Scroll 1.09, Type 10 chars 1.11, Click triple 1.17, Move drag 1.19, FindText full screen 1.24. Over 1.5: MultiSelect (2 clicks) 1.58, Process list 1.60, MultiEdit (1 field) 2.34. No call hung; the slow ones are fixed pauses (0.5 s after every click and move) and per-key delays, listed as improvements.

## Bugs

- **R3-1 (High) Windows that cannot be maximized are missing from the window list.** `Desktop.get_windows` keeps only windows whose WindowPattern has CanMinimize **and** CanMaximize. A WinForms FixedDialog form, Avast's alert, and Notepad while it asks "create a new file?" (its Maximize button is disabled) were all absent from App `list`; App `close`/`switch` by name and Click `window=` replied "not found" while the window was in front; Snapshot named it as the focused window. Right after the Notepad question was answered, Notepad reappeared in the list.
- **R3-2 (High) A full-screen capture can miss a window that is in front.** Avast's "Threat blocked" alert (foreground per `GetForegroundWindow`, visible, not cloaked, at (455,179)-(1055,571)) was absent from every full Screenshot/Snapshot image (backend pillow); a `region` capture of the same rectangle (backend dxcam) showed it. Cause: `DxcamBackend.is_available` returns False when no region is given, so full captures always use GDI (pillow), which misses this kind of window. The agent then believed the alert had closed.
- **R3-3 (Medium) False refusals from the "still at its spot" check.** Click `element="button:MORE OPTIONS"` in Avast's alert was refused as "covered ... bring it to the front" while it was in front: `ControlFromPoint` in an embedded web page returns the page's pane, not the button. Type `label=` on Explorer's Address Bar was refused as "the screen changed since Snapshot": its centre shows a path button drawn over the box. Both messages point the agent the wrong way.
- **R3-4 (Medium) WaitFor `screen_changed` misses small real changes.** The fixed 100-changed-pixel floor ignored the taskbar clock going 10:18 -> 10:19 in an 80x30 region (70 s timeout).
- **R3-5 (Low) Identical duplicates can't be picked.** Explorer's context menu exposes "Copy as path" twice (same type and name); Click `element=` refuses as ambiguous and its advice (give the type) cannot help.
- **R3-6 (Low) "Also matched ..." after an exact title.** `name="outbox - File Explorer"` (the exact title) still added "Also matched" with the user's other File Explorer window.
- **R3-7 (Low) Notification reply doubles a full stop** when the message ends with "." ("...to outbox..").
- **R3-8 (Low) FileSystem `info` on a folder** reports 4 KB (the directory entry), not the 407 bytes it holds.
- **R3-9 (Low) Registry Binary shown two ways:** `get` gives `01,02,ff`, `list` gives `{1, 2, 255}`.

## Improvements

- **R3-I1 Fixed pauses:** Click (0.56 s) and Move hover (0.52 s) each include a fixed 0.5 s wait; Scroll 1.1 s per call; MultiSelect ~0.8 s per click; MultiEdit ~2.3 s per field. Computer use has no such floor. Wait only when the next step needs it (or make the settle short and adaptive).
- **R3-I2 Short text is slower than long text:** Type 10 characters 1.11 s, 60 characters 0.70 s — short text goes through SendKeys with per-key delays; send all plain text through the Unicode path.
- **R3-I3 Process list 1.6 s** even for `limit=5` sorted by memory: sample CPU only when `sort_by="cpu"`.
- **R3-I4 PowerShell runs look like malware to antivirus heuristics:** every run is `powershell -EncodedCommand <base64>` and the OCR script uses reflection. Not proven to trigger Avast today (three OCR runs raised nothing), but a temp `.ps1` run with `-File` is plainer.
- **R3-I5 `launch_executable` bare names** could also use the App Paths registry (`msedge.exe` is not on PATH; `Start-Process msedge` finds it).
- **R3-I6 FindText phrase across columns:** join OCR lines that share a baseline, so "North 460 units" is found.
- **R3-I7 Right-click menus appear ~1 s after Click returns**; a screenshot taken straight away shows no menu.
- **R3-I8 Snapshot tree noise:** many empty `window ""` lines (invisible helper windows).
- **R3-I9 Tool description** says FindText takes ~2.5 s on a full screen; measured 1.24 s.

## New tools / abilities

- **R3-N1 Pop-up detection:** WaitFor `condition="new_window"` (any new top-level window, dialogs included) or a note in every reply when the foreground window changed unexpectedly. Both surprises this round (Notepad's question, Avast's alert) were found only by accident.

## Guide corrections made (Skills/Skill.md)

Machine line (1920x1080 at the PC; 2560x1440 only over RDP); typical cost per call; second-screen move no longer "not yet tested"; PowerShell non-zero exit and timeout are tool errors (status -1) with `success_exit_codes`; Registry MultiString takes a JSON list; Binary shown two ways; Process `limit` below 1 refused and CPU% not summed; FindText timing and column gaps; WaitFor 100-pixel floor; FileSystem folder size; plus warnings for R3-1, R3-2, R3-3 and the Edge path.

## Environmental notes

- **Avast alert was not caused by windows-mcp.** At 09:59:54 Avast Behavior Shield raised "powershell.exe ... IDP.HELU.PSE91 - Command line detection". It was first blamed on FindText's OCR (Windows PowerShell); disproved: three OCR runs later, with no exception, raised nothing, and the same alert came back at 10:09:59 and 10:14:01 with no OCR running. The only Windows PowerShell running was another installed app's hidden tray script (installed the night before), whose own header records Avast flagging it. The user closed that app; the alert stays unanswered because its only choices were Quarantine (would target Windows' own powershell.exe) and a PowerShell-wide exception. Avast's "More options" did not react to the tool's clicks ("See details" did).
- The Notepad launched on the report file restored five of the user's unsaved tabs; only the report tab was typed into, and closing the window kept all five (tab-state files checked).
- Do Not Disturb was on, so the toast went straight to the notification centre.
- Clean-up verified: work folder deleted, `HKCU:\Software\WMCP-Work` gone, form and own Explorer window closed, clipboard image restored.

# Round 4 (2026-09-24, real-work scenario after the round-3 backlog, all 21 tools)

**Setup:** at the PC (console session, one 1920x1080 display, 100%), the windows-mcp server Claude Code is connected to, started 15:50 from this repo on branch `fix/open-issues-backlog` (round-3 fixes committed; working tree clean). Step 0 passed: Process `list details=true` showed "Started" and "Command line", and every App `list` line ended `at (x,y) size WxH`. Test only: no code was changed. The user was hands-off during the input steps (17:34-17:45).

**Method:** one job, "prepare a small weekly sales report", driven through the connected tools: data file and folders (FileSystem), settings of every value type (Registry), a summary and failing commands (PowerShell), process lists and a kill, the report typed and edited in Notepad (Click, Type, MultiEdit in Notepad's Find & Replace, Shortcut, Scroll, Move), a file pick in File Explorer (MultiSelect), OCR checks (FindText, WaitFor), Edge with a throwaway profile (App, Scrape), a toast, and two pop-ups (Notepad's "save changes?" and a WinForms message box). Every change was checked a second way: PowerShell reads of files, raw registry values (.NET, not expanded), clipboard, processes and window rectangles (`GetWindowRect`, DWM frame), plus screenshots. **Timing** is end-to-end per call from Claude Code's MCP log (`%LOCALAPPDATA%\claude-cli-nodejs\Cache\<project>\mcp-logs-windows-mcp\*.jsonl`, "Calling MCP tool" to "Tool ... completed", millisecond timestamps), so it includes stdio transport; WaitFor times are its own reply. Calls to the same tool made in parallel cannot be paired in that log and were not used for timing. The clipboard (text) was saved to a file before the first overwrite and restored (checked equal) after the copy steps and again at the end.

## Verdicts

| Tool | Verdict | Calls and evidence |
|---|---|---|
| DisplayInventory | Pass | 1 display, bounds, work area 1920x1032, DPI 96, scale 1. 6 ms. |
| Screenshot | Pass, with a note | Full, region, `zoom`, `display=[0]`, grid. Region/full 8-96 ms. **Once, the first full capture after the PC sat idle ~1.5 h used `pillow`** (R4-11); every later one used dxcam. |
| Snapshot | Pass, with notes | Region on own Notepad and Explorer windows only; labels, document value, `[focused]` correct. 175-323 ms. **Word elements' boxes include trailing spaces** (R4-3); a 20-line note is 134 word elements; words under Notepad's Find panel are still listed (R4-13). A region Snapshot's window list only holds windows inside the region. |
| FindText | Pass, with a note | "North 460 units" found across columns in a region (0.65 s) and full screen (1.24 s); click at (312,254) landed in "460" on the North row (Ln 4). Full screen joined a word of the neighbouring VS Code window into the line (".venv North 460 units", R4-9). |
| WaitFor | **Fail (text_exists)** | active_window 0.34-0.49 s, element_exists 0.26 s, element_enabled 0.25 s, screen_idle 1.01 s (settle 1), screen_text 0.60 s, screen_changed caught the clock minute in 12.9 s. **text_exists does not find a phrase inside a document** ("North leads the week" timed out; "leads" matched, R4-4); its timeout error does not name the active window. |
| Wait | Pass | 1 s took 1.01 s. |
| Click | Pass, with notes | loc 0.18 s; `element=` 0.26-0.30 s (tab, Replace all, Got it, message-box No); label; double 0.48 s. Reply named `document "Text editor"` when the click hit a Find-panel button (R4-8), and `in ""` for Edge's sign-in notice. |
| Type | **Fail (speed, caret)** | Single-line text 26-35 ms; replaces a selection (622 chars kept); `clear=true` exact. **Multi-line text 177 chars 7.5 s, 622 chars 26.2 s** (R4-1). **`caret_position="start"` put text at the start of the current (last) line** (R4-6). A read-back said 213 characters while Notepad showed 215 (R4-7). |
| MultiEdit | Pass | Find and Replace fields by label, 0.90 s for 2 fields (0.45 s each); "Replace all" then changed 410 to 405. |
| MultiSelect | Pass | Ctrl-selected data.csv + report.txt in Explorer ("2 items selected 145 bytes"), 0.43 s; plain clicks in sequence left the last item selected, 0.37 s. |
| Scroll | Pass, with a note | 0% -> end, back to 0% in a 360-px-high Notepad; 0.27-0.56 s. Position read mid-animation: "now at 87.3%" then the next call said "was 100%" (R4-7). |
| Move | Pass, with a note | Hover 0.15 s (showed the snap-layout panel); drag selected exactly notes 1-3 ("140 of 622 characters") but took 1.29 s. New-window note fired on a Move. |
| Shortcut | Pass | ctrl+a/c/z/h/w, shift+home, ctrl+shift+left, win+n, escape, BackSpace: 46-88 ms. |
| App | **Fail (launch reply)** | launch_executable notepad/explorer/msedge.exe (bare name via App Paths)/pwsh: 19-43 ms, returned a hand-off PID for notepad and explorer as the guide warns. resize exact (visible 1000x700 at 200,100 = DWM frame; outer 1010x705 at 195,100), minimize/restore/maximize/move/switch/close by handle and name: 72-176 ms; list 16-99 ms; display 1 and resizing a maximized window refused clearly. **launch "Notepad" took 2.26 s but named the existing "\*report.txt - Notepad" window while the new one was "Untitled - Notepad"** (R4-2). |
| PowerShell | Pass, with a note | CSV summary (total 1540), failing Get-Item as a tool error status 1, `success_exit_codes` [0,1] for findstr, non-terminating error under "Errors and messages:" with status 0. 0.35-0.47 s. **timeout=1 replied after 3.45 s, timeout=2 after 4.36 s** (R4-10); the WARNING line came back inline, not under the heading. |
| FileSystem | Pass | write (CRLF, 93 bytes checked), refusal without overwrite, append, read offset/limit, copy into a new folder, move/rename into a new folder, list, search (recursive 3 hits; top-only "No matches"), info file/folder (342 B total), delete refusal and recursive. 4-17 ms. |
| Registry | Pass | String (Unicode), ExpandString (raw `%TEMP%` kept, read via .NET), Binary 01,02,ff, DWord 0x27 = 39 Int32, MultiString JSON list, QWord 5000000000 Int64, `(Default)` on a new sub-key, missing value and bad DWord refused, value delete, sub-key guard, recursive key delete. 0.30-0.40 s. |
| Process | Pass, slow | memory 0.85-1.06 s, cpu 2.26-2.82 s, name+details 0.93 s (622 processes running); details hid a fake `-Token` (closing quote still eaten); kill by PID 7 ms, confirmed gone. |
| Clipboard | Pass | get text (6,041 chars), Unicode + emoji set checked by PowerShell `-ceq`, copy via Ctrl+C matched the typed report exactly. 4-7 ms. |
| Notification | Pass | Toast with the Explorer AppID; found in the notification centre by FindText. 1.20 s. |
| Scrape | Pass | HTTP with query ("2 of 137 paragraphs"), 0.30 s; 404 is a tool error; `use_dom` read the Edge tab, 0.32 s, but included Edge's sign-in notice twice. Avast did not block HTTPS. |

## Timing against the targets (ms, end to end)

On or under target: Shortcut 46-88, Clipboard 4-7, FileSystem 4-17, DisplayInventory 6, Screenshot 8-96, App list 16-99, single-line Type 26-35, MultiEdit 450 a field, MultiSelect 185-215 a click, WaitFor 250-600, Registry 303-401, FindText region 651-813 / full 1242, App launch 2258, Scrape 300-315.
Slower than target: **Type multi-line 42 per character (7494 for 177, 26177 for 622)**; Process memory 847-1064 (target 600) and cpu 2258-2819 (target 1700) with 622 processes (473 in round 3); Move drag 1285; Click double 475-486, Click `element=` 256-296 and plain 176 (target 150); Scroll 269-560 (target 300); PowerShell 354-473 (target 300); PowerShell timeout 2.4 s late; Snapshot region 175-323 (guide says under 100); Screenshot `display=[0]` 381 once; Notification 1197 (no target). No call froze or hung.

## Bugs

- **R4-1 (High) Multi-line Type is typed one key at a time.** Any text with a line break, tab or brace goes through `SendKeys` with a 0.04 s pause per key (`desktop/service.py` ~1153-1160): 177 characters took 7.5 s and 622 characters 26.2 s, against 26-35 ms for single-line text. The guide's "2,000 characters arrived intact" would take ~80 s. Typing a report or a code block is the common case.
- **R4-2 (Medium) App `launch` names the wrong window.** `_wait_for_launched_window` (`desktop/service.py` ~815-839) accepts any visible window whose title contains the app name, including ones open before the launch: `launch name=Notepad` replied "\*report.txt - Notepad launched." while the new window was "Untitled - Notepad". An agent typing next would write into the old document.
- **R4-3 (Medium) Snapshot word elements include trailing spaces.** In Notepad each word's box spans the spaces after it: "North" centre (261,255) against a drawn centre of 237, "460" (337,255) against 317; the last word of a line ("units") is exact. Click `label=` on "460" with `clicks=2` landed in the gap, selected the blanks, and the next Type gave "460460".
- **R4-4 (Medium) WaitFor `text_exists` misses text inside a text box or document.** "North leads the week" (in the Notepad document's value) timed out; the single word "leads" matched, so it compares element names only. The timeout error also omits the active window the guide promises.
- **R4-5 (Medium) The new-window note misses dialogs drawn inside the app's window.** Notepad's "Do you want to save changes to ...report.txt?" (Ctrl+W on the modified tab) was not named by the next input reply (Click `element="button:Save"`). A WinForms message box started by a hidden pwsh was named on the next Move ("WMCP R4 question", handle, pid), as were the new Explorer and Edge windows.
- **R4-6 (Medium) `caret_position` works per line.** "start"/"end" press Home/End (`service.py` ~1140-1143): with the caret on the last line, "start" put "DRAFT - " at the start of that line, not of the text; "end" on the title line appended to the title line. The tool description says "'start' (beginning)".
- **R4-7 (Low) Read-backs are taken before the app settles.** Type's "now reads ... (213 characters)" while Notepad showed 215; Scroll's "now at 87.3%" and "now at 83.8%" were followed by "was 100%" and "was 62%" on the next call (Notepad scrolls smoothly).
- **R4-8 (Low) Click names the element under an in-window flyout.** Clicks on Notepad's "Replace all" and "Exit Find and Replace" buttons (both acted) were reported as `document "Text editor"`; Edge's sign-in notice button was reported `in ""`.
- **R4-9 (Low) FindText joins lines across windows.** A full-screen search joined the VS Code side bar's ".venv" onto Notepad's "North 460 units" line; a phrase could be "found" across two unrelated windows.
- **R4-10 (Low) PowerShell timeout replies ~2.4 s late.** `timeout=1` with a 3 s sleep replied after 3.45 s; `timeout=2` with an 8 s sleep after 4.36 s (so the command is stopped, but late).
- **R4-11 (Low) A full Screenshot fell back to pillow after the PC sat idle.** The first full capture at 17:34 (after ~1.5 h idle) reported `Screenshot Backend: pillow` on a single display; the next full and `display=[0]` captures used dxcam. pillow is the method that missed Avast's alert in round 3, and the reply gives no reason.
- **R4-12 (Low) Some maximized windows are listed with their outer frame.** FactsERP shows `Maximized at (-8,-8) size 1936x1048` in App `list` and Snapshot while every other maximized window shows `(0,0) 1920x1032`.
- **R4-13 (Low) Snapshot lists elements hidden under an in-window panel.** With Notepad's Find & Replace panel open over the first lines, the words "Region", "North", "460" under it were still listed as clickable.
- **R4-14 (Low) Every server start writes a uv warning to stderr:** "The `extra-build-dependencies` option is experimental ..." from `[tool.uv.extra-build-dependencies]` in `pyproject.toml` (zero-warnings rule).
- **R4-15 (Low) Cosmetic:** the `redact` closing-quote loss seen in R3-I10 is still there; WaitFor writes Edge's zero-width space as a literal `​` (App list shows the real character); FileSystem folder info says "Contents: 1 files, 2 directories" (top level only, while Size counts subfolders).

## Improvements

- **R4-I1 Process list speed and CPU sort.** 0.85-1.06 s by memory, 2.3-2.8 s by CPU with 622 processes; the cost grows with the process count (round 3's 0.6 s was 473). "System Idle Process" (82-92%) always tops the CPU list.
- **R4-I2 Process `details=true` output size.** Command lines are not shortened and the table pads every row to the longest (an Edge GPU process line is ~1,900 characters): the 5-row Step 0 list was ~10,000 characters, mostly spaces.
- **R4-I3 Snapshot word elements.** A 20-line Notepad text is 134 `word` elements; the document element already carries the whole text as its value.
- **R4-I4 Fixed costs left:** Move drag 1.29 s (excluded from R3-I1), Click double 0.48 s, Notification 1.2 s.
- **R4-I5 Screenshot reply boilerplate.** Each screenshot reply carries empty "Active Desktop / All Desktops / Focused Window skipped / Opened Windows skipped" tables (~450 characters).
- **R4-I6 App `list` order.** Lines are not in front-to-back order and do not mark the front window.
- **R4-I7 Resize refusal hint.** "Restore it first (e.g. Shortcut win+down)" should point to App `mode="restore"`, which has no focus risk.

## New abilities

- **R4-N1 Caret to the start/end of the whole field** (Ctrl+Home / Ctrl+End) in Type, alongside the per-line start/end.
- **R4-N2 FindText limited to one window** (`window=` name or handle), so other windows neither match nor join lines.

## Guide check

Compared SKILL.md, the seven references, each tool's description and known-gaps.md with what the tools did. Every wrong, missing or outdated statement is item D.1-D.31 in `Plan/windows-mcp-open-issues-round4.md` with the line quoted. Main ones: `references/web.md` still sends the reader to known-gaps.md for the Edge full path (R3-I5 fixed that; bare `msedge.exe` works); nothing warns that multi-line Type is slow or that `caret_position` is per line; `text_exists` is described as finding text in a window; App `launch` "names the window found"; Process timings; the Snapshot tool description still says "Always call this first" and lists a "system language" it no longer returns; the tool-tester skill says Notepad's text area is not exposed (it is, as `document "Text editor"`) and that Type of 20+ characters uses the clipboard; the live-test skill's `FileShare ReadWrite` for Avast's log now fails (needs ReadWrite + Delete). Tool choice: the "Which tool for which job" table covers every scenario step, but does not say to write a document with FileSystem rather than typing it, or how to verify text inside a document.

## Environmental notes

- The user answered the hands-off question after ~1.5 h, so the input steps ran 17:34-17:45 (UI steps, then clean-up).
- Win11 Notepad restored five of the user's saved tabs into the test window; only the report tab was typed into, and closing the window left their five tab-state files in place (checked).
- Edge started with a throwaway `--user-data-dir` signed itself into the Windows Microsoft account and showed a "now syncing" notice over the page; the profile folder was deleted afterwards and no process of it remained.
- Nine windows-mcp servers (09:09-15:50, this session's included) were running, left by earlier Claude sessions; only this session's was used.
- Avast logged nothing during the session (last entry 06:35 UTC = 10:35 local); its log opened only with `FileShare` ReadWrite + Delete.
- Clean-up verified with PowerShell: `HKCU:\Software\WMCP-Test` gone, scratch folders gone, Notepad/Explorer/Edge/test pwsh closed by own handle or PID, clipboard equal to the backup.
