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
- Plain unit tests (`pytest`), or using the tools for a user's task (see `Skills/windows-mcp/`)

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
   FileShare `ReadWrite, Delete`: plain `ReadWrite` fails with "being used by another process";
   timestamps are **UTC**) for "show and wait for user choice".
   Before blaming the test for a "powershell.exe ... IDP.HELU ... Command line detection"
   alert, list every running `powershell.exe` with its command line: on 2026-09-24 it was
   another app's hidden tray script, and three OCR runs with no exception raised nothing. An
   unanswered alert comes back each time it is closed with X; never suggest a PowerShell-wide
   exception, and warn that Quarantine targets Windows' own powershell.exe. Avast's "More
   options" did not react to the tool's clicks ("See details" did), so that choice is the user's.
3. If the test overwrites the clipboard (Clipboard set, copy shortcuts), back it up right
   before that step and restore it after, every time. Text, an image (`clipboard.service`
   `save_image` then `set_image`) and a file list (`set_files`) can be restored; other formats
   (HTML, Office data) cannot, so ask first. Type never uses the clipboard. Check an empty clipboard with `EnumClipboardFormats(0) == 0`: pywin32's
   `CountClipboardFormats` raises on 0 instead of returning it.
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
| `start_window(title, log, rect=, textbox=, scrollbars=, buttons=, seconds=, fixed_dialog=, shifting_list=)` | Opens `scripts/test_harness.ps1`: a visible TopMost window that logs every key, click and wheel with the modifiers held (`key F5 held=[ctrl]`, `hwheel -120 held=[alt]`). `textbox=True` adds a text box (Tab types a tab) whose content goes to `<log>.text`, read back with `\n` line breaks; the box itself stores CR LF, so Type's read-back counts each line break twice; right after a long Type the box is busy rewriting that file on every key and its scroll position may be unreadable, so for a Scroll test fill it with `WM_SETTEXT` to its child hwnd instead of typing; there, clicks and vertical wheel are still logged but horizontal wheel is not, and a double-click shows as two `lbutton` lines. Typed Unicode text logs as `key Packet` lines, so check the text in `<log>.text`. `scrollbars=True` gives the text box a vertical scroll bar (a UIA ScrollPattern; read its position independently with win32 `GetScrollInfo(box, SB_VERT)`). `buttons=("OK", "Save")` adds a row of real buttons (UIA type "button"); each click logs `click <name>`. `fixed_dialog=True` makes it a fixed-size dialog with no Maximize/Minimize (UIA CanMaximize False). `shifting_list=True` (with `buttons`) stacks the buttons as a list, and the first click on the first one inserts an "Inserted" row above the second (logged `inserted row`), so later rows move down: a stale-label test. It closes itself after `seconds`. |
| `control_center(hwnd, text)` | Screen centre of the test window's child control with that text (a harness button), for `guarded_call` points when the tool picks the spot itself. |
| `guarded_call(c, hwnd, tool, args, points=, keyboard=)` | Calls the tool only if every point is on the test window and, for keyboard input, the window is in front; otherwise aborts. Use it for **every** input call. |
| `read_settled(path)` | Reads the log once it stops changing and retries while the file is locked. The window lags behind fast input, so an early read under-counts. |
| `center`, `on_window`, `close_window`, `mcp_client` | Window centre point, the WindowFromPoint check, clean close by own handle, in-process client. |

The harness text box has no UIA TextPattern, so Snapshot lists no `word` elements for it. To
test word elements, open a throwaway WPF window instead (PowerShell `-STA`,
`Add-Type -AssemblyName PresentationFramework`, a `Windows.Controls.TextBox` inside a `Grid` as the
content, kill its own PID after): its words are listed. Without the Grid the window's UIA Name is
the box's text, not its title, so `window_name` matching fails. A single click on a word label then Type "X"
shows where the click landed without touching the clipboard.

To prove a double click or drag selected text (not just that clicks were logged): Type one
long word into the harness text box, double-click it or drag across it (the box's child Edit
rect from `EnumChildWindows`), then Type "X": `<log>.text` is exactly "X" only if the word was
selected. No clipboard needed (R4-I4, 2026-09-26).

The harness text box ignores Ctrl+A (it is a multiline WinForms box), so Ctrl+A then
Backspace deletes only the last character: compare the new tail, or use a fresh window per case.

Snapshot's text block reaches the client JSON-escaped (`button \"Alpha\"`, line breaks as a
literal `\n`): undo both before matching element lines with a regex, or it finds nothing or
reads the whole block as one line. Save the text to a file and read it before typing into a
label chosen by regex: twice a wrong match sent text to the wrong control.

