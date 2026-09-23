---
name: windows-mcp-live-test
description: >
  Prove a Windows-MCP code change on the real desktop: real clicks, keys, scrolls and UI-tree reads sent by an in-process server to a guarded throwaway test window.
  Use after changing input, Snapshot/WaitFor or App behaviour, or when unit tests can't show it works. Triggers: live test, real desktop, test window, harness.
  Read lines 11–24 of SKILL.md first to confirm scope.
---

# Windows-MCP Live Test

## Scope Gate — Read First (Lines 11–24)

**This skill IS for:**
- Checking a code change in this repo against the real desktop before calling it done
- Writing and running a live-test script with the guarded test window and in-process server
- Multi-monitor, focus, IME, clipboard or modifier-key behaviour that mocks cannot prove

**This skill is NOT for:**
- Black-box QA of one tool through its MCP schema (use `windows-mcp-tool-tester`)
- Plain unit tests (`pytest`), or using the tools for a user's task (see `Skills/Skill.md`)

**Matches → keep reading. No match → stop.**

---

## Why a script, not the connected tools

The MCP server Claude Code is connected to runs the code from when it started, so it does
not show an uncommitted fix. `scripts/livetest.py` builds a fresh server from the working tree
(`_build_mcp`) and calls it through a FastMCP client. The same client can send inputs the
Claude Code client cannot, such as an empty string.

## 1. Before the run (tell the user, in one message)

1. Say how long it takes and **ask them to keep off mouse and keyboard**. The PC is their
   working machine; a run done while they typed hit the wrong window and had to be repeated.
2. Warn that an **Avast "allow/block" pop-up** may pause the script (Behavior Shield flags a
   Python script that moves windows and sends input): they should pick **Allow**. To confirm
   afterwards, read `C:\ProgramData\AVAST Software\Avast\log\detections.log` (open with
   FileShare ReadWrite; timestamps are **UTC**) for "show and wait for user choice".
3. If the test overwrites the clipboard (Clipboard set, copy shortcuts), back it up right
   before that step and restore it after, every time. Non-text contents cannot be restored:
   ask first. Type restores the clipboard itself after a paste of 20+ characters.
4. If the test reads the UI tree (Snapshot, WaitFor, App switch/resize), check for
   "Not Responding" windows first; one can stall the read:
   `Add-Type -Name U -Namespace W -MemberDefinition '[DllImport("user32.dll")] public static extern bool IsHungAppWindow(IntPtr h);'; Get-Process | ? { $_.MainWindowHandle -ne 0 -and [W.U]::IsHungAppWindow($_.MainWindowHandle) } | select Id,ProcessName,MainWindowTitle`

## 2. Write the script (session scratchpad, never the repo)

```python
import asyncio
from pathlib import Path

from livetest import center, close_window, guarded_call, mcp_client, read_settled, start_window

LOG = Path(__file__).with_name("harness.log")


async def main(hwnd):
    x, y = center(hwnd)
    async with mcp_client() as c:
        await guarded_call(c, hwnd, "Click", {"loc": [x, y]}, points=[(x, y)])  # focus it first
        await guarded_call(c, hwnd, "Type", {"text": "héllo 🌍"}, keyboard=True)
        await guarded_call(c, hwnd, "Shortcut", {"shortcut": "ctrl+a"}, keyboard=True)


proc, hwnd = start_window("LiveTest320", LOG, textbox=True)
try:
    asyncio.run(main(hwnd))
    print("typed:", repr(read_settled(Path(f"{LOG}.text"))))
    print("events:", read_settled(LOG))
finally:
    close_window(proc, hwnd)
```

Helpers (`scripts/livetest.py`):

| Helper | What it does |
|---|---|
| `start_window(title, log, rect=, textbox=, seconds=)` | Opens `scripts/test_harness.ps1`: a visible TopMost window that logs every key, click and wheel with the modifiers held (`key F5 held=[ctrl]`, `hwheel -120 held=[alt]`). `textbox=True` adds a text box whose content goes to `<log>.text`. It closes itself after `seconds`. |
| `guarded_call(c, hwnd, tool, args, points=, keyboard=)` | Calls the tool only if every point is on the test window and, for keyboard input, the window is in front; otherwise aborts. Use it for **every** input call. |
| `read_settled(path)` | Reads the log once it stops changing and retries while the file is locked. The window lags behind fast input, so an early read under-counts. |
| `center`, `on_window`, `close_window`, `mcp_client` | Window centre point, the WindowFromPoint check, clean close by own handle, in-process client. |

Read-only calls (Snapshot, WaitFor, DisplayInventory) need no `points`. Give Snapshot a
`region` around the test window so it does not read other apps. Snapshot, WaitFor and App
always skip VS Code-family windows; never set `WINDOWS_MCP_READ_VSCODE`, because one read
freezes VS Code until restart.

For UI other than the log window (a real Notepad, Explorer, a browser tab): start it yourself,
record its PID, target it with `guarded_call` using its own hwnd, and kill only that PID (a Win11
Notepad PID can be a stub that exits; find the real one before killing).

## 3. Run it

```bash
cd "<repo root>" && timeout 180 env -u SSLKEYLOGFILE \
  PYTHONPATH="<repo root>/.claude/skills/windows-mcp-live-test/scripts" \
  uv run --no-sync python "<scratchpad>/live_x.py"
```

- `env -u SSLKEYLOGFILE`: Avast injects it, and the FastMCP client's OpenSSL then aborts.
- `--no-sync`: a running server from this `.venv` locks `windows-mcp.exe`.
- Always use `timeout`, and announce the run first. A script that hangs leaves the user watching
  a silent spinner.

## 4. Judge and report

- Judge by what the test window logged or holds, never by the tool's reply text alone.
- If the guard aborted, nothing was sent: re-check focus and window position, then re-run.
- Report the result in plain words. Record any new lesson in this skill, and any behaviour
  change in `Skills/Skill.md`, in the same task (CLAUDE.md "Skills and Keeping Them Current").

## Multi-monitor tests (this PC has one screen)

A temporary virtual screen works without a reboot: the signed "Driver.Only" build of
VirtualDrivers/Virtual-Display-Driver (hardware id `Root\MttVDD`), installed through SetupAPI
(pnputil cannot create a root device), with `vdd_settings.xml` in `C:\VirtualDisplayDriver\`.
It adds an 800x600 screen to the right. Install and removal each need **admin: the user must
click Yes on UAC**, so ask before every install. Remove with `pnputil /remove-device /deviceid
Root\MttVDD` and `pnputil /delete-driver <oemNN> /uninstall`, and move test windows back first.
