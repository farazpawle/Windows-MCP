"""App's window modes: minimize, maximize, restore, close, list and move to another display.

Each function acts on a window Desktop.pick_window already chose. Coordinates are real
screen pixels, like App resize.
"""

from time import sleep

import win32con
import win32gui
from psutil import Process

import windows_mcp.uia as uia
from windows_mcp.desktop.utils import is_window_hung

_SHOW_FLAGS = {
    "minimize": win32con.SW_MINIMIZE,
    "maximize": win32con.SW_MAXIMIZE,
    "restore": win32con.SW_RESTORE,
}


def _state(handle: int) -> str:
    if uia.IsIconic(handle):
        return "minimized"
    if uia.IsZoomed(handle):
        return "maximized"
    return "normal"


def _refuse_hung(window) -> None:
    # ShowWindow and MoveWindow wait on the window's own thread, so a hung window
    # would hang the tool call too.
    if is_window_hung(window.handle):
        raise ValueError(f"{window.name} is not responding; try again once it recovers.")


def show(window, mode: str) -> str:
    """Minimize, maximize or restore *window*; the reply is the state read back."""
    _refuse_hung(window)
    win32gui.ShowWindow(window.handle, _SHOW_FLAGS[mode])
    return f"{window.name} is now {_state(window.handle)}."


def close(window) -> str:
    """Ask *window* to close (WM_CLOSE, as its X button does); never kills the process."""
    win32gui.PostMessage(window.handle, win32con.WM_CLOSE, 0, 0)
    for _ in range(20):  # up to ~2 s
        if not win32gui.IsWindow(window.handle):
            return f"Closed {window.name}."
        sleep(0.1)
    return (
        f"Asked {window.name} to close, but it is still open "
        "(it may be asking to save changes; take a Screenshot)."
    )


def format_list(windows) -> str:
    if not windows:
        return "No windows found on the desktop."
    lines = [f"{len(windows)} windows:"]
    for window in windows:
        try:
            exe = Process(window.process_id).name()
        except Exception:
            exe = "?"
        lines.append(
            f'handle={window.handle} pid={window.process_id} {exe} {window.status.value} "{window.name}"'
        )
    return "\n".join(lines)


def _area(display):
    return display.work_rect or display.rect


def move_to_display(window, displays, index: int) -> str:
    """Move *window* to display *index*, keeping its offset and fitting it inside the work area.

    A maximized window is restored, moved and maximized again, so it fills the new display.
    """
    target = next((d for d in displays if d.index == index), None)
    if target is None:
        known = ", ".join(str(d.index) for d in displays) or "none"
        raise ValueError(f"There is no display {index} (displays: {known}; see DisplayInventory).")
    _refuse_hung(window)
    handle = window.handle
    if uia.IsIconic(handle):
        raise ValueError(f"{window.name} is minimized; restore it first.")
    was_maximized = bool(uia.IsZoomed(handle))
    if was_maximized:
        win32gui.ShowWindow(handle, win32con.SW_RESTORE)

    left, top, right, bottom = win32gui.GetWindowRect(handle)
    cx, cy = (left + right) // 2, (top + bottom) // 2
    source = next(
        (
            d
            for d in displays
            if d.rect.left <= cx < d.rect.right and d.rect.top <= cy < d.rect.bottom
        ),
        target,
    )
    src, dst = _area(source), _area(target)
    width = min(right - left, dst.width())
    height = min(bottom - top, dst.height())
    x = min(max(dst.left + left - src.left, dst.left), dst.right - width)
    y = min(max(dst.top + top - src.top, dst.top), dst.bottom - height)
    win32gui.MoveWindow(handle, x, y, width, height, True)
    if was_maximized:
        win32gui.ShowWindow(handle, win32con.SW_MAXIMIZE)
        return f"Moved {window.name} to display {index} (maximized)."
    # Read back: a display with another scale makes the window resize itself.
    new_left, new_top, _, _ = win32gui.GetWindowRect(handle)
    return f"Moved {window.name} to display {index} at ({new_left},{new_top})."
