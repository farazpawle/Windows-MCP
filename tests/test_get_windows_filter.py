"""Which top-level windows Desktop.get_windows lists (round-3 R3-1).

A window that cannot be maximized (a fixed-size dialog, an app while it shows a
modal question) is still a real window the caller must be able to find by name.
"""

from unittest.mock import MagicMock, patch

import win32con

import windows_mcp.uia as uia
from windows_mcp.desktop.service import Desktop
from windows_mcp.desktop.views import Status


def _control(hwnd: int, name: str, can_max: bool = True, has_pattern: bool = True):
    control = MagicMock(spec=uia.WindowControl)
    control.Name = name
    control.NativeWindowHandle = hwnd
    control.ProcessId = 1000 + hwnd
    control.BoundingRectangle.isempty.return_value = False
    control.GetChildren.return_value = [object()]
    pattern = MagicMock(CanMinimize=can_max, CanMaximize=can_max)
    control.GetPattern.return_value = pattern if has_pattern else None
    return control


def _listed(controls: dict, tool_windows=(), foreground: int = 0) -> list[str]:
    desktop = Desktop.__new__(Desktop)
    desktop.get_window_status = lambda c: Status.NORMAL
    desktop.is_window_browser = lambda c: False
    desktop._window_box = lambda c: None

    def ex_style(hwnd, index):
        return win32con.WS_EX_TOOLWINDOW if hwnd in tool_windows else 0

    with (
        patch.object(uia, "ControlFromHandle", side_effect=controls.__getitem__),
        patch.object(uia, "GetForegroundWindow", return_value=foreground),
        patch("windows_mcp.desktop.service.win32gui.GetWindowLong", side_effect=ex_style),
        patch("windows_mcp.desktop.service.Window", side_effect=lambda **kw: kw["name"]),
    ):
        windows, _ = desktop.get_windows(set(controls))
    return sorted(windows)


def test_fixed_size_dialog_is_listed():
    controls = {1: _control(1, "Notepad"), 2: _control(2, "Fixed Dialog", can_max=False)}
    assert _listed(controls) == ["Fixed Dialog", "Notepad"]


def test_helper_windows_stay_out():
    controls = {
        1: _control(1, "Notepad"),
        2: _control(2, "Twinkle Tray Panel", can_max=False),  # tool window
        3: _control(3, "Windows Input Experience", has_pattern=False),
        4: _control(4, "", can_max=False),  # untitled, not in front
    }
    assert _listed(controls, tool_windows={2}) == ["Notepad"]


def test_front_window_is_listed_even_if_tool_window():
    # Alerts such as an antivirus pop-up may be tool windows; in front they still count.
    controls = {1: _control(1, "Notepad"), 2: _control(2, "Threat blocked", can_max=False)}
    assert _listed(controls, tool_windows={2}, foreground=2) == ["Notepad", "Threat blocked"]