Real apps: Edge with `--app=<file URL> --user-data-dir=<scratchpad>` gives a throwaway web
page in its own process (kill it with `taskkill /T /PID`); its elements appear to UIA only
after a first query, so retry Click `element=` once. The throwaway profile signs itself into
the Windows Microsoft account and shows a "now syncing" notice over the page (Scrape
`use_dom` then returns the notice's text): click its "Got it" first. That notice can be an
untitled top-level msedge window over the page centre, so `guarded_call`'s point check aborts
there: check instead that the window at the point belongs to the throwaway Edge's process tree.
The first `use_dom` read (Scrape, Snapshot, WaitFor) of a fresh page usually comes from the
IA2 fallback, since Chromium builds its UIA tree only once asked: a UIA-path fix shows only
from the second read on, so read at least twice (tell them apart with
`windows_mcp.tree.service` INFO logging: "IA2 fallback for ..."). Use `--app`: with
`--new-window` the synced profile opens extension welcome tabs in front of the test page
(R5-1, 2026-09-28).
**Never time other tools with a throwaway profile open:** from ~30-40 s after its start
(sign-in and sync) every UIA call on the PC slows 10-30x (App list/switch by name ~1.4 s
instead of ~0.08 s) until it closes (R6-4, 2026-09-28). `explorer.exe <scratch folder>` opens a
window titled "<folder> - File Explorer" (explorer.exe is shared: close it by WM_CLOSE, never
kill). Never Type `clear=true` into an Explorer file list: it sends Ctrl+A then Backspace,
which navigates up a folder. Explorer's right-click menu is a separate "Pop-upHost" window
of the same explorer.exe process: before clicking in it, check the front window's PID matches
the test Explorer window's. It leaves the clipboard changed ("Copy as path"): back it up first.

Read-only calls (Snapshot, WaitFor, DisplayInventory, FindText) need no `points`. For pixel
checks (WaitFor `screen_changed` / `screen_idle`, FindText), open a plain test window first and
give a `region` inside its client area: anything else on screen (the Claude Code panel's
spinner, a clock) changes pixels and spoils the result. A see-through WinForms window
(`Opacity` < 1) shows in pillow captures too, so it cannot stand in for the Avast alert pillow
missed (round-3 R3-2); a full capture on one screen uses dxcam now.
Windows OCR drops words for some crops of the same pixels (R5-4: "460" lost when the window
edge moved 2-4 px), so one live FindText proves little: save one screenshot, then run
`ocr.service.read_lines` + `find_phrase` offline on 20-60 crops jittered by a few pixels and
count misses (~0.6 s a read, no screen needed). Give Snapshot a
`region` around the test window so it does not read other apps. Snapshot, WaitFor and App
always skip VS Code-family windows; never set `WINDOWS_MCP_READ_VSCODE`, because one read
freezes VS Code until restart.

For UI other than the log window (a real Notepad, Explorer, a browser tab): start it yourself,
record its PID, target it with `guarded_call` using its own hwnd, and kill only that PID (a Win11
Notepad PID can be a stub that exits; find the real one before killing).

**Windows 11 Notepad is never a throwaway window.** Even with no Notepad running, the first
one started restores the user's earlier tabs (unsaved notes, saved files). On 2026-09-24 a
clean-up WM_CLOSE on that window raised "save changes to Untitled.txt?" over the user's own
notes. Close only the tab the test opened (switch to it, Ctrl+W), never the window, and never
kill Notepad. If a save prompt does appear, choose Cancel: nothing of the user's is changed.
To get Notepad's "save changes?" question safely: App `launch name=Notepad` (the reply gives the
new window's handle), App `switch handle=` (a launched window is not always put in front, and
`guarded_call` then aborts), Type one letter, Ctrl+W, then press the dialog's "Don't save"
through UIA (`FindFirst` by name, `GetInvokePattern().Invoke()`): only the test tab is lost.
The question is a UIA element inside the window (`IsDialog`), not a window of its own.
Never judge typing accuracy in Notepad: its auto-correct changes words ("charlie" ->
"Charlie") and garbles fast typed text after one (R4-16); use the harness text box, and in
Notepad type short text without spaces. Before each live run after a pause, check the user is
not working in another window: the guard aborted a run on 2026-09-25 because they were.
Ctrl+H/Ctrl+F do nothing in an empty tab (Find and Replace needs text): click the page, Type
one letter, then Ctrl+H. After typing, the title is `*x - Notepad`, no longer "Untitled", so
match the tab by handle, not by that title.
If App `launch name=Notepad` says "window not detected yet", check for a **suspended** Notepad
(psutil status `stopped`, WM_NULL times out, UIA reads fail with 0x80131505): the launch was
handed to it. Only a force-end clears it (ask first; its tabs come back from Notepad's session).
When Notepad opens with the user's restored tabs (some named "Untitled", so a title check is
not enough): press OK on any "Cannot find ... file" message, invoke the "Add New Tab" button
through UIA, take the one tab whose runtime id is new, and before every key check that the
selected TabItem has that id; close it with Ctrl+W and "Don't save" (R4-13 runs, 2026-09-25).
Notepad's Find panel is a XAML island child window drawn on top by the compositor, yet it sits
below the document in the stacking order: WindowFromPoint under it returns `RichEditD2DPT`.
A safer Notepad test tab: with Notepad already open, a second App `launch name=Notepad` opens a
separate window holding one fresh tab (round 5, 2026-09-26); type only there, closing its tab
closes that window, and the user's window is never touched.
For a read-only or scroll test with a long document (R6-5, 2026-09-28), `notepad.exe <scratch
file>` opens the file as its own tab (restoring the user's tabs if Notepad was closed): the
title is `<file> - Notepad` while it is selected; check that before every input, and Ctrl+W
closes it with no question as long as nothing was typed. Leave the window open.
**Never run `pytest` while a user's document is in front** unless `tests/conftest.py`
`_no_real_input` is in place: before it existed, a run typed "hi"/"new" into the front window.
Check the screen size with DisplayInventory first (1920x1080 in rounds 4-5, 2560x1440 once):
above 1920x1080 the server scales coordinates (x0.75 at 2560x1440), so run with
`WINDOWS_MCP_RAW_COORDINATES=1` when the script passes win32 screen pixels.
To put a window App `list` does not list in front without a click (R5-I3, 2026-09-28): Win+B
focuses the taskbar tray (`Shell_TrayWnd`), then Enter opens the hidden-icons panel
(`TopLevelWindowForOverflowXamlIsland`); Escape twice closes it, and focus stays on the taskbar.
Starting `test_harness.ps1` yourself (not through `start_window`) for a connected-tool test
opens a visible console window per harness; input replies then name it as a new window.

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
- For anything slow (App launch waits up to ~15 s), write each result to a log file with a
  timestamp and add `faulthandler.dump_traceback_later(40, exit=True, file=...)`. Several runs
  piped through `| cut` printed nothing at all, and repeating them wasted the user's time
  and left Calculator windows open. If a run prints nothing, find out why before running again.
- Add `2>/dev/null` when a call is expected to fail: the server logs each tool error as a long
  boxed traceback on stderr, which buries the script's own prints (it cost a repeat run).

## 4. Judge and report

- Judge by what the test window logged or holds, never by the tool's reply text alone.
- If the guard aborted, nothing was sent: re-check focus and window position, then re-run.
- Report the result in plain words. Record any new lesson in this skill, and any behaviour
  change in `Skills/windows-mcp/references/`, in the same task (CLAUDE.md "Skills and Keeping Them Current").

To test a lost screen duplication (what a lock or long idle does to dxcam) without locking:
make the camera's `_duplicator.update_frame` return False once (dxcam's own ACCESS_LOST
path), then capture. Releasing the duplicator instead makes it crash with an AttributeError
that a real loss never gives.

