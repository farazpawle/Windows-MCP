"""Name windows that appeared since the last input action (round-3 R3-N1).

Both round-3 surprises, Notepad's "save changes?" question and an Avast alert, were
found only by accident, and every later action went to the wrong window. Input tools
now add a note naming any top-level window that was not there at the previous action.
"""

import ctypes
import logging
from functools import wraps

import win32con
import win32gui
import win32process
from psutil import Process

logger = logging.getLogger(__name__)

_DWMWA_CLOAKED = 14

# Handle -> title of the windows seen after the last input action; None until the first.
# ponytail: one module-wide baseline, shared by every client of this server process.
_seen: dict[int, str] | None = None


def _cloaked(handle: int) -> bool:
    # Suspended Store apps and windows on other virtual desktops are "visible" but not shown.
    value = ctypes.c_int(0)
    result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        handle, _DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value)
    )
    return result == 0 and value.value != 0


def _top_windows() -> dict[int, str]:
    """Visible, titled, uncloaked top-level windows that are not tool windows."""
    found: dict[int, str] = {}

    def add(handle: int, _) -> bool:
        try:
            if (
                win32gui.IsWindowVisible(handle)
                and (title := win32gui.GetWindowText(handle))
                and not win32gui.GetWindowLong(handle, win32con.GWL_EXSTYLE)
                & win32con.WS_EX_TOOLWINDOW
                and not _cloaked(handle)
            ):
                found[handle] = title
        except Exception as e:  # a window closing mid-enumeration
            logger.debug("Skipped window %s: %s", handle, e)
        return True

    win32gui.EnumWindows(add, None)
    return found


def _process_of(handle: int) -> tuple[int, str]:
    pid = win32process.GetWindowThreadProcessId(handle)[1]
    try:
        return pid, Process(pid).name()
    except Exception:
        return pid, "?"


def _note(new: dict[int, str]) -> str:
    parts = []
    for handle, title in new.items():
        pid, exe = _process_of(handle)
        parts.append(f'"{title}" (handle={handle}, pid={pid} {exe})')
    what = "a new window appeared" if len(parts) == 1 else "new windows appeared"
    return f"\n\nNote: {what}: {', '.join(parts)}."


def note_new_windows(func):
    """Append a note naming windows that appeared since the last input action.

    Apply directly on an input tool function, inside @with_analytics.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        global _seen
        if _seen is None:
            _seen = _top_windows()
        reply = func(*args, **kwargs)
        now = _top_windows()
        new = {h: t for h, t in now.items() if h not in _seen}
        _seen = now
        if new and isinstance(reply, str):
            return reply + _note(new)
        return reply

    return wrapper
