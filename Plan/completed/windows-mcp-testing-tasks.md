---
Title: Rigorous windows-mcp testing and Skills guide validation
Description: DONE 2026-09-22 (remaining items resolved in Plan/completed/windows-mcp-open-issues.md). Original task (2026-09-22) — rigorously test every windows-mcp tool in Claude Code and check whether Skills/Skill.md (written in Claude Desktop) steers agents to the right tool in the right scenario. Scope agreed with the user — all 20 tools, focused on the guide's claims and main risks, sandboxed destructive tests only (temp folder, HKCU:\Software\WMCP-Test, self-launched PIDs), guide changes applied only after approval. Done so far — capture/system/input tools tested, guide corrected for capture/system tools, the frozen-app hang fixed and proven live, and four input bugs fixed with tests (emoji typing, emoji paste, empty text, stuck Ctrl after a bad shortcut). All uncommitted. Session 2 also fixed horizontal scroll, WaitFor text_exists, clear on legacy edit boxes and a server-killing OpenSSL abort caused by Avast (all uncommitted, 632 tests pass), and wrote docs/testing/windows-mcp-tool-test-report.md. Session 3 ran the post-restart re-tests: emoji Type and Scrape pass; use_dom only partly (browser-lock extension). Remaining — decide on Claude Desktop config, the open issues in the report (FileSystem overwrite, hidden elements, toasts), and committing the report/plan changes.
Total Tasks: 26
---

# Tasks

## 1. Capture tools — DONE
- [x] 1.1 DisplayInventory, Screenshot (params, bad display index, grid lines), Snapshot (text, vision, display filter).
- **Findings:** Screenshot's "No windows found" means not checked; Screenshot ignores grid lines; Snapshot hit the 500-element cap on VS Code words alone.

## 2. System tools — DONE
- [x] 2.1 FileSystem, all 8 modes. `write` ignores `overwrite=false`; string `"yes"` counts as false.
- [x] 2.2 Registry, every type. Binary accepts a single byte only; key delete wipes sub-keys with no confirmation.
- [x] 2.3 PowerShell. Errors are dropped when the exit code is 0; a timeout really stops the command; `timeout=0` fails every command.
- [x] 2.4 Process and App launch_executable. The fuzzy name filter matched ShellExperienceHost for "pwsh"; kill by PID verified.
- [x] 2.5 Clipboard. Unicode and multi-line round-trip; the user's clipboard was restored.

## 3. Frozen-app hang fix — DONE (uncommitted)
- [x] 3.1 Root cause: the legacy CUIAutomation has no call timeout, so the hung Antigravity window blocked Snapshot/WaitFor forever.
- [x] 3.2 Fix: CUIAutomation8 with 2 s / 5 s timeouts, ERROR_TIMEOUT mapped to UIATimeoutError and not retried, and hung windows skipped. Tests: tests/test_uia_timeouts.py, tests/test_hung_windows.py.
- [x] 3.3 Claude Code's user-scope windows-mcp server now runs the local repo.
- [x] 3.4 Committed with all session-2 fixes as bf0137f on branch fix/uia-hang-and-input-bugs (not pushed). Plan/ and Skills/ left untracked.
- [x] 3.5 [User] Decide whether to point Claude Desktop at the local repo too. Done 2026-09-22 (first backlog item 4.2: Claude Desktop now runs the local repo). Only the user can edit or approve Claude Desktop's config.

