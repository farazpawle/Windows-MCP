# PyPI release: how it differs

Read only when the server is `uvx windows-mcp` (see SKILL.md, "Which server"). Everything else
in this guide still applies unless a line here says otherwise. These notes come from testing
older builds; the PyPI release was not re-checked for every one.

Contents: General · Observe · Apps and windows · Input · PowerShell · FileSystem · Registry ·
Process · Clipboard · Notification · Scrape

## General

- **Failures come back as normal replies**, not tool errors: read the text, not just the
  success flag.
- Booleans: any string other than `"true"` is silently false (FileSystem `recursive="yes"`
  searched only the top folder).
- **A frozen ("Not Responding") app can hang Snapshot, WaitFor and App switch.**
- **It reads VS Code-family windows: any Snapshot, WaitFor or App switch freezes an open
  VS Code.**
- Replies only echo the request (no element hit, field value or scroll position).
- No 50,000-character cap on long replies.

## Observe

- Screenshot: "No active window found / No windows found" means **not checked**, not that
  nothing is open; use Snapshot for the window list.
- Screenshot ignored `width_reference_line` / `height_reference_line`. There is no `zoom`.
- Full captures always use "pillow", which can miss pop-ups such as an antivirus alert:
  capture the window's rectangle with `region`.
- Snapshot shows label ids **only on the annotated image** (`use_vision=true`): prefer `loc`.
- **Labels are renumbered after WaitFor or any other capture**: Snapshot again right before a
  label click. There is no spot check before a label action.
- Snapshot still lists elements of background windows that another window covers.
- `region` only filters the result: everything is read first (slow).
- **The screen layout is remembered from server start**: a monitor plugged in later shows no
  elements until the server restarts. Windows maximized on the other screen show as 8 px wide.
- No FindText, and no WaitFor `screen_text`, `screen_changed` or `screen_idle`.
- WaitFor `text_exists` sees only buttons, fields and titles, and ignores `window_name`.
- Wait takes whole seconds only, with no upper limit.

## Apps and windows

- `launch_executable` needs a full path (no bare names).
- `launch` echoes your text ("Calc launched.") instead of the real title: check the reply.
- `switch` needs a long title fragment ("Personal - Microsoft Edge"; "Microsoft Edge" fails
  because Edge titles hide a zero-width space).
- `resize` with no `name` uses the window that was active at the **last Snapshot, Screenshot
  or App call**, not the current focus: pass `name`.
- No `minimize`, `maximize`, `restore`, `close`, `list`, `move` or `handle=`.
- Windows that cannot be maximized (fixed-size dialogs, an app showing a modal question, an
  alert) are left out ("not found"): use Click `element=` without `window` (front window),
  Process `kill` by PID, or Snapshot's "Focused Window" line.
- Screenshot coordinates of a shrunk image are not converted: **always screen pixels; multiply
  image coordinates by the printed scale yourself.**

## Input

- Click: `clicks` other than 0–3 replies "None … clicked"; a negative value single-clicks.
- Click: no `modifiers` (Ctrl-click only via MultiSelect; no Shift-click) and no `element=`.
- **A point off every screen is clamped to the screen edge and clicked there** (all input
  tools).
- Type requires `loc` or `label`. `clear=true` deletes one character in old-style boxes and
  appends. **Emoji type a wrong character.**
- **Type pastes 20+ characters through the clipboard and restores only text: an image or copied
  files on it are lost.** Back them up first.
- Type with empty `text` and `clear=true` raises "string index out of range" although it
  cleared.
- MultiEdit moves a bad target to the screen corner, and later fields may fail silently.
- MultiSelect says "multi-selected" whether or not Ctrl was held.
- Scroll accepts `wheel_times` of 0 or less and does nothing. **Horizontal scroll sends
  Shift+wheel, which native apps treat as vertical** (it scrolled down instead of right).
- Move has no `modifiers` or `mouse_button`, and refuses a Move with no `loc`.
- **A held mouse button stays held, so the next Click becomes a drag.**
- Click, Move, Scroll and MultiSelect each pause 0.5 s (Click ~0.6 s, Scroll ~1.1 s,
  MultiEdit ~2.3 s per field); Type of under 20 characters takes ~1.1 s.
- Shortcut knows no computer-use names except `Return` and `BackSpace`: use `pagedown`, `win`,
  `ctrl+=`. No `repeat`, `hold` or `release_all`.
- **A misspelled Shortcut key presses Ctrl, fails and leaves Ctrl held down**: release the
  modifiers before continuing.

## PowerShell

- `Read-Host` silently returns an empty string.
- **Errors are dropped silently** (status stays 0) and failures show as raw CLIXML. Wrap
  commands: `$ErrorActionPreference='Stop'; try { ... } catch { "ERR: "+$_.Exception.Message; exit 1 }`
- A timeout is a normal reply with status 1. `timeout=0` fails every command.

## FileSystem

- **`write` silently overwrites an existing file even with `overwrite=false`**: check `info`
  first.
- A file over 10 MB is refused even with `offset` + `limit`: use PowerShell
  `Get-Content -TotalCount`.
- `info` on a folder shows the folder entry itself (4 KB). For the contents use PowerShell
  `Get-ChildItem -Recurse | Measure-Object Length -Sum`.

## Registry

- **`*`, `?` and `[ ]` in a path act as wildcards (a `delete` of `A*` hits every matching key),
  and a path without a hive goes to the file system**: never use those characters, and always
  start with `HKCU:\` or `HKLM:\`.
- Binary `set` accepts only a single byte. Use PowerShell
  `Set-ItemProperty ... -Value ([byte[]](1,2,255)) -Type Binary`.
- MultiString: commas and newlines both become ONE item. Use PowerShell
  `Set-ItemProperty -Path ... -Name X -Value @('a','b') -Type MultiString`.
- `list` shows Binary as a decimal list (`{1, 2, 255}`); the bytes are the same as `get`'s hex.
- **`delete` without `name` deletes the whole tree with no confirmation.**
- A missing key gives a noisy CLIXML error.

## Process

- The `list` name filter is fuzzy ("pwsh" also matched ShellExperienceHost.exe): list first,
  then kill by PID.
- `limit=0` says "No processes found".
- CPU% may be summed across cores (System Idle over 1000%): read it with care.
- `kill` with both `pid` and `name` silently uses the pid.

## Clipboard

- Non-text content reads as "empty or non-text" and **cannot be saved or restored**: warn
  before overwriting.

## Notification

- **Reports success even for a fake app_id** (nothing is shown).

## Scrape

- Fails on this PC: CERTIFICATE_VERIFY_FAILED (Avast re-signs HTTPS), or with Python 3.14 the
  whole server **crashes** ("Connection closed" on every later call) because Avast injects
  `SSLKEYLOGFILE`. Use WebFetch or PowerShell `Invoke-WebRequest`.
- `use_dom=true` always says "Reached top … Scroll down": ignore it.
- `query` is ignored without a summary.
