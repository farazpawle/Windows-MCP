---
Title: Windows-MCP tool test report (2026-09-22)
Description: Live test results for all 20 windows-mcp tools on the maintainer's Windows 11 PC, run from Claude Code against the local repo over two sessions on 2026-09-22. Gives a pass/fail verdict per tool, the ten bugs found and fixed (frozen-app hang, emoji typing and paste, empty Type text, stuck Ctrl after a bad shortcut, horizontal scroll, WaitFor text_exists missing static text and ignoring window_name, clear on legacy edit boxes, OpenSSL abort from Avast's SSLKEYLOGFILE, Scrape HTTPS rejected under Avast), the issues still open, the post-restart re-tests (emoji typing and Scrape pass; use_dom only partly tested), and how each result was verified.
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