## Display-scaling tests

`scripts/dpi_check.py` (run as in section 3, hands off, ~30 s) checks Snapshot centres, label
Clicks, Move and Screenshot region sizes on a 3-button test window at the current scaling and
prints `RESULT: PASS`/`FAIL` with the monitor DPI. Passed at 100%, 125% and 150% on 2026-09-24.
The test window is DPI-unaware (it reports DPI 96 and Windows stretches it), so this covers the
harder case, stretched apps. Scale changes from Settings apply at once; no sign-out needed. Over
Remote Desktop the session's scaling comes from the connecting client, so change it at the PC itself.

## Multi-monitor tests (this PC has one screen)

A temporary virtual screen works without a reboot: the signed "Driver.Only" build of
VirtualDrivers/Virtual-Display-Driver (hardware id `Root\MttVDD`; release 25.7.23's
`VirtualDisplayDriver-x86.Driver.Only.zip` is in fact the x64 build, signed by SignPath
Foundation). It adds an 800x600 screen to the right. `scripts/virtual_display.ps1` does it all:
`-Install -Source <unzipped VirtualDisplayDriver folder>` (copies to `C:\VirtualDisplayDriver\`,
trims the settings to 800x600, creates the root device through SetupAPI since pnputil cannot)
and `-Remove` (device, driver package and folder). It must run elevated, so each run needs
**the user to click Yes on UAC**: start it with `Start-Process powershell -Verb RunAs -Wait`
and pass `-Log <file>`, because the elevated window's output is otherwise lost. Ask before every
install, and move test windows back before removing it.

The virtual screen gets its own taskbar, so its work area is 800x552, not 800x600. App `move`
then pushes a window up to fit: assert "on the target screen and inside its work area", not an
exact offset. A DPI-unaware window moved from a 150% to a 100% screen keeps its physical size.

**Not over Remote Desktop.** In an RDP session (`query session` shows `rdp-tcp#N` Active;
`GetSystemMetrics(SM_REMOTESESSION)` is 1) Windows shows only the session's own screen: the
virtual screen installs fine ("Virtual Display Driver", status OK) but never appears. The user
must be signed in at the PC itself. Check this before asking for the UAC click.
