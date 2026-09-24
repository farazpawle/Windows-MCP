---
Title: Windows-MCP tool test report (2026-09-22 to 2026-09-24)
Description: Live test results for all 20 windows-mcp tools on the maintainer's Windows 11 PC, run from Claude Code against the local repo on 2026-09-22. Round 1 - a verdict per tool, the ten bugs found and fixed, and post-restart re-tests. Round 2 (after every round-1 item was fixed) - per-tool verdicts again, confirmation that all round-1 fixes held, and 49 new bugs (6 High - registry paths act as wildcards and reach the file system, Snapshot labels renumbered by WaitFor, off-screen points clamped and clicked, an on-top unfocused window gets no Snapshot elements, pop-up menus don't hide covered elements; 16 Medium; 27 Low), plus a comparison with Claude Cowork computer use giving 14 improvements and 8 new-tool ideas, with how each was verified. Round-2 backlog (all done) - Plan/completed/windows-mcp-open-issues-round2.md. Round 3 (2026-09-24) - all 21 tools in a real-work scenario plus per-tool timings: 2 High bugs (windows that cannot be maximized missing from the window list; a full-screen capture missing Avast's front alert), 2 Medium, 5 Low, 9 improvements, 1 new ability; an Avast alert traced to another app; backlog Plan/windows-mcp-open-issues-round3.md.
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