## 4. Input tools — DONE (2026-09-22, second session)
- [x] 4.1 [User] Restart Claude Code so the fixed local server is live.
- [x] 4.2 [User] Stay hands-off for about 10 minutes while the tests run.
- [x] 4.3 WinForms harness in %TEMP%\wmcp-test (harness.ps1; state.json is UTF-8 with code units; `WMCP_LEGACY=1` skips EnableVisualStyles).
- [x] 4.4 Click: left/right/middle, clicks 0/1/2/3 all correct. `clicks=-1` silently single-clicks and replies "None left clicked". `label=0` resolved to the harness Close button, not the first tree line: the text tree shows no ids, so labels are only readable from the annotated image.
- [x] 4.5 Type: caret start/end, press_enter, accents and CJK pass. Bugs: emoji truncated (fixed), long-text paste cut the emoji and dropped the NUL (fixed), empty text cleared the box then raised "string index out of range" (fixed). `clear=true` uses Ctrl+A, which legacy Win32 EDIT boxes (no visual styles) ignore: it deletes one char and appends.
- [x] 4.6 Scroll vertical passes (3 wheels = 360 px). Horizontal is Shift+wheel, which native apps treat as vertical: "right" scrolled the panel down. Move hover, drag with from_loc and drag from current position (with duration) pixel-exact. Shortcut combos pass; an unknown key name left Ctrl stuck down (fixed: rejected before any key is sent). MultiSelect ctrl true/false correct (reply says "multi-selected" either way). MultiEdit passes, replaces existing text.
- [x] 4.7 WaitFor with a frozen Settings window present: active_window, element_exists, focused_element, element_enabled each ~0.2 s; timeout returns cleanly at 10 s. Bug: text_exists only searches interactive/scrollable nodes and window titles, so plain static text (a label) is never found, and window_name is ignored for it. Wait(3) took 3.4 s.
- [x] 4.8 Fixed and tested: surrogate pairs in SendUnicodeChar, UTF-16 sizing in SetClipboardText, empty SendKeys no-op, unknown key names rejected up front. Tests: tests/test_key_input.py. The Clipboard tool uses pywin32 and was never affected.
- [x] 4.9 Bad-shortcut fix re-tested live through the reconnected server (clean error, Ctrl not held).
- [x] 4.9b [User] Close every Claude Code session (VS Code AND the one inside Antigravity), then reopen. Only the user can restart the host. Why both: the Antigravity session started 11:02, before the config switch, and still runs the PyPI server; and after the truststore dependency was added, `uv run` must reinstall the local package, which fails ("windows-mcp.exe being used by another process") while any old local server is running. If the server still fails to connect, end leftover local `windows-mcp.exe` processes and retry.
- [x] 4.9c After the restart, re-test emoji typing through the Type tool and Scrape (HTTP, use_dom, use_sampling=false). Session 3: short and long (paste) emoji text arrive exactly; clipboard restored.
- [x] 4.10 User chose to fix all four. Done: horizontal scroll (ScrollPattern, horizontal-wheel fallback), text_exists (FindFirst substring search, window_name respected), clear on legacy boxes (ValuePattern fallback). The "region" item was a mis-finding: region filtering works, but occluded background-window elements are still listed (open issue, needs a decision).

## 5. Web and notifications — DONE (use_dom partly)
- [x] 5.1a Scrape: any HTTPS request aborted the server via Avast's SSLKEYLOGFILE (fixed, tests/test_ssl_keylog_env.py). HTTPS still fails strict certificate checks under Avast; truststore fixes it in a test (pending user decision).
- [x] 5.1b Notification sent through the tool; call reported success.
- [x] 5.1c [User] Confirm the toast appeared — user saw no toast (recorded as open issue).
- [x] 5.1e User approved truststore: Scrape now verifies via the Windows cert store (tests/test_scrape_tls.py); live: example.com loads, expired cert refused.
- [x] 5.1d After restart: Scrape HTTP, use_dom on an open tab, use_sampling=false. HTTP/HTTPS pass, expired cert refused; default sampling silently falls back to raw (Claude Code has no sampling); use_dom gives a clean "open the page first" reply.
- [x] 5.1f [User] Optional: full use_dom read. Done 2026-09-22 by the agent in a new tab (first backlog item 4.1). Needs a browser tab the agent can open; a browser-lock extension on the user's Edge replaces new windows with an error page, and the agent will not work around it.

## 6. Report — PARTLY DONE
- [x] 6.1a Test report written: docs/testing/windows-mcp-tool-test-report.md.
- [x] 6.1b Skills/Skill.md updated with the input-tool, WaitFor, Scrape and Notification findings (user approved).

# Implementation verification
- Every mutating call is verified with a different tool (PowerShell, harness state.json, or Screenshot), never the tool under test.
- The full test suite passes (`.venv/Scripts/python.exe -m pytest -q`, 611 passing on 2026-09-22) and ruff reports no new issues.
- Cleanup is confirmed: the temp folder and test registry key are gone, test PIDs are gone, and the clipboard is restored.
- Acceptance: every tool has a pass/fail verdict, and every wrong or missing claim in Skills/Skill.md is corrected.
