"""Name windows and dialogs that appeared since the last input action (round-3 R3-N1).

Both round-3 surprises, Notepad's "save changes?" question and an Avast alert, were
found only by accident, and every later action went to the wrong window. Input tools
now add a note naming any top-level window that was not there at the previous action,
and any dialog drawn inside the front window of a XAML app (round-4 R4-5): Notepad's
question is a UIA element in its own window, with no window of its own.
"""

import ctypes
import logging
from functools import wraps

import win32con
import win32gui
import win32process
from psutil import Process

import windows_mcp.uia as uia
from windows_mcp.desktop.utils import is_window_hung

logger = logging.getLogger(__name__)

_DWMWA_CLOAKED = 14

# Handle -> title of the windows seen after the last input action; None until the first.
# ponytail: one module-wide baseline, shared by every client of this server process.
_seen: dict[int, str] | None = None

# UIA runtime ids of the in-window dialogs reported after the last input action.
_seen_dialogs: set[tuple] = set()

# Child window classes of apps built on XAML (WinUI 3, UWP, XAML Islands): the ones that
# draw modal dialogs inside their own window.
_XAML_HOSTS = {
    "Microsoft.UI.Content.DesktopChildSiteBridge",
    "Windows.UI.Core.CoreWindow",
    "Windows.UI.Composition.DesktopWindowContentBridge",
}


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


def _is_xaml_window(handle: int) -> bool:
    classes: set[str] = set()
    win32gui.EnumChildWindows(
        handle, lambda c, _: classes.add(win32gui.GetClassName(c)) or True, None
    )
    return not classes.isdisjoint(_XAML_HOSTS)


def _question(names: list[str], dialog_name: str) -> str:
    """The dialog's question: its first text that is not its title ("Notepad")."""
    return next((n for n in names if n and n != dialog_name), "")


def _front_dialogs() -> dict[tuple, str]:
    """Dialogs drawn inside the front window, as {UIA runtime id: description}.

    Only XAML apps are searched: the UIA search takes ~0.03-0.1 s there and up to
    ~0.18 s in Excel, whose dialogs are separate windows anyway.
    """
    front = win32gui.GetForegroundWindow()
    if not front or is_window_hung(front) or not _is_xaml_window(front):
        return {}
    ia = uia.core._AutomationClient.instance().IUIAutomation
    found = ia.ElementFromHandle(front).FindAll(
        uia.TreeScope.TreeScope_Descendants,
        ia.CreatePropertyCondition(uia.PropertyId.IsDialogProperty, True),
    )
    text_type = ia.CreatePropertyCondition(
        uia.PropertyId.ControlTypeProperty, uia.ControlType.TextControl
    )
    title = win32gui.GetWindowText(front)
    dialogs = {}
    for i in range(found.Length):
        dialog = found.GetElement(i)
        texts = dialog.FindAll(uia.TreeScope.TreeScope_Descendants, text_type)
        names = [texts.GetElement(j).CurrentName for j in range(texts.Length)]
        question = _question(names, dialog.CurrentName)
        message = f': "{question}"' if question else ""
        dialogs[tuple(dialog.GetRuntimeId() or ())] = (
            f'"{dialog.CurrentName}" in "{title}"{message}'
        )
    return dialogs


def _note(new: dict[int, str]) -> str:
    parts = []
    for handle, title in new.items():
        pid, exe = _process_of(handle)
        parts.append(f'"{title}" (handle={handle}, pid={pid} {exe})')
    what = "a new window appeared" if len(parts) == 1 else "new windows appeared"
    return f"\n\nNote: {what}: {', '.join(parts)}."


def _dialog_note() -> str:
    """Note naming in-window dialogs not reported after the previous action."""
    global _seen_dialogs
    try:
        dialogs = _front_dialogs()
    except Exception as e:  # a window closing mid-search; never fail the action
        logger.debug("In-window dialog check failed: %s", e)
        return ""
    new = [text for rid, text in dialogs.items() if rid not in _seen_dialogs]
    _seen_dialogs = set(dialogs)
    return "".join(f"\n\nNote: a dialog is open: {text}." for text in new)


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
        if not isinstance(reply, str):
            return reply
        return reply + (_note(new) if new else "") + _dialog_note()

    return wrapper
