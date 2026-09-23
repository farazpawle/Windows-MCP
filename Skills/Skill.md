---
name: windows-mcp
description: Use when controlling this Windows PC via the windows-mcp tools (lcl-windows-mcp-*) — apps, UI clicks/typing, files, registry, processes, PowerShell, screenshots. Read before the first windows-mcp call.
---
# Windows MCP — field-tested guide (tested 2026-09-22 in Claude Desktop, re-verified in Claude Code)


Which server? Both Claude Code and (from 2026-09-22, after a Claude Desktop restart) Claude Desktop run the **local repo** (`uv --directory <repo> run windows-mcp serve`), so "Local repo" notes below apply to both. "PyPI" notes only matter for other machines or configs using `uvx windows-mcp`.
Machine: 1 display 1920x1080, 100% scale (screen coords = image coords) · PowerShell 7.6 · Avast AV · OneDrive-synced Desktop.

## 0. Golden rules (learned the hard way)

0. **A frozen app can stall Snapshot / WaitFor / App switch.** They query every open window; a "Not Responding" app (seen: Antigravity IDE) used to block them forever. Fixed in the local repo on 2026-09-22 (UIA timeouts + skip hung windows) and proven live: every WaitFor condition answered in ~0.2 s with a frozen app open. The PyPI release (`uvx windows-mcp`) may still hang. If one of these calls stalls, check with PowerShell: `Add-Type -Name U -Namespace W -MemberDefinition '[DllImport("user32.dll")] public static extern bool IsHungAppWindow(IntPtr h);'; Get-Process | ? { $_.MainWindowHandle -ne 0 -and [W.U]::IsHungAppWindow($_.MainWindowHandle) } | select Id,ProcessName,MainWindowTitle` — then ask the user to close/restart that app. Screenshot never hangs this way (it doesn't query windows).
1. **Approval prompts steal focus (Claude Desktop only).** Each call the user approves in the Claude app brings Claude to the front, covering the target window. Not observed in Claude Code (no approval pop-ups). Unless windows-mcp is on "Always allow":
   - Coordinate clicks and typing can land IN THE CLAUDE CHAT (a Type+Enter test sent a chat message).
   - Shortcut goes to Claude, not the target.
   - Mitigations: ask the user to Always-allow; for windows you create, set TopMost; prefer PowerShell/FileSystem/Registry over UI automation.
   - Never use press_enter=true unless a fresh screenshot shows the target on top at that exact spot.
2. **Verify by effect, never by tool output.** "Sent / Typed / Clicked" only means the call ran. Check the result: screenshot, file content, registry read, process list.
3. **Kill by PID, not by name.** Notepad on Win11 runs every tab in one process, and a name kill ends *every* process with that name. Local repo: `list` filters by plain substring ("pwsh" → only pwsh.exe) and `kill` by name is exact with `.exe` optional. PyPI release: the list filter is fuzzy ("pwsh" also matched ShellExperienceHost.exe). List first, then kill by PID only a process you launched.
4. **Absolute paths only.** Relative paths resolve to the user's OneDrive-synced Desktop (cloud-synced).
5. Sandbox experiments in `%TEMP%\<name>` and `HKCU:\Software\<TestKey>`. Clean up and verify cleanup.
6. **Boolean params: pass real `true`/`false`.** Local repo: every tool also accepts `"yes"/"no"/"1"/"0"/"on"/"off"` and rejects any other word with an error. PyPI release: strings other than `"true"` are silently false (FileSystem `recursive="yes"` searched only the top folder).
7. **VS Code-family windows are never read (local repo).** One element read of VS Code pinned it at 100% CPU, "Not Responding" until restart, and returned nothing (proven 2026-09-22; Antigravity froze the same way). Snapshot/WaitFor/App switch now list VS Code, Cursor, Windsurf, Antigravity and VSCodium by name only ("elements not read"); use Screenshot + coordinates for them. `WINDOWS_MCP_READ_VSCODE=1` turns reading back on — don't. **The PyPI release still reads them: any Snapshot/WaitFor/App switch there freezes an open VS Code.** Antigravity's program is `Antigravity IDE.exe` on this PC; the guard missed it until 2026-09-22 (a test froze it), now covered.

## 1. Observe


| Tool             | Use                                                | Notes                                                                                                                                                                                                                                         |
| ------------------ | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| DisplayInventory | monitor bounds, DPI, scale                         | Run first if coords look off. Scale 1.0 here.                                                                                                                                                                                                 |
| Screenshot       | fast image only                                    | No UI tree. It does not list windows: local repo says "Skipped (screenshot-only…)"; PyPI says "No active window found / No windows found", which means **not checked**, NOT that nothing is open — use Snapshot for the window list. `display=[n]` with a bad index returns a clear error listing valid displays. Captures pending approval prompts. `width_reference_line` / `height_reference_line` draw a grid (local repo; either one alone works). PyPI ignored them here.                                                                                                                       |
| Snapshot         | UI tree with (x,y) centres, focused/opened windows | Local repo: each element line in the text tree starts with `[label:N]`, the id `label=` in Click/Type/MultiSelect uses (numbers do NOT follow the tree's order; read them from the line). **PyPI shows label ids only on the annotated image** (use_vision=true) — prefer `loc` there. `region` keeps only elements inside the rectangle. Local repo: elements of background windows that another window covers are left out (their click would hit the covering window); PyPI still lists them. The focused window is read first, so it gets its elements before the 500-element cap is reached (other windows fill the rest; the truncation message says so). A busy focused window (Excel sheet, long document: one element per word) can fill the cap alone — use `region` or raise `WINDOWS_MCP_MAX_TREE_ELEMENTS`. Local repo: `region` also limits what is read (only windows visible in it; a taskbar-strip Snapshot took 0.3 s instead of 22 s). PyPI reads everything first. `display=[0]` works. **Second monitor (tested 2026-09-22 with a temporary virtual screen):** `display=[1]` and `[0,1]` capture correctly, coordinates are virtual-desktop (the 2nd screen starts at x=1920 here) and a click there lands right; the capture border shows on that screen. Local repo re-reads the screen layout on every call; **PyPI remembers the layout from server start, so a monitor plugged in later shows no elements until the server restarts**, and it lists windows maximised on the other screen as 8 px wide (their invisible border). Reference-line grid renders with use_vision=true (local repo: either line alone works).                  |
| WaitFor          | poll until a condition                             | Conditions:`active_window` (window_name), `text_exists` / `element_exists` / `element_enabled` / `focused_element` (text). Returns time + attempts; on timeout it errors and names the actual active window. Cheaper than repeated Snapshots. `text_exists` searches the active window, or the windows matching `window_name`, including plain labels ("Saved") — local repo only; the PyPI release sees only buttons/fields/titles and ignores `window_name` for it. |
| Wait             | sleep N seconds                                    | Verified: `Wait(3)` took 3.4 s. Local repo accepts decimals (`0.5`) and refuses negative or non-numeric values; PyPI takes whole seconds only. Prefer WaitFor.                                                                                                                                                                                               |

## 2. Apps and windows — `App`

- `launch_executable`: `executable` = full path (local repo also takes a bare name found on PATH, e.g. `notepad.exe`), `args` = argv **list**, optional `cwd`. Returns `{pid,...}`; **save the PID** for later kills. **The PID can be a stub that hands off and exits:** `notepad.exe` returned PID 42484 while the Notepad window belonged to PID 27328 (2026-09-22). Before killing, check the PID is still alive; if not, find the real one with Process `list`. Tested: `C:\Program Files\PowerShell\7\pwsh.exe` with `["-NoProfile","-STA","-WindowStyle","Hidden","-File","<path>"]`.
- `launch`: by Start Menu name, fuzzy ("calc" opens Calculator; verified 2026-09-22). An unknown name replies "... not found in start menu." Local repo names the window it found, with its real title ("Calculator launched."), and refuses an empty name; PyPI echoes your text ("Calc launched."), so check the reply there. Returns no PID — use `launch_executable` when you need to kill it later. Store apps like Notepad may open a new tab in an already-running window instead of a new process.
- `switch` (and `resize`): fuzzy match on the **window title**. Local repo then falls back to a plain part of the title ("Edge", "tri.txt") and to the program name ("msedge", "notepad.exe"); verified 2026-09-22. Local repo: when a name matches several windows it switches to the best match and lists the others ("Also matched ..."), and an empty name is refused. **PyPI needs a long title fragment** ("Personal - Microsoft Edge"; "Microsoft Edge" failed because Edge titles hide a zero-width space).
  - The approval click undoes the switch (see rule 1).
- `resize`: `name`, `window_loc=[x,y]`, `window_size=[w,h]`. Works; the outer window rectangle matched exactly (700x500 at 100,100, checked 2026-09-22), and the visible frame is a few px smaller (invisible borders). Either `window_loc` or `window_size` alone is fine (the other is kept). With no `name` it resizes the window that was active at the **last Snapshot/Screenshot/App call**, not the current focus — pass `name` if focus may have moved. Maximized or minimized windows are refused ("Cannot resize ...: it is maximized"); restore first. Local repo also refuses a `window_size` that is not two positive numbers and a `window_loc` that puts the window fully off every display.

## 3. Mouse and keyboard


| Tool        | Verified behaviour                                                                                                                                                                                         |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Click       | `loc=[x,y]` or `label=<int>`. `clicks` 0 (hover only), 1, 2, 3 (triple = select a line; verified in Notepad). Local repo refuses any other value; PyPI replies "None … clicked" and a negative value single-clicks. Local repo only (2026-09-22): `modifiers` holds keys during the click — `"shift"` extends a selection (Shift+click selected lines 1–3 in Notepad), `"ctrl"` adds to one or opens a link in a new tab, `"ctrl+shift"`; allowed ctrl, shift, alt, win, always released afterwards. With no `loc`/`label` it clicks where the pointer is. PyPI has neither: Ctrl-click via MultiSelect, no Shift-click. |
| Type        | Clicks `loc` first, then types. Local repo: with no `loc`/`label` it types into whatever already has keyboard focus, with no click, so the caret and selection stay put (use it after a click/shortcut that placed the caret, or to replace a selection); make sure the right window is focused first. PyPI requires `loc`/`label`. `clear=true` empties the field first (local repo also clears old-style boxes that ignore Ctrl+A; PyPI deletes one char there and appends). `caret_position` start/end verified. `press_enter=true` sends Enter (dangerous, see rule 1). Accents and CJK OK. **Emoji: local repo OK; PyPI types a wrong character.** Text of 20+ chars is pasted via the clipboard, which is restored afterwards. Empty `text` with `clear=true` clears the field (PyPI then raises "string index out of range" even though it worked). |
| MultiEdit   | `locs=[[x,y,"text"],...]` or `labels=[[id,"text"],...]`. **Clears each field before typing** (it overwrites, it doesn't append). Verified.                                                                   |
| MultiSelect | `locs=[[x,y],...]`; `press_ctrl=true` gives Ctrl-multi-select (verified: 3 list items). `press_ctrl=false` means plain sequential clicks — in a list the last click wins. Local repo replies "Ctrl-selected elements" or "Clicked in sequence"; PyPI says "multi-selected" either way. |
| Scroll      | `loc`, `direction`, `wheel_times`. **1 wheel = 3 lines.** `type="horizontal"` (local repo: the argument is now `axis`, `type` still accepted; a direction that doesn't fit the axis, e.g. horizontal + up, is a tool error): local repo scrolls sideways in any app; **PyPI uses Shift+wheel, which native apps treat as vertical** (it scrolled down instead of right). Local repo: `modifiers="ctrl"` with up/down zooms a page or document (2 notches took Notepad from 100% to 120%). |
| Move        | Hover with `loc`; drag with `from_loc` + `loc` + `drag=true` (optional `duration`), or `drag=true` from the current pointer. Verified pixel-exact. Local repo: `modifiers` works with `drag=true` only (e.g. `"ctrl"` to copy instead of move). For paths one straight drag can't do (curves, hover over a target before dropping): `mouse_button="down"` at `loc`, plain Moves to steer, then `mouse_button="up"` (`loc` optional on both `down` and `up` = where the pointer is). Verified: down/two moves/up selected lines in Notepad. **Always send the `up`**, or the left button stays held for everything after. PyPI has no `modifiers`/`mouse_button`. |
| Shortcut    | e.g. `"ctrl+s"`, `"win+r"`. Local repo: `repeat=N` (1–100) presses it N times (`"down"`, `repeat=5` moved 5 lines); `hold=S` (up to 10 s) keeps the keys down that long, for games or apps that check whether a key is held. A held key does **not** auto-repeat characters (holding `b` typed one `b`), so use `repeat` for that. hold and repeat can't be combined. PyPI has neither. Hits whatever has focus, which after approval is Claude. **Unreliable unless Always-allow.** Local repo rejects a misspelled key before pressing anything; **PyPI presses Ctrl, fails, and leaves Ctrl held down** — if a shortcut errors there, release modifiers before continuing. |

Coordinates: use Snapshot centres. Re-snapshot after any window move, resize or scroll, because coords go stale.

## 4. System tools (most reliable, no focus issues)

**PowerShell** (`command`, `timeout` s, default 30)

- Output is UTF-8 and returns `Status Code`.
- Local repo: errors and warnings come back as plain text. When the command still succeeds (non-terminating errors, status 0), they follow the output under an `Errors and messages:` heading (with any warning, verbose and debug lines) — check for it. **PyPI release drops those errors silently** (status stays 0) and shows failures as raw CLIXML; there, wrap commands: `$ErrorActionPreference='Stop'; try { ... } catch { "ERR: "+$_.Exception.Message; exit 1 }`
- On timeout it returns "Command execution timed out" with status 1, and the command really is stopped (a timed-out script did not finish its work later). Raise `timeout` for long jobs. `timeout` must be at least 1 (local repo rejects 0 or less with a clear error; on PyPI `timeout=0` fails every command).
- Web requests work here (Invoke-WebRequest uses the Windows cert store), so use this as the fallback when Scrape fails.
- Find notification AppIDs: `Get-StartApps`.

**FileSystem** (`mode`, absolute `path`)

- `write`: creates parent folders automatically; `append=true` appends. Local repo: an existing file is refused unless `overwrite=true`. **PyPI release silently overwrites it even with `overwrite=false`** — check `info` first there. Newlines are written as CRLF.
- `search` without `recursive=true` only looks in the top folder ("No matches" even when subfolders have hits).
- `read`: `offset` is a **1-based line number**, plus `limit`.
- `copy` / `move`: refuse an existing destination unless `overwrite=true`. `move` also renames and creates target folders.
- `delete`: refuses a non-empty dir unless `recursive=true`.
- `list`: `pattern` filter. `search`: glob + `recursive=true`. `info`: size, dates, counts.

**Registry** (PowerShell-style paths `HKCU:\...`)

- `get` / `list` / `set` (`type` String|ExpandString|Binary|DWord|MultiString|QWord) / `delete`.
- `set` auto-creates the key. DWord is stored as a real Int32.
- Binary, local repo: pass hex bytes `"01,02,ff"` / `"01 02 ff"` / `"0102ff"` or a decimal list `"[1, 2, 255]"`; anything else is refused before writing. **PyPI release accepts only a single byte** — there use PowerShell `Set-ItemProperty ... -Value ([byte[]](1,2,255)) -Type Binary`.
- `list` shows ExpandString values already expanded (`%TEMP%` → full path); the stored raw value is intact.
- **MultiString can't hold several items.** Commas and newlines both become ONE item. For real lists use PowerShell: `Set-ItemProperty -Path ... -Name X -Value @('a','b') -Type MultiString`.
- `delete` WITH `name` removes one value. WITHOUT `name` it deletes the key and its values. Local repo: a key that has sub-keys is refused unless `recursive=true`. **PyPI release deletes the whole tree with no confirmation.**
- A missing key returns an error (plain text in the local repo, noisy CLIXML on PyPI).

**Process**

- `list`: `name` is a substring filter (fuzzy on PyPI); `sort_by` memory|cpu|name; `limit` (`limit=0` misleadingly says "No processes found"). CPU% is summed across cores (System Idle can show >1000%).
- `kill`: prefer `pid`; give `pid` **or** `name`, not both (local repo refuses the pair; PyPI silently uses the pid). By `name` it is an exact match (`.exe` optional) and ends every process with that name. `force` is available. Returns "Terminated: exe (PID)".

**Clipboard**: `get` / `set`; Unicode round-trips. Non-text content reads as "empty or non-text" and **can't be saved or restored**, so warn before overwriting.

**Notification**: `title`, `message`, `app_id` — must be an installed app's AppID from `Get-StartApps`; Windows PowerShell's `{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell1.0\powershell.exe` and File Explorer's `Microsoft.Windows.Explorer` were both shown on screen on 2026-09-22. Local repo: an unknown app_id, or notifications turned off for the app / all apps / by policy, returns an error instead of "sent". Do Not Disturb (Focus) can't be read: with it on, a "sent" toast goes to the notification centre without popping up. **PyPI release reports success even for a fake app_id** (nothing is shown).

## 5. Web — `Scrape`

- Default HTTP mode, **local repo (from 2026-09-22):** works on this PC; certificates are checked against the Windows store, so Avast's HTTPS inspection is accepted and bad certificates are still refused. Local/private addresses are blocked by design.
- **PyPI release:** fails on this PC. Either CERTIFICATE_VERIFY_FAILED (Avast re-signs HTTPS), or with Python 3.14 the whole server **crashes** ("Connection closed" on every later call) because Avast injects `SSLKEYLOGFILE`. Use WebFetch or PowerShell Invoke-WebRequest there.
- `use_dom=true` reads the **active tab of the focused browser** (verified 2026-09-22 in Edge; Snapshot `use_dom=true` lists the page's links/fields with labels that Click accepts). To open a page, start `msedge.exe <url>` (opens a new tab; this PC's browser lock blocks new *windows*, not tabs), then App switch to it. Close only your own tab afterwards (Ctrl+W while it is active). Local repo: the first/last line says top / middle / bottom, or "Whole page visible"; **PyPI always says "Reached top … Scroll down"** — ignore it there.
- It returns only the **visible viewport** text; scroll and scrape again for more. `use_sampling=false` gives raw text. Clients that can't summarise (Claude Code) always get raw text; the local repo adds "Note: summary unavailable in this client" so you know.

## 6. Recommended workflow for UI tasks

1. DisplayInventory once, then Snapshot (local repo prints label ids in the text; PyPI needs use_vision=true for them).
2. App switch or launch_executable (save the PID), then WaitFor `active_window`.
3. Screenshot to confirm the target is ON TOP at the coordinates.
4. Act with coordinates. No Enter or shortcuts unless focus is proven.
5. Verify the effect (Screenshot, WaitFor text_exists, or a file/registry read).
6. Clean up: kill only your own PIDs; remove sandbox files and keys; `Test-Path` to confirm.
