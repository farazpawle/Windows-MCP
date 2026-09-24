# Input: Click, Type, MultiEdit, MultiSelect, Scroll, Move, Shortcut

Contents: Click · Spot check · Type · MultiEdit · MultiSelect · Scroll · Move · Shortcut ·
Coordinates · What the replies report · Shrunk screenshots

## Click

- Target: `loc=[x,y]`, `label=<id>` (from Snapshot) or `element=`. With none, it clicks where
  the pointer is.
- `clicks`: 0 (hover only), 1, 2, 3 (triple selects a line); any other value is refused.
- `modifiers` holds keys during the click: `"shift"` extends a selection, `"ctrl"` adds to one
  or opens a link in a new tab, `"ctrl+shift"`. Allowed: ctrl, shift, alt, win (`super`,
  `cmd`, `meta` = win; `option` = alt). Always released afterwards. Not with `clicks=0`.
- A point outside every display is refused, naming it (MultiEdit, MultiSelect, Type, Scroll
  and Move do the same).
- `element="button:Save"` (type optional: `element="Save"`) finds the element by name when it
  clicks, no Snapshot needed. It searches the front window, or the one named by `window`.
  - An exact name (case ignored) wins, else a single partial match; several or none are
    refused with what was found.
  - The type is the Snapshot type (button, edit, menu item, check box…). A name containing `:`
    needs a leading `:` (`element=":12:00"`). Not with `loc` or `label`.
  - Two entries with the same type and name are told apart by what is on screen: the one shown
    at its centre is taken, and copies at the same spot count as one (Explorer reports its
    context menu's "Copy as path" twice, same box). Two shown at different spots are refused;
    then use `loc`.
  - In a Chromium/Edge page the first search can find nothing: page elements appear only once
    a UI Automation client asks. Retry after ~2 s.
- A right-click menu appears ~1 s after Click returns: WaitFor `element_exists` or
  `screen_idle` before reading it.

## Spot check (label= and element=)

- Before acting, the tool checks the element is still at its spot.
- When something of the same window is drawn over the element's centre (Explorer's path
  buttons over its Address Bar), it acts on a free point of the element; the reply's
  "at (x,y)" shows where.
- Refusals name their cause: `covered by "<window>"; bring ... to the front` (another window
  on top), or "no longer at its spot" / "drawn over it everywhere tried" (the element moved or
  is hidden in its own window): take a new Snapshot, or use `loc`.

## Type

- Clicks `loc`/`label` first, then types. With neither it types into whatever has keyboard
  focus, without a click, so the caret and selection stay put (after a click or shortcut
  placed the caret, or to replace a selection). Make sure the right window is focused.
- `clear=true` empties the field first, old-style boxes that ignore Ctrl+A included. Empty
  `text` with `clear=true` just clears it. Never in an Explorer file list: it sends Ctrl+A
  then Backspace, which goes up a folder.
- `caret_position`: `start` or `end` of the **current line** (Home/End), not of the whole
  field. For the start or end of a multi-line field, send Shortcut `ctrl+home` or
  `ctrl+end` first. `press_enter=true` sends Enter (see golden rule 1).
- Accents, CJK and emoji are typed correctly. Text is sent as keystrokes and never touches
  the clipboard (2,000 characters arrived intact). Line breaks and tabs are real Enter and
  Tab key presses (in a form, Tab moves to the next field); braces are typed as-is. A
  622-character multi-line text takes under 1 s.

## MultiEdit

- `locs=[[x,y,"text"],...]` or `labels=[[id,"text"],...]`. **Clears each field before typing**
  (it overwrites, it does not append).
- Every target is checked before anything is typed; it stops at a field that fails and lists
  which were done.

## MultiSelect

