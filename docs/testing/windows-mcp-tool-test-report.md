---
Title: Windows-MCP tool test report (2026-09-22)
Description: Live test results for all 20 windows-mcp tools on the maintainer's Windows 11 PC, run from Claude Code against the local repo on 2026-09-22. Round 1 - a verdict per tool, the ten bugs found and fixed, and post-restart re-tests. Round 2 (after every round-1 item was fixed) - per-tool verdicts again, confirmation that all round-1 fixes held, and 49 new bugs (6 High - registry paths act as wildcards and reach the file system, Snapshot labels renumbered by WaitFor, off-screen points clamped and clicked, an on-top unfocused window gets no Snapshot elements, pop-up menus don't hide covered elements; 16 Medium; 27 Low), plus a comparison with Claude Cowork computer use giving 14 improvements and 8 new-tool ideas, with how each was verified. Round-2 backlog (all done) - Plan/completed/windows-mcp-open-issues-round2.md.
Tags: testing, qa, windows-mcp
Updated: 2026-09-22
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
