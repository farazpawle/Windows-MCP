# Input: Click, Type, MultiEdit, MultiSelect, Scroll, Move, Shortcut, Steps

Contents: Click · Spot check · Type · MultiEdit · MultiSelect · Scroll · Move · Shortcut · Steps ·
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
- `expect="Save"` with `loc`: before clicking, the element at the point or one of its first
  three parents must have a name containing "Save" (case ignored), else nothing is clicked and
  the error names what is there (`found pane in "<pop-up>"`). Use it when a pop-up may have
  covered the spot since the last Screenshot. Costs ~0.005 s. Always refuses on a VS
  Code-family or not-responding window (never read).

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
- `expect=` works as on Click (needs `loc` or `label`): nothing is clicked or typed when the
  field at the point is not named like it.
- `clear=true` empties the field first, old-style boxes that ignore Ctrl+A included. Empty
  `text` with `clear=true` just clears it. Never in an Explorer file list: it sends Ctrl+A
  then Backspace, which goes up a folder.
- `caret_position`: `start` or `end` of the **current line** (Home/End); `field_start` or
  `field_end` of the **whole field** (Ctrl+Home/Ctrl+End). `press_enter=true` sends Enter
  (see golden rule 1).
- Accents, CJK and emoji are typed correctly. Text is sent as keystrokes and never touches
  the clipboard (2,000 characters arrived intact). Line breaks and tabs are real Enter and
  Tab key presses (in a form, Tab moves to the next field); braces are typed as-is. A
  622-character multi-line text takes under 1 s. Windows 11 Notepad can garble typed text
  (known-gaps.md): write documents with FileSystem instead.

## MultiEdit

- `locs=[[x,y,"text"],...]` or `labels=[[id,"text"],...]`. **Clears each field before typing**
  (it overwrites, it does not append).
- Every `locs` point is checked to be on screen before anything is typed. Each label is
  checked to be still at its spot just before its own field, since typing can reflow a form.
  The first failure stops the call with an error naming the item (`locs[1]`, `label 7`), what
  was done and what was not.
- `locs` items go first, then `labels` items.

## MultiSelect

- `locs=[[x,y],...]` or `labels=[id,...]`. `press_ctrl=true` Ctrl-multi-selects (the reply
  says "Ctrl-selected elements"); `press_ctrl=false` clicks in sequence ("Clicked in
  sequence"), so in a list the last click wins.
- Each label is checked just before its own click. When an earlier click moved it (a list
  that inserts or expands a row), the call stops before that click with an error naming the
  label and the clicks done; take a new Snapshot and carry on. `locs` points are not checked
  (there is nothing to compare against). Ctrl is always released.

## Scroll

- `loc`, `direction`, `wheel_times` (a whole number, 1 or more). **1 wheel = 3 lines.**
- `axis="horizontal"` (`type` is still accepted) scrolls sideways in any app. A direction that
  does not fit the axis (horizontal + up) is an error.
- `modifiers="ctrl"` with up/down zooms a page or document (2 notches took Notepad from 100%
  to 120%).
- The reply's "now at X% (was Y%)" is read once the position stops moving, so it is the
  final one. That makes a Scroll take ~0.2-0.3 s in plain boxes and ~0.5 s in apps that
  animate scrolling (Notepad animates ~0.3 s); at the end of a list, where nothing moves,
  ~0.5 s.

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

## Steps

- Several input steps in one call, for a fixed sequence (a Save As, a small form):
  `steps=[{"do": "click", "element": "button:Save"}, {"do": "type", "text": "hi"}, ...]`.
  `do` is `click`, `type`, `shortcut`, `scroll`, `move`, `wait_for` or `wait`; every other key
  is that tool's own argument, and each step keeps all of that tool's checks.
- Up to 20 steps; the waits (Wait, WaitFor `timeout` - 10 s when left out -, Move `duration`,
  Shortcut `hold`) may add up to 60 s. The whole list is checked first: an unknown `do`, a
  misspelled key or a missing argument is refused naming the step, and nothing runs.
- The run stops at the first step that fails, or whose reply names a new window or dialog,
  unless that step has `"allow_new_window": true`. The stop is a tool error listing what each
  step that ran replied and which steps did not run. Example, a pop-up on purpose:
  `[{"do": "shortcut", "shortcut": "win+r", "allow_new_window": true}, {"do": "wait_for",
  "condition": "active_window", "text": "Run", "timeout": 3}, {"do": "shortcut", "shortcut": "escape"}]`.
- No Screenshot mid-run: prefer `element=` and `wait_for` over `loc`, and put `expect=` on
  every `loc` click or Type after the first step (an earlier step can move things).
- The action log records each step as its own call, then the Steps call.
- One Claude Desktop approval covers the whole list (fewer focus-stealing prompts).
- Measured: a four-step click, type, click, wait_for on a test window took 0.65 s in one call.

## Coordinates

- Use Snapshot centres. Take a new Snapshot after any window move, resize or scroll: old
  coordinates go stale.

## What the replies report

- Click names the element it hit (`clicked button "Save" in "Notepad" at (…)`): with
  `element=` or `label=`, the element found; with `loc`, the one read at the point just before
  clicking. A `loc` click on a panel drawn inside an app's window (Notepad's Find and Replace)
  can name the element under the panel (`document "Text editor"`); click such buttons with
  `element=`. A title-less pop-up is named after the window that owns it.
- Type adds what the focused field now holds (`The field (edit "Search") now reads "…"`);
  password boxes are never shown. If the field then lacks the typed text it adds "Warning:
  the field does not contain the typed text exactly ..." (auto-correct, formatting or lost
  keys; it waits up to 2 s for a slow field first): read the field before going on.
- Scroll adds the scroll area's position (`list "Files" is now at 45% (was 30%)`) or says it
  could not be read.
- Both are read once the app has caught up (two readings 0.05 s apart agree, at most 0.3 s
  of waiting), so "now" matches what the next call finds.
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