- `locs=[[x,y],...]`. `press_ctrl=true` Ctrl-multi-selects (the reply says "Ctrl-selected
  elements"); `press_ctrl=false` clicks in sequence ("Clicked in sequence"), so in a list the
  last click wins.

## Scroll

- `loc`, `direction`, `wheel_times` (a whole number, 1 or more). **1 wheel = 3 lines.**
- `axis="horizontal"` (`type` is still accepted) scrolls sideways in any app. A direction that
  does not fit the axis (horizontal + up) is an error.
- `modifiers="ctrl"` with up/down zooms a page or document (2 notches took Notepad from 100%
  to 120%).

## Move

- Hover: `loc`. Drag: `from_loc` + `loc` + `drag=true` (optional `duration`), or `drag=true`
  from the current pointer. Pixel-exact. `modifiers` works with `drag=true` only (`"ctrl"`
  copies instead of moving).
- Paths one straight drag cannot do (curves, hover over a target before dropping):
  `mouse_button="down"` at `loc`, plain Moves to steer, then `mouse_button="up"`; `loc` is
  optional on both (= where the pointer is). **Always send the `up`.**
- A second `down`, or an `up` with nothing held, is refused. The next click, scroll, drag or
  located Type lets go of a held button first and says so ("Released the held left mouse
  button first.").
- Move with no `loc`/`label` and no drag moves nothing and replies "The cursor is at (x,y)."

## Shortcut

- e.g. `"ctrl+s"`, `"win+r"`. Also computer-use (xdotool) names: `Page_Down`, `KP_Enter`,
  `Return`, `BackSpace`, `super`/`cmd`, and `ctrl++` or `ctrl+plus` for Ctrl+Plus.
- `repeat=N` (1–100) presses it N times back to back (`"down"`, `repeat=5` moves 5 lines).
- `hold=S` (up to 300 s; the call blocks that long) keeps the keys down, for games or apps that
  check a key is held. A held key does not auto-repeat characters (holding `b` typed one `b`):
  use `repeat` for that. `hold` and `repeat` cannot be combined.
- `release_all=true` (alone) is the panic button after a failed sequence: it lets go of any
  held Shift/Ctrl/Alt/Win and mouse button and names them ("Released: left Shift, left mouse
  button."; else "Nothing was held; nothing was sent.").
- A misspelled key is refused before anything is pressed.
- It hits whatever has focus, which after an approval is Claude: unreliable unless
  Always-allow.

## Coordinates

- Use Snapshot centres. Take a new Snapshot after any window move, resize or scroll: old
  coordinates go stale.

## What the replies report

- Click names the element it hit, read just before clicking
  (`clicked button "Save" in "Notepad" at (…)`).
- Type adds what the focused field now holds (`The field (edit "Search") now reads "…"`);
  password boxes are never shown.
- Scroll adds the scroll area's position (`list "Files" is now at 45% (was 30%)`) or says it
  could not be read.
- VS Code-family and frozen windows are named but never read (a horizontal Scroll over them
  sends a plain sideways wheel).
- Every input reply (Click, Type, Scroll, Move, Shortcut, MultiSelect, MultiEdit) ends with
  `Note: a new window appeared: "<title>" (handle=…, pid=… program)` when a window opened
  since the previous input action, including a pop-up that came up after that reply. Read
  it before the next step: a question or alert may be waiting and take the next keys. Each
  window is named once; one opened on purpose (a Save dialog) is named too.
- Apps built on Windows' newer app toolkit (Notepad, Settings, Terminal, Photos) draw their
  questions inside their own window instead. For those the reply ends with
  `Note: a dialog is open: "Notepad" in "*x - Notepad": "Do you want to save changes to x.txt?"`,
  usually already on the reply of the key that caused it. Answer it before anything else.
  In-window questions of other apps (a web page's pop-up) are not noted: take a Screenshot.
- This is evidence, not a guarantee: still verify important results.

## Shrunk screenshots

- Screens above 1920x1080, or `WINDOWS_MCP_SCREENSHOT_SCALE` below 1, shrink the image.
- A full (non-region) Screenshot or vision Snapshot then makes the image's own pixels the
  coordinates: click where you see a thing. Snapshot centres, the cursor, display boxes,
  `loc`/`locs`/`from_loc` and `region` all use the same shrunk space; the reply's
  `Coordinates:` line says so.
- A region image is a close-up and does not change the space; its `Coordinates:` line gives
  the pixel formula. For small text use Screenshot `zoom=true` (observe.md).
- App `window_loc`/`window_size` and DisplayInventory stay real screen pixels.
- `WINDOWS_MCP_RAW_COORDINATES=1` keeps plain screen pixels everywhere.
