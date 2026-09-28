---
name: windows-mcp
description: Use when controlling this Windows PC via the windows-mcp tools (lcl-windows-mcp-*) — apps, UI clicks/typing, files, registry, processes, PowerShell, screenshots. Read before the first windows-mcp call.
---
# Windows MCP — field guide

## Which server

Claude Code and Claude Desktop on this PC both run the **local repo** build
(`uv --directory <repo> run windows-mcp serve`). This guide and its references describe it.

The **PyPI** release (`uvx windows-mcp`, other machines or configs) differs in many places:
read `references/pypi-differences.md` before using it. To tell them apart: local repo Snapshot
lines start with `[label:N]`, and its Screenshot has no window tables (one "UI Tree and window
list: skipped" line) where PyPI says "No active window found".

## This machine

- One display: 1920x1080 at 100% at the PC; 2560x1440 over Remote Desktop, where screenshots
  shrink to 1920x1080 (x0.75; see `references/input.md`, "Shrunk screenshots").
- PowerShell 7.6, Avast antivirus, a OneDrive-synced Desktop.

## Golden rules

1. **Approval prompts steal focus (Claude Desktop only; Claude Code has no approval pop-ups).**
   Each call the user approves brings Claude to the front, over the target window, unless
   windows-mcp is on "Always allow".
   - Coordinate clicks and typing can land in the Claude chat (a Type with Enter once sent a
     chat message); Shortcut goes to Claude.
   - Ask the user to Always-allow; set TopMost on windows you create; prefer PowerShell,
     FileSystem and Registry over UI automation.
   - Never `press_enter=true` unless a fresh screenshot shows the target on top at that spot.
2. **Verify by effect, never by the reply.** "Clicked / Typed / Sent" means the call ran.
   Check with the cheapest proof (see "UI workflow"). Failures are tool errors.
3. **Kill by PID, not by name.** Win11 Notepad runs every tab in one process, and a kill by
   name ends every process with that name. List first, then kill only a PID you launched.
   To close a window, use App `close` instead (by name, or `handle=` for same-named windows).
4. **Absolute paths only.** Relative paths resolve to the OneDrive-synced Desktop.
5. **Sandbox experiments** in `%TEMP%\<name>` and `HKCU:\Software\<TestKey>`, then clean up
   and confirm with `Test-Path`.
6. **Booleans:** pass real `true`/`false`. `"yes"/"no"/"1"/"0"/"on"/"off"` also work; any
   other word is an error.
7. **VS Code-family windows are never read.** One UI read pins VS Code at 100% CPU,
   "Not Responding" until restart, and returns nothing. Snapshot, WaitFor and App switch list
   VS Code, Cursor, Windsurf, Antigravity (`Antigravity IDE.exe`) and VSCodium by name only
   ("elements not read"): use Screenshot and coordinates for them. Never set
   `WINDOWS_MCP_READ_VSCODE=1`.
8. **Frozen apps are skipped**, so Snapshot, WaitFor and App switch still answer in ~0.2 s
   with a "Not Responding" app open. If one stalls anyway, run the frozen-app check in
   `references/observe.md` and ask the user to close or restart that app. Screenshot never
   hangs this way.

## Which tool for which job

| Job | Tool | Read |
|---|---|---|
| See the screen fast | Screenshot | observe.md |
| Elements, label ids, window list | Snapshot | observe.md |
| Text in apps with no UI tree (games, remote desktops, canvas) | FindText | observe.md |
| Wait for a window, text, element or screen change | WaitFor (not Wait) | observe.md |
| Monitor bounds, DPI, scale | DisplayInventory | observe.md |
| Click, type, scroll, drag, keys | Click, Type, MultiEdit, MultiSelect, Scroll, Move, Shortcut | input.md |
| Start, switch, resize, move, close windows | App | apps-windows.md |
| Commands, files, registry, processes | PowerShell, FileSystem, Registry, Process | system-tools.md |
| Clipboard, toast notifications | Clipboard, Notification | system-tools.md |
| Read a web page | Scrape | web.md |
| Write a document or report | FileSystem `write` (not typing it) | system-tools.md |
| Check text inside a document | WaitFor `text_exists` (or Ctrl+A, Ctrl+C, Clipboard `get`, after backing up the clipboard) | observe.md |

System tools have no focus problems: prefer them over the UI when both can do the job.

## UI workflow: cheapest step first

A Screenshot takes the server a fraction of a second but costs you seconds to read the picture; a text
reply costs almost nothing to read. Start on the lowest rung, climb one only when a step fails
or leaves doubt, and drop back down after it succeeds.

1. **No UI:** PowerShell, FileSystem, Registry or Process, when they can do the job.
2. **Act by name, no picture:** App switch or `launch_executable` (save the PID), WaitFor
   `active_window`, then Click `element=` with `window=`. Its spot check refuses when another
   window (an approval prompt) covers the target, so no Screenshot is needed first.
3. **Name unknown:** Snapshot of a `region` or the whole screen (text), then `label=`.
4. **No elements** (games, canvas, VS Code family) **or a text check failed:** Screenshot of a
   `region`; FindText for words.
5. **Region not enough:** full Screenshot, then `zoom=true` on a region for small text.

Check each step with the cheapest proof: Type's "now reads" line, a new-window or dialog note
in the reply, WaitFor `text_exists` / `element_exists` / `active_window`, or a file, registry
or process read. Screenshot only when none of these can show the effect.

Always take a fresh Screenshot first, on any rung, before a `loc` click or Type, Type with
`press_enter=true`, Type with no target, or Shortcut: these hit whatever is on top, which can
be an approval prompt (golden rule 1).

Clean up: kill only your own PIDs, remove sandbox files and keys, confirm with `Test-Path`.

## Typical cost per call

- Under 0.1 s: DisplayInventory, Clipboard, FileSystem, Registry, App list/switch,
  Screenshot, Shortcut.
- ~0.2-0.3 s Snapshot of a region; ~0.2 s WaitFor; ~0.3 s PowerShell (a new PowerShell each call).
- FindText ~0.6 s for a region, ~1.6 s for the full screen.
- Move ~0.1 s, Click ~0.15 s, Scroll ~0.5 s, MultiSelect ~0.2 s per click (a 0.1 s pause
  after each action; a slow app may need WaitFor `screen_idle` before a Screenshot).
  Double click ~0.25 s, Click `element=` ~0.3 s, Move drag ~0.5 s (longer with `duration`).
- Type without `loc` ~0.1 s for short text, under 1 s for 600 characters with
  line breaks; MultiEdit ~0.45 s per field;
  Process list under 0.05 s (~0.5 s sorted by CPU).

## References

Read only the one the task needs:

- `references/observe.md`: Screenshot, Snapshot, FindText, WaitFor, Wait, DisplayInventory,
  and the frozen-app check.
- `references/input.md`: Click, Type, MultiEdit, MultiSelect, Scroll, Move, Shortcut;
  coordinates, shrunk screenshots, what the replies report.
- `references/apps-windows.md`: App launch, switch, resize, minimize/maximize/restore, close,
  list, move, and how window names match.
- `references/system-tools.md`: PowerShell, FileSystem, Registry, Process, Clipboard,
  Notification.
- `references/web.md`: Scrape.
- `references/known-gaps.md`: what still goes wrong, with workarounds.
- `references/pypi-differences.md`: only when the server is the PyPI release.
