---
Title: What's new in this version
Description: What this version of Windows-MCP adds and fixes compared with the original CursorTouch release on PyPI - new tools (Steps, FindText), new abilities in Click, Type, Move, Shortcut, App, Clipboard, Process and WaitFor, safety checks, honest replies and errors, reliability fixes, and the Claude Desktop extension on every release.
---

# What's new in this version

This version started from [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP)
and has since had more than 240 changes, backed by unit tests and live tests on a real desktop. The comparison below is
against the original's PyPI release as it was tested here; some of it may have reached the
original since.

## New tools

- **Steps**: runs up to 20 clicks, keystrokes, scrolls, moves and waits in one call. Each step
  keeps its own checks, the run stops at the first failure or surprise window, and Claude
  Desktop asks for one approval instead of twenty.
- **FindText**: finds words on screen by OCR (Windows' built-in text recognition), for games,
  remote desktops and canvas apps that expose no elements. It returns clickable positions and
  can read one window only.

## New abilities

- **Click by name:** `element="button:Save"` finds the element at the moment of the click, with
  no Snapshot first. Also Shift/Ctrl/Alt clicks (`modifiers`), triple clicks, and `expect=`,
  which refuses to click when what is at the spot is not what was expected.
- **Type** anywhere the caret is (no click needed), jump to the start or end of the whole field
  (`field_start`, `field_end`), and a reply showing what the field now holds.
- **Move:** exact drags from a start point, hold a mouse button down and steer before letting
  go, modifier drags (Ctrl to copy), and "where is the cursor?".
- **Shortcut:** `repeat`, `hold` (for games and apps that check a key is held), a
  `release_all` panic button, and computer-use key names.
- **App:** minimize, maximize, restore, close, list (handle, PID, state, position, size) and
  move to another display; `handle=` picks one of several same-named windows; `launch_executable`
  returns the PID and accepts bare names like `notepad.exe`.
- **WaitFor:** wait for text on screen by OCR (`screen_text`), for the screen to change
  (`screen_changed`) or to settle (`screen_idle`); `text_exists` also reads text inside documents.
- **Clipboard:** images and copied files, not just text; save a clipboard image to a file.
- **Process:** see start time and command line (`details=true`), sort by CPU.
- **Screenshot:** `zoom` for small text, and shrunk screenshots use the image's own pixels as
  coordinates, so an agent clicks where it sees a thing.
- **Action log:** an optional readable log of every tool call, with secrets hidden.

## Safer

- Before a `label=` or `element=` action, the tool checks the element is still there and
  refuses if another window (such as an approval prompt) covers it.
- Points off every screen are refused instead of being clicked at the screen edge.
- A held mouse button or key is released before the next action, and a misspelled Shortcut
  key is refused before anything is pressed (no more stuck Ctrl).
- Every input reply names any new window or in-app dialog that appeared ("save changes?"),
  so the next keys do not land in it by accident.
- FileSystem never overwrites unless asked; Registry never deletes a whole hive and treats
  `*` and `?` as plain characters; Process kills by exact name only.
- VS Code-family windows are never read (one read froze VS Code), and a frozen
  ("Not Responding") app no longer hangs Snapshot, WaitFor or App.

## Honest replies

- Failures are real tool errors, not success messages with an error inside.
- Replies report the effect, not just the request: the element clicked, the field's new text,
  the new scroll position, the real title of a launched window.
- PowerShell errors are reported (non-zero exit is an error, timeouts really stop the command),
  and Notification fails on an app id that would show nothing.
- Long replies stop at 50,000 characters with a note.

## Faster and more reliable

- Registry works directly instead of starting PowerShell (under 0.01 s a call).
- Typing sends real keystrokes: accents, CJK and emoji come out right, and the clipboard is
  never touched.
- Snapshot with a `region` reads only the windows visible there (0.3 s instead of 22 s in one
  test), and a cap stops huge lists from stalling it.
- The screen layout is re-read on every call, so a monitor plugged in later just works.
- Scrape checks certificates against the Windows store, so it works behind antivirus HTTPS
  inspection.

## Easier to install and use

- A ready-to-install Claude Desktop extension (`.mcpb`) is attached to every
  [release](https://github.com/farazpawle/Windows-MCP/releases).
- A [field guide](../Skills/windows-mcp/SKILL.md) skill teaches agents to use the tools well.
- Short [install](install.md), [tools](tools.md), [settings](settings.md) and
  [remote access](remote-access.md) guides replace the single long page.
