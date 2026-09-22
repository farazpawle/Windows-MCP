---
Title: Windows-MCP open issues backlog (from the 2026-09-22 tool testing)
Description: Every failing behaviour and every change still needed after three test sessions of all 20 windows-mcp tools on 2026-09-22. Collected only, nothing fixed, as the user asked. Grouped by priority, plus test-coverage gaps and seven actions missing compared with Claude computer use (Cowork), with the tool, what happens, why it matters and the suggested change, plus a standing task to update Skills/Skill.md as each fix lands. No freeze or server-crash issue is open: the frozen-app hang and the Avast HTTPS crash were fixed and committed (bf0137f). Source: docs/testing/windows-mcp-tool-test-report.md and Plan/windows-mcp-testing-tasks.md.
Total Tasks: 38
---

# Windows-MCP open issues

**Freeze / crash status:** none open. The frozen-app hang (Snapshot/WaitFor/App blocking on a "Not Responding" window) and the server abort on the first HTTPS request are fixed. The UIA focus WatchDog can still crash the server (#332), which is why it stays off by default. Leave it off.

## 1. High — can lose data or act on the wrong thing

- [x] 1.1 **FileSystem `write` ignores `overwrite=false`.** An existing file is replaced anyway. Fix: refuse the write when the file exists and `overwrite` is false. Done 2026-09-22.
- [x] 1.2 **FileSystem booleans:** the string `"yes"` counts as false. Fix: accept yes/no/1/0/on/off, or reject unknown strings with an error. Done 2026-09-22.
- [x] 1.3 **Process name filter is fuzzy.** "pwsh" matched ShellExperienceHost, so a kill by name could end the wrong process. Fix: exact (case-insensitive) name match for kill; keep fuzzy only for listing. Done 2026-09-22.
- [x] 1.4 **Registry key delete wipes all sub-keys** when `name` is omitted, with no warning. Fix: refuse to delete a key that has sub-keys unless an explicit `recursive=true` is passed. Done 2026-09-22.
- [x] 1.5 **Snapshot lists hidden elements.** Elements of background windows are listed even where another window covers them, so a click on one hits the covering window. Fix: drop or mark elements whose centre point belongs to another window (hit-test with WindowFromPoint). Done 2026-09-22 (fix/open-issues-backlog).
- [x] 1.6 **Snapshot / WaitFor / App switch can freeze VS Code.** Repeated full-desktop reads made a large VS Code window go "Not Responding" on 2026-09-22: Electron answers every accessibility query on its UI thread. Fix idea: skip or cap the element walk of background Electron windows, or default to the focused window only. Done 2026-09-22: proven that one read pins VS Code at 100% CPU until restart; VS Code-family windows are now listed by name only (override WINDOWS_MCP_READ_VSCODE=1). Full read went from 21.5 s to 0.2 s with VS Code idle.

## 2. Medium — wrong or misleading results

- [x] 2.1 **PowerShell drops errors when the exit code is 0.** Non-terminating errors (e.g. `Get-Item` on a missing path) vanish from the reply. Fix: include the error stream in the output. Done 2026-09-22: error stream decoded from CLIXML to plain text; the PowerShell tool appends it under `Errors:` even at exit 0 (internal callers still get stdout only, since they parse it).
- [x] 2.2 **PowerShell `timeout=0` fails every command.** Fix: treat 0 as "no timeout" or reject values below 1 with a clear message. Done 2026-09-22: values below 1 rejected with a clear error.
- [x] 2.3 **Registry binary values** accept a single byte only. Fix: accept a byte list or hex string. Done 2026-09-22: hex list, hex string or decimal JSON list; bad input refused before writing. Checked with reg.exe.
- [x] 2.4 **Notification toasts never appeared** on the user's screen although the call reported success. It also reports success for a made-up `app_id`. Fix: check Do Not Disturb, and validate the app id or report delivery failure. Done 2026-09-22: unknown app id and turned-off notification settings now return errors; reply notes Do Not Disturb can't be read. A real toast was seen on screen, so the original miss was most likely the app id.
- [x] 2.4b Check whether Do Not Disturb / Focus was on during the toast test. Done 2026-09-22 by the agent (no person needed): Do Not Disturb is off now (Windows notification state = accepts notifications; Focus profile = off), notifications are on for all apps, and toasts from both File Explorer's id (the one the earlier test used) and Windows PowerShell's id appeared on screen. The state at the time of the earlier test can't be read back, so the most likely cause of that miss was a temporary Do Not Disturb (an automatic rule such as full screen or a game) or the toast closing (~5 s) before anyone looked.
- [x] 2.5 **Screenshot says "No windows found" / "No active window found"** when the window list was simply not checked. Fix: say "Window list skipped (screenshot-only)". Done 2026-09-22.
- [x] 2.6 **Screenshot ignores grid lines** (`width_reference_line` / `height_reference_line`). Fix: draw them, or remove the parameters from Screenshot. Done 2026-09-22: grid drawn on plain screenshots too; either reference line alone works.
- [x] 2.7 **Scrape summary silently skipped.** With the default summary mode, clients that cannot summarise (Claude Code) get the raw page with no note. Fix: add "summary unavailable, raw content returned". Done 2026-09-22.

## 3. Low — replies and usability

- [x] 3.1 **Click with `clicks` outside 0–2** replies "None … clicked"; negative values single-click. Fix: validate the range and name 3+ correctly. Done 2026-09-22: 0-3 accepted (3 = triple click, verified in Notepad), anything else refused.
- [x] 3.2 **MultiSelect reply** says "multi-selected" even without Ctrl. Fix: word the reply by mode. Done 2026-09-22.
- [x] 3.3 **Snapshot text tree shows no label ids.** `label=N` can only be read from the annotated image. Fix: print the id next to each element. Done 2026-09-22: `[label:N]` printed on each element line; a label read from the text clicked the right Notepad menu.
- [x] 3.4 **Snapshot 500-element cap** is filled by a busy editor (VS Code) alone. Fix: prioritise the focused window before others. Closed 2026-09-22, no code change: the focused window is already read first, and since 1.6 VS Code-family windows are not read at all. Reproduced with VS Code and Antigravity in the background: a small focused Notepad got all its elements although the cap was hit.
- [x] 3.5 **App `switch`** needs a long title fragment to find a window. Fix: fall back to substring/process-name matching. Done 2026-09-22: title substring (invisible characters removed), then program name. "Edge" and "msedge" now switch to Edge.
- [x] 3.6 **Snapshot `region` still reads every window.** Found 2026-09-22: a Snapshot limited to a small Notepad area walked the whole desktop up to the 500-element cap, then trimmed to the region. Wasted time, and a busy background window can use up the cap. Fix idea: skip windows whose rectangle does not overlap the region before walking them. Done 2026-09-22: only windows whose visible frame (without invisible borders) overlaps the region are read; a taskbar-strip Snapshot went from 22 s (500-cap hit) to 0.3 s. While measuring this, a gap in 1.6 showed up: Antigravity runs as `Antigravity IDE.exe`, which the guard did not know, so it was read and froze (user restarted it). Name added.

## 4. Not yet tested / decisions

- [ ] 4.1 [User] **Full Scrape `use_dom` read.** A browser-lock extension on the user's Edge replaces new windows with an error page, and the agent will not work around it. Needs the user to open a test page in a browser tab.
- [ ] 4.2 [User] **Claude Desktop still runs the PyPI server** without these fixes. Only the user can change or approve its config.
- [x] 4.3 [User] **Commit the report and plan updates.** Done 2026-09-22 (1cb7d91, a55962a); `Skills/` is still untracked.

## 5. Test coverage gaps (tested lightly or not at all)

- [ ] 5.1 App `launch` (by Start Menu name) and `resize` modes — only `launch_executable` and `switch` were verified.
- [ ] 5.2 Snapshot `use_dom=true` (browser page elements) — never run; blocked by the same browser lock as 4.1.
- [ ] 5.3 Multi-monitor behaviour (`display=[0,1]`, flash border, coordinates) — this PC has one display.
- [ ] 5.4 Screenshot backends other than the automatic choice (`dxcam`, `mss`, `pillow` forced by setting).
- [ ] 5.5 Network modes (SSE and HTTP transports, bearer/OAuth login, IP allowlist) — only the local stdio mode was used.
- [x] 5.6 Compare the tool set with Claude Cowork's computer-use actions to find missing tools. Done — see section 6.

## 6. Missing compared with Claude computer use (Cowork)

Reference: Anthropic's published computer-use toolset (`computer_toolset_20260801`, 17 actions, platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool, read 2026-09-22). Cowork's own desktop implementation is not published action by action, so this API toolset is the closest official reference.

Already covered: screenshot (Screenshot), zoom (Screenshot `region` returns native-resolution pixels), right/middle/double/triple click (Click `button`/`clicks`), drag (Move `drag=true`), mouse move (Move), cursor position (shown in Screenshot output), scroll in four directions (Scroll), type (Type), key combos (Shortcut), wait (Wait).

- [ ] 6.1 **Click with a modifier held** (Shift+click to extend a selection, Ctrl+click on a link). Only MultiSelect can Ctrl-click; nothing can Shift-click or Alt-click. Suggest: a `modifiers` option on Click.
- [ ] 6.2 **Hold a key for a set time** (`hold_key`, e.g. hold an arrow key in a game or hold Shift). Missing. Suggest: a `hold` option on Shortcut with a duration cap.
- [ ] 6.3 **Separate mouse button down / up** for drags that one straight move can't express (curved paths, drag-and-hover-then-drop). Missing. Suggest: `press`/`release` modes on Move.
- [ ] 6.4 **Scroll or drag with a modifier held** (Ctrl+wheel to zoom a page or document). Missing. Suggest: the same `modifiers` option on Scroll and Move.
- [ ] 6.5 **Repeat a key N times** (`key` with `repeat`, e.g. press Down 20 times). Missing; each press needs its own call. Suggest: a `repeat` option on Shortcut.
- [ ] 6.6 **Click or type at the current position / current focus.** Click and Type both require `loc` or `label`; typing into an already-focused field forces an extra click that can move the caret or change the selection. Suggest: allow both to run without a location.
- [ ] 6.7 **Wait takes whole seconds only.** Half-second waits are not possible. Suggest: accept decimals.

Beyond the screen tools, Cowork also works with files, connectors and a built-in browser. windows-mcp covers files (FileSystem) and pages (Scrape) differently, and has extras Cowork's screen tools lack: the UI element tree (Snapshot), WaitFor, MultiEdit, PowerShell, Registry, Process, Clipboard, Notification and App.

## 7. Keep the agent guide in step with the fixes

- [ ] 7.1 After each item above is fixed or added, update `Skills/Skill.md` in the same change: remove the workaround or warning it described, and document any new option (e.g. Click `modifiers`, Shortcut `hold`/`repeat`, Type without a location) with when to use it.
- [ ] 7.2 At the end of the implementation, re-read `Skills/Skill.md` end to end and confirm every claim still matches the tools' real behaviour.

## Not a bug

- **Orange capture border covers only part of the screen in these tests.** The border outlines exactly the area captured. These tests captured small regions (`region=[...]`), so the border was small. A full-screen capture, as Claude Cowork does, gets a full-screen border. Set `WINDOWS_MCP_DISABLE_FLASH=1` to turn it off.

# Implementation verification

- Each fix gets a failing test first, then passes; the full suite stays green (`.venv/Scripts/python.exe -m pytest -q`) and `ruff check .` is clean.
- Each fix is re-checked live with a different tool than the one fixed (PowerShell, the harness state file, or a registry/file read).
- Acceptance: every item above is either fixed and ticked, or explicitly declined by the user.
