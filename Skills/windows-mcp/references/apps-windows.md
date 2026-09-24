# Apps and windows: App

## launch_executable

- `executable` = full path, or a bare name found on PATH (`notepad.exe`; other bare names:
  see known-gaps.md). `args` = argv **list**, optional `cwd`.
  Example: `C:\Program Files\PowerShell\7\pwsh.exe` with
  `["-NoProfile","-STA","-WindowStyle","Hidden","-File","<path>"]`.
- Returns `{pid,...}`: **save the PID** for later kills. The PID can be a stub that hands off
  and exits (`notepad.exe` returned one PID while the window belonged to another). Before a
  kill, check the PID is still alive; if not, find the real one with Process `list`.
- A new Notepad on a missing file first asks "create a new file?"; that dialog is a window
  like any other (listed, closable).

## launch

- By Start Menu name, fuzzy ("calc" opens Calculator). An unknown name replies
  "... not found in start menu."; an empty name is refused.
- The reply names the window found, with its real title ("Calculator launched.").
- Returns no PID: use `launch_executable` when you will need to kill it.
- Store apps such as Notepad may open a new tab in an already-running window instead of a new
  process.

## How a window name matches (switch, resize and the window modes)

- Fuzzy match on the **window title**, then a plain part of the title ("Edge", "tri.txt"),
  then the program name ("msedge", "notepad.exe").
- A name equal to a whole title (case ignored) picks that window outright.
- When a name matches several windows, the best match is used and the others are listed
  ("Also matched ..."): only same-titled windows when the name was a whole title.
- An empty name is refused.
- `handle=<number from list>` instead of `name` picks one of several same-named windows; every
  window mode, `switch` and `resize` included, takes it.
- Windows that cannot be maximized are included (a fixed-size dialog, an app showing a modal
  question, an alert in front), also for Click `window=`.

## switch

- Brings the window to the front. In Claude Desktop the approval click undoes it (golden
  rule 1).

## resize

- `name`, `window_loc=[x,y]`, `window_size=[w,h]`; either one alone keeps the other.
- The outer window rectangle is set exactly; the visible frame is a few px smaller (invisible
  borders).
- With no `name` it acts on the window in front right now.
- A maximized or minimized window is refused ("Cannot resize ...: it is maximized"): restore
  first. A `window_size` that is not two positive numbers, or a `window_loc` fully off every
  display, is refused.

## minimize / maximize / restore / close / list / move

- `minimize`, `maximize`, `restore`: named or front window; the reply is the state read back
  ("Notepad is now minimized.").
- `close`: like the X button, never a kill; **name or handle required**. Replies "Closed X."
  or says it is still open (e.g. asking to save).
- `list`: one line per window: `handle=... pid=... program State "title"`.
- `move` with `display=N` (numbering as in DisplayInventory): keeps the offset but moves the
  window up/left to stay inside the work area (taskbar excluded), shrinks it to fit, and
  re-maximizes a maximized window; a minimized one is refused. Works across screens with
  different scaling.
