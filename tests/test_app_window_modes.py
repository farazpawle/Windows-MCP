"""Round-2 C.3: App minimize / maximize / restore / close / list / move, by name or handle."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import win32con

from windows_mcp.desktop import window_control
from windows_mcp.desktop.service import Desktop
from windows_mcp.desktop.views import Status
from windows_mcp.tools import app as app_tool_module
from windows_mcp.uia.core import Rect

WC = "windows_mcp.desktop.window_control"


def _window(name, handle, status=Status.NORMAL, pid=None, box=(100, 50, 800, 600)):
    left, top, width, height = box
    return SimpleNamespace(
        name=name,
        handle=handle,
        process_id=pid or handle,
        status=status,
        bounding_box=SimpleNamespace(left=left, top=top, width=width, height=height),
    )


def _desktop(windows, active=None):
    desktop = Desktop.__new__(Desktop)
    desktop.desktop_state = None
    desktop.get_windows = lambda: (list(windows), set())
    desktop.get_active_window = lambda: active
    return desktop


# --- picking the window --------------------------------------------------------------


class TestPickWindow:
    def test_by_handle(self):
        windows = [_window("Notepad", 11), _window("Notepad", 22)]
        window, note = _desktop(windows).pick_window(None, 22)
        assert window.handle == 22 and note == ""

    def test_unknown_handle_points_to_list(self):
        with pytest.raises(ValueError, match="mode='list'"):
            _desktop([_window("Notepad", 11)]).pick_window(None, 99)

    def test_name_and_handle_together_refused(self):
        with pytest.raises(ValueError, match="not both"):
            _desktop([_window("Notepad", 11)]).pick_window("Notepad", 11)

    def test_no_target_uses_live_foreground_window(self):
        front = _window("Front", 5)
        window, _ = _desktop([], active=front).pick_window(None, None)
        assert window is front

    def test_no_target_refused_when_required(self):
        with pytest.raises(ValueError, match="name or handle"):
            _desktop([], active=_window("Front", 5)).pick_window(None, None, required=True)

    def test_name_keeps_other_matches_note(self):
        windows = [_window("Notepad", 11), _window("Notepad", 22)]
        window, note = _desktop(windows).pick_window("Notepad", None)
        assert window.handle == 11 and "Also matched" in note

    def test_exact_title_wins_without_a_note(self):
        # R3-6: partial matches are not "also matched" when the name is a whole title.
        windows = [_window("Notepad - draft.txt", 11), _window("notepad", 22)]
        window, note = _desktop(windows).pick_window("Notepad", None)
        assert window.handle == 22 and note == ""


# --- minimize / maximize / restore -----------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "flag", "state"),
    [
        ("minimize", win32con.SW_MINIMIZE, "minimized"),
        ("maximize", win32con.SW_MAXIMIZE, "maximized"),
        ("restore", win32con.SW_RESTORE, "normal"),
    ],
)
def test_show_modes_report_the_state_read_back(mode, flag, state):
    with (
        patch(f"{WC}.is_window_hung", return_value=False),
        patch(f"{WC}.win32gui.ShowWindow") as show,
        patch(f"{WC}.uia.IsIconic", return_value=state == "minimized"),
        patch(f"{WC}.uia.IsZoomed", return_value=state == "maximized"),
    ):
        reply = window_control.show(_window("Notepad", 7), mode)
    show.assert_called_once_with(7, flag)
    assert reply == f"Notepad is now {state}."


def test_show_refuses_hung_window():
    with (
        patch(f"{WC}.is_window_hung", return_value=True),
        patch(f"{WC}.win32gui.ShowWindow") as show,
    ):
        with pytest.raises(ValueError, match="not responding"):
            window_control.show(_window("Stuck", 7), "minimize")
    show.assert_not_called()


# --- close -------------------------------------------------------------------------------


def test_close_posts_wm_close_and_confirms():
    with (
        patch(f"{WC}.win32gui.PostMessage") as post,
        patch(f"{WC}.win32gui.IsWindow", return_value=False),
    ):
        reply = window_control.close(_window("Notepad", 7))
    post.assert_called_once_with(7, win32con.WM_CLOSE, 0, 0)
    assert reply == "Closed Notepad."


def test_close_says_when_window_stays_open():
    with (
        patch(f"{WC}.win32gui.PostMessage"),
        patch(f"{WC}.win32gui.IsWindow", return_value=True),
        patch(f"{WC}.sleep"),
    ):
        reply = window_control.close(_window("Notepad", 7))
    assert "still open" in reply and "save" in reply


# --- list --------------------------------------------------------------------------------


def test_list_shows_handle_pid_process_state_and_title():
    windows = [
        _window("notes.txt - Notepad", 1234, pid=4120),
        _window("Inbox", 5678, Status.MAXIMIZED, pid=8812, box=(-8, -8, 1936, 1048)),
    ]
    names = {4120: "notepad.exe", 8812: "chrome.exe"}
    with (
        patch(f"{WC}.Process", side_effect=lambda pid: SimpleNamespace(name=lambda: names[pid])),
        patch(f"{WC}.win32gui.GetForegroundWindow", return_value=1234),
    ):
        reply = window_control.format_list(windows)
    # Round-4 R4-I6: front to back, the window in front marked.
    assert reply.splitlines() == [
        "2 windows, front to back:",
        'handle=1234 pid=4120 notepad.exe Normal at (100,50) size 800x600 "notes.txt - Notepad"'
        " (front)",
        'handle=5678 pid=8812 chrome.exe Maximized at (-8,-8) size 1936x1048 "Inbox"',
    ]


def _list_with_front(front, title="", class_name=""):
    with (
        patch(f"{WC}.Process", side_effect=lambda pid: SimpleNamespace(name=lambda: "notepad.exe")),
        patch(f"{WC}.win32gui.GetForegroundWindow", return_value=front),
        patch(f"{WC}.win32gui.GetWindowText", return_value=title),
        patch(f"{WC}.win32gui.GetClassName", return_value=class_name),
    ):
        return window_control.format_list([_window("notes.txt - Notepad", 1234)]).splitlines()


def test_list_names_an_unlisted_front_window():
    # Round-5 R5-I3: the taskbar's hidden-icons panel in front left no "(front)" at all.
    lines = _list_with_front(999, class_name="TopLevelWindowForOverflowXamlIsland")
    assert lines[:2] == [
        "1 windows, front to back:",
        'In front, not listed: handle=999 class TopLevelWindowForOverflowXamlIsland ""',
    ]
    assert not any(line.endswith("(front)") for line in lines)


def test_list_unlisted_front_window_shows_its_title():
    lines = _list_with_front(999, title="Task Switching", class_name="XamlExplorerHostIslandWindow")
    assert lines[1] == (
        'In front, not listed: handle=999 class XamlExplorerHostIslandWindow "Task Switching"'
    )


def test_list_says_when_nothing_is_in_front():
    assert _list_with_front(0)[1] == "Nothing is in front (the desktop has no foreground window)."


def test_list_adds_no_line_when_front_is_listed():
    assert len(_list_with_front(1234)) == 2


def test_list_empty():
    assert window_control.format_list([]) == "No windows found on the desktop."


# --- move to another display -------------------------------------------------------------


def _display(index, left, right, height=1080):
    rect = Rect(left, 0, right, height)
    return SimpleNamespace(index=index, rect=rect, work_rect=Rect(left, 0, right, height - 40))


DISPLAYS = [_display(0, 0, 1920), _display(1, 1920, 2720, 600)]


def _move(rect, display, zoomed=False, iconic=False):
    rects = [rect]
    with (
        patch(f"{WC}.is_window_hung", return_value=False),
        patch(f"{WC}.uia.IsIconic", return_value=iconic),
        patch(f"{WC}.uia.IsZoomed", return_value=zoomed),
        patch(f"{WC}.win32gui.GetWindowRect", side_effect=lambda h: rects[-1]),
        patch(f"{WC}.win32gui.ShowWindow") as show,
        patch(
            f"{WC}.win32gui.MoveWindow",
            side_effect=lambda h, x, y, w, ht, r: rects.append((x, y, x + w, y + ht)),
        ) as move,
    ):
        reply = window_control.move_to_display(_window("Notepad", 7), DISPLAYS, display)
    return reply, move, show


def test_move_keeps_offset_and_fits_the_target():
    # 1000x500 at (100,50) on display 0 -> display 1 is 800x560 of work area.
    reply, move, _ = _move((100, 50, 1100, 550), 1)
    move.assert_called_once_with(7, 1920, 50, 800, 500, True)
    assert reply == "Moved Notepad to display 1 at (1920,50)."


def test_move_small_window_keeps_offset():
    _, move, _ = _move((100, 50, 500, 350), 1)
    move.assert_called_once_with(7, 2020, 50, 400, 300, True)


def test_move_maximized_window_is_maximized_again():
    reply, move, show = _move((0, 0, 1920, 1040), 1, zoomed=True)
    assert [c.args[1] for c in show.call_args_list] == [
        win32con.SW_RESTORE,
        win32con.SW_MAXIMIZE,
    ]
    assert "maximized" in reply


def test_move_refuses_minimized_window():
    with pytest.raises(ValueError, match="minimized"):
        _move((0, 0, 10, 10), 1, iconic=True)


def test_move_refuses_unknown_display():
    with pytest.raises(ValueError, match="display 5"):
        _move((0, 0, 10, 10), 5)


# --- the App tool's argument rules ------------------------------------------------------


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _app(desktop):
    mcp = FakeMCP()
    app_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    tool = mcp.tools["App"]
    return lambda **kwargs: asyncio.run(tool(**kwargs))


def test_tool_passes_handle_and_display():
    desktop = MagicMock()
    _app(desktop)(mode="move", handle="1234", display=1)
    desktop.app.assert_called_once_with("move", None, None, None, handle=1234, display=1)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ({"mode": "move", "name": "Notepad"}, "display"),
        ({"mode": "minimize", "name": "Notepad", "display": 1}, "display"),
        ({"mode": "list", "name": "Notepad"}, "list"),
        ({"mode": "launch", "name": "Notepad", "handle": 5}, "handle"),
        ({"mode": "close", "name": "Notepad", "window_size": [5, 5]}, "resize"),
        ({"mode": "close", "handle": True}, "handle"),
    ],
)
def test_tool_refuses_wrong_argument_mixes(args, message):
    desktop = MagicMock()
    with pytest.raises(ValueError, match=message):
        _app(desktop)(**args)
    desktop.app.assert_not_called()


# --- close needs a target; switch and resize accept a handle ----------------------------


def test_close_without_name_or_handle_is_refused():
    desktop = _desktop([_window("Claude", 1)], active=_window("Claude", 1))
    with patch(f"{WC}.win32gui.PostMessage") as post:
        with pytest.raises(ValueError, match="name or handle"):
            desktop.app("close")
    post.assert_not_called()


def test_switch_by_handle_picks_that_window():
    desktop = _desktop([_window("Notepad", 11), _window("Notepad", 22)])
    with (
        patch("windows_mcp.desktop.service.uia.IsIconic", return_value=False),
        patch.object(Desktop, "bring_window_to_top") as bring,
        patch("windows_mcp.desktop.service.win32gui.GetForegroundWindow", return_value=22),
    ):
        reply = desktop.app("switch", handle=22)
    bring.assert_called_once_with(22)
    assert reply == "Switched to Notepad window."


def test_resize_by_handle_picks_that_window():
    ctrl = MagicMock(BoundingRectangle=Rect(100, 100, 900, 700))
    desktop = _desktop([_window("Notepad", 11), _window("Notepad", 22)])
    desktop.get_displays = lambda: [SimpleNamespace(rect=Rect(0, 0, 1920, 1080))]
    with (
        patch("windows_mcp.desktop.service.uia.ControlFromHandle", return_value=ctrl) as from_h,
        patch("windows_mcp.desktop.service.uia.DwmGetWindowExtendFrameBounds", return_value=None),
    ):
        desktop.app("resize", size=[800, 600], handle=22)
    from_h.assert_called_once_with(22)
    ctrl.MoveWindow.assert_called_once_with(100, 100, 800, 600)
