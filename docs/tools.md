---
Title: Windows-MCP tools reference
Description: All 22 tools grouped as See the screen, Mouse and keyboard, Waiting, Apps and windows, and System, with what each does and its main options. For agents, the deeper how-to lives in the field guide (Skills/windows-mcp). Any tool can be switched off with --exclude-tools.
---

# Tools

Windows-MCP gives an AI agent 22 tools. Tools that act on the screen hit whatever window is on
top, so the system tools (PowerShell, FileSystem, Registry, Process) are the safest choice when
they can do the job.

Every failure comes back as a real tool error, not as a normal reply. Long replies stop at
50,000 characters with a note saying how much was left out.

For the tricky cases (focus stolen by approval prompts, shrunk screenshots, apps with no
accessibility data), agents should read the [field guide](../Skills/windows-mcp/SKILL.md).

## See the screen

| Tool | What it does | Main options |
|---|---|---|
| `Screenshot` | Fast picture of the screen, with no element list. The usual first call. | `display=[0]`, `region=[l,t,r,b]`, `zoom=true` (enlarge a region for small text), reference grid lines |
| `Snapshot` | The screen's interactive elements (buttons, fields, menus, links) with `[label:N]` ids and positions, plus the window list. | `region` (reads only windows visible there, ~0.2 s), `display`, `use_vision=true` (adds the picture), `use_dom=true` (web page content in a browser) |
| `FindText` | Finds words on screen by OCR, for apps with no accessibility data: games, remote desktops, canvas apps. Returns every match with a clickable position. | `text`, `region`, `window` (one window only) |
| `DisplayInventory` | Every display's bounds, work area, DPI and scale. | none |
| `Scrape` | Reads a web page over HTTP, or the active browser tab. Private and local addresses are blocked. | `url`, `use_dom=true`, `query` |

Elements behind another window are left out of Snapshot, because a click on them would hit the
window in front. A Snapshot collects at most 500 elements (`WINDOWS_MCP_MAX_TREE_ELEMENTS`).

## Mouse and keyboard

| Tool | What it does | Main options |
|---|---|---|
| `Click` | Clicks at a point, a Snapshot label, or an element found by name at click time. The reply names what was hit. | `loc`, `label`, `element="button:Save"`, `window`, `clicks` 0-3, `button`, `modifiers="ctrl"`, `expect` (refuse if the spot is not what you expect) |
| `Type` | Types text as real keystrokes (accents, CJK and emoji included; the clipboard is never touched). The reply shows what the field now holds. | `loc`/`label` or none (type where the caret is), `clear`, `caret_position` (`start`, `end`, `field_start`, `field_end`), `press_enter`, `expect` |
| `MultiEdit` | Fills several fields in one call; each field is cleared first. | `locs=[[x,y,"text"]]` or `labels=[[id,"text"]]` |
| `MultiSelect` | Ctrl-selects several items, or clicks them in turn. | `locs` or `labels`, `press_ctrl` |
| `Scroll` | Scrolls up, down, left or right. The reply gives the new position ("now at 45%"). | `loc`/`label`, `direction`, `wheel_times`, `axis="horizontal"`, `modifiers="ctrl"` (zoom) |
| `Move` | Moves the pointer, drags, or holds a mouse button for custom paths. With no target it reports where the cursor is. | `loc`, `from_loc` + `drag=true`, `duration`, `mouse_button="down"`/`"up"`, `modifiers` |
| `Shortcut` | Presses key combinations. Common computer-use key names work too (`Page_Down`, `Return`). A misspelled key is refused before anything is pressed. | `"ctrl+s"`, `repeat=N`, `hold=seconds`, `release_all=true` (let go of every held key and button) |
| `Steps` | Runs up to 20 of the steps above (plus `wait_for` and `wait`) in one call. Each step keeps its own checks, and the run stops at the first failure or unexpected new window. One Claude Desktop approval covers the whole list. | `steps=[{"do": "click", ...}, {"do": "type", ...}]`, `allow_new_window` per step |

Before a `label=` or `element=` action, the tool checks the element is still at its spot and
refuses if another window now covers it. Points off every screen are refused, not clamped to
the edge.

Every input reply ends with a note when a new window or an in-app dialog appeared (a "save
changes?" question, an error), so the agent can answer it before the next keys land there.

## Waiting

| Tool | What it does | Main options |
|---|---|---|
| `WaitFor` | Waits inside one call until a condition is met; a timeout is an error. | `active_window`, `text_exists`, `element_exists`, `element_enabled`, `focused_element`, `screen_text` (OCR), `screen_changed`, `screen_idle` (`settle` seconds), `region`, `timeout` |
| `Wait` | Pauses for a number of seconds (decimals allowed, at most 300). Prefer WaitFor. | `duration` |

## Apps and windows

| Tool | What it does | Main options |
|---|---|---|
| `App` | Starts apps and manages windows: `launch` (Start-menu name), `launch_executable` (path or name on PATH, returns the PID), `switch`, `resize`, `minimize`, `maximize`, `restore`, `close`, `list` (handle, PID, state, position, size) and `move` (to another display). | `name` or `handle`, `executable` + `args` + `cwd`, `window_loc`, `window_size`, `display` |

Window names match fuzzily on the title, then on part of the title, then on the program name.
`switch` confirms the window really came to the front and says which window Windows kept in
front if it did not.

## System

| Tool | What it does | Main options |
|---|---|---|
| `PowerShell` | Runs a PowerShell command. A non-zero exit code is an error; a timeout really stops the command. | `command`, `timeout` (default 30 s), `success_exit_codes` |
| `FileSystem` | `read`, `write`, `copy`, `move`, `delete`, `list`, `search` and `info` for files and folders. Nothing is overwritten unless asked. | `path` (absolute; relative paths start at the Desktop), `offset`/`limit` (line numbers), `overwrite`, `append`, `recursive`, `pattern` |
| `Registry` | `get`, `set`, `delete` and `list` registry values and keys, directly (no PowerShell, under 0.01 s). A whole hive can never be deleted. | `path` (`HKCU:\...`), `name`, `value`, `type`, `recursive` |
| `Process` | Lists processes, or ends one. | `list` with `name`, `sort_by` (memory, cpu, name), `limit`, `details=true` (start time and command line, secrets hidden); `kill` by `pid` (preferred) or exact `name`, `force` |
| `Clipboard` | Reads or sets the clipboard: text, images and file lists. | `get`, `save_image` (to a new .png), `set` with `text`, `image` or `files` |
| `Notification` | Shows a Windows toast notification. An unknown app id is an error. | `title`, `message`, `app_id` |

## Switching tools off

Any tool can be removed at startup, which is worth doing when a deployment does not need it:

```shell
windows-mcp serve --exclude-tools PowerShell,Registry
windows-mcp serve --tools Screenshot,Snapshot,Click,Type
```

See [Remote access and security](remote-access.md) for the other server options.
