# Observe: Screenshot, Snapshot, FindText, WaitFor, Wait, DisplayInventory

## DisplayInventory

- Monitor bounds, DPI and scale (1.0 on this PC). Run it first when coordinates look off.

## Screenshot

- The fast image, with no UI tree and no window list (it says "Skipped (screenshot-only…)");
  use Snapshot for windows.
- `display=[n]` picks a display; a bad index is an error that lists the valid ones.
- It captures pending approval prompts too.
- `width_reference_line` / `height_reference_line` draw a grid; either one alone works.
- On one screen, full captures use the same method as `region` captures (header
  "Screenshot Backend: dxcam"), which shows pop-ups such as Avast's alert. Several screens:
  see known-gaps.md.
- `zoom=true` with a `region` enlarges it to about 1280 px wide at full resolution, for small
  text; keep clicking with full-screen coordinates.

## Snapshot

- Each element line in the text tree starts with `[label:N]`: the id `label=` takes in Click,
  Type and MultiSelect. Numbers do not follow the tree's order; read them from the line.
- Only Snapshot sets labels; WaitFor, Screenshot, App and Scrape leave them alone.
- Before acting on a label the tool re-checks the element is still at its spot (input.md,
  "Spot check") and refuses with "take a new Snapshot" if the screen changed.
- `region` keeps only elements inside the rectangle and reads only windows visible in it (a
  taskbar-strip Snapshot took 0.3 s instead of 22 s).
- Elements of background windows that another window covers are left out: their click would
  hit the covering window.
- At most 500 elements (`WINDOWS_MCP_MAX_TREE_ELEMENTS`); the truncation message says so. The
  focused window is read first; a busy one (Excel sheet, long document: one element per word)
  can fill the cap alone: use `region` or raise the cap. Other windows fill the rest.
- `display=[0]`, `[1]` and `[0,1]` work. Coordinates are virtual-desktop (a second screen to
  the right starts at x=1920 here) and clicks there land; the capture border shows on the
  screen captured. The screen layout is re-read on every call.
- With `use_vision=true` the reference-line grid is drawn on the image; either line alone works.
- In a browser, `use_dom=true` lists the page's links and fields with labels Click accepts.

## FindText

- Text on screen by OCR, for apps with no UI tree (games, remote desktops, canvas apps).
  Prefer Snapshot or Click `element=` where elements exist.
- `text`: case ignored, words in order on one line, may be part of a word. Optional `region`.
- Lists every spot with a clickable `(x,y)`, within 1 px of the real centre.
- Not found is a normal reply, not an error.
- ~1.2 s for the full screen, ~0.4 s for a small region.
- It reads visible pixels only: tiny, stylised or low-contrast text can be missed. A phrase
  may run across table columns on one row ("North 460 units"). A short number alone in a
  column can be missed in some fonts (Consolas "460"): then search a longer neighbour.

## WaitFor

- Cheaper than repeated Snapshots. Returns the time and attempts; on timeout it is an error
  that names the window actually active.
- `active_window` takes `window_name`. `text_exists`, `element_exists`, `element_enabled` and
  `focused_element` take `text`.
- `text_exists` searches the active window, or the windows matching `window_name`, including
  plain labels ("Saved").
- `screen_text` (`text`, optional `region`, no `window_name`) reads the screen by OCR on each
  look and reports where the text is: ~1.2 s a look full screen, under 1 s for a small region.
- `screen_changed` waits until the screen (or `region`) differs from how it looked when
  WaitFor started, and says where (`changed around [l, t, r, b]`, a window's drop shadow
  included). It misses a change that already happened during the click before it.
- `screen_idle` waits until nothing changed for `settle` seconds (default 1, less than
  `timeout`). Use it after a click instead of a fixed Wait.
- Both ignore tiny changes: under 100 changed pixels, or under 1% of a small `region` (never
  under 20). A blinking caret is ignored; an 80x30 region around the taskbar clock catches the
  minute changing.
- Both watch every screen unless `region` is given, so a clock or animation elsewhere can keep
  `screen_idle` from settling: give a `region`.

## Wait

- Sleeps N seconds (`Wait(3)` took 3.4 s). Decimals work (`0.5`), at most 300; negative or
  non-numeric values are refused. Prefer WaitFor.

## Frozen-app check

If Snapshot, WaitFor or App switch stalls, list "Not Responding" windows with PowerShell:

```powershell
Add-Type -Name U -Namespace W -MemberDefinition '[DllImport("user32.dll")] public static extern bool IsHungAppWindow(IntPtr h);'
Get-Process | ? { $_.MainWindowHandle -ne 0 -and [W.U]::IsHungAppWindow($_.MainWindowHandle) } | select Id,ProcessName,MainWindowTitle
```

Then ask the user to close or restart that app.
