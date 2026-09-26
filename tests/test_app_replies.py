"""Round-2 3.9: App validates its inputs and its replies say what actually happened."""

import winreg
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from windows_mcp.desktop.service import Desktop
from windows_mcp.desktop.views import Status
from windows_mcp.tools.app import _resolve_executable
from windows_mcp.uia.core import Rect

SERVICE = "windows_mcp.desktop.service"


def _window(name, handle, status=Status.NORMAL):
    return SimpleNamespace(name=name, handle=handle, process_id=handle, status=status)


def _desktop(windows):
    desktop = Desktop.__new__(Desktop)
    desktop.desktop_state = None
    desktop.get_windows = lambda: (list(windows), set())
    desktop.get_displays = lambda: [SimpleNamespace(rect=Rect(0, 0, 1920, 1080))]
    return desktop


@pytest.fixture
def control():
    ctrl = MagicMock(BoundingRectangle=Rect(100, 100, 900, 700))
    with (
        patch(f"{SERVICE}.uia.ControlFromHandle", return_value=ctrl),
        patch(f"{SERVICE}.uia.DwmGetWindowExtendFrameBounds", return_value=None),
    ):
        yield ctrl


# Round-3 R3-I11, measured live: GetWindowRect (300,250,940,610) was visible (307,250,933,603),
# so resize put the visible window 7 px off from what window_loc/window_size asked.
@pytest.mark.parametrize(
    ("loc", "size", "moved", "reply"),
    [
        (None, [700, 400], (300, 250, 714, 407), "resized to 700x400 at 307,250."),
        ([400, 300], [500, 300], (393, 300, 514, 307), "resized to 500x300 at 400,300."),
        ([400, 300], None, (393, 300, 640, 360), "resized to 626x353 at 400,300."),
    ],
)
def test_resize_means_the_visible_window(loc, size, moved, reply):
    ctrl = MagicMock(BoundingRectangle=Rect(300, 250, 940, 610))
    with (
        patch(f"{SERVICE}.uia.ControlFromHandle", return_value=ctrl),
        patch(
            f"{SERVICE}.uia.DwmGetWindowExtendFrameBounds", return_value=Rect(307, 250, 933, 603)
        ),
    ):
        text, status = _desktop([_window("WMCP Harness", 1)]).resize_app("WMCP Harness", size, loc)
    assert status == 0
    ctrl.MoveWindow.assert_called_once_with(*moved)
    assert text.endswith(reply)


# a. window_size must be two positive numbers
@pytest.mark.parametrize("size", [[0, -5], [800], [800, 600, 1], [-1, 600]])
def test_resize_refuses_bad_size(size, control):
    reply, status = _desktop([_window("WMCP Harness", 1)]).resize_app("WMCP Harness", size=size)
    assert status == 1
    assert "window_size" in reply
    control.MoveWindow.assert_not_called()


def test_resize_refuses_one_number_location(control):
    reply, status = _desktop([_window("WMCP Harness", 1)]).resize_app("WMCP Harness", loc=[5])
    assert status == 1
    assert "window_loc" in reply
    control.MoveWindow.assert_not_called()


def test_resize_accepts_good_size(control):
    reply, status = _desktop([_window("WMCP Harness", 1)]).resize_app(
        "WMCP Harness", size=[800, 600]
    )
    assert status == 0
    control.MoveWindow.assert_called_once_with(100, 100, 800, 600)
    assert reply == "WMCP Harness resized to 800x600 at 100,100."  # c. real title


# b. a location that puts the window fully off every display is refused
def test_resize_refuses_fully_off_screen(control):
    reply, status = _desktop([_window("WMCP Harness", 1)]).resize_app(
        "WMCP Harness", loc=[-3000, 200]
    )
    assert status == 1
    assert "off" in reply and "display" in reply
    control.MoveWindow.assert_not_called()


def test_resize_allows_partly_off_screen(control):
    _, status = _desktop([_window("WMCP Harness", 1)]).resize_app("WMCP Harness", loc=[-700, 200])
    assert status == 0
    control.MoveWindow.assert_called_once_with(-700, 200, 800, 600)


# g. a maximised window is a refusal, not a status
def test_resize_of_maximised_window_is_worded_as_refusal(control):
    desktop = _desktop([_window("Calculator", 1, Status.MAXIMIZED)])
    reply, status = desktop.resize_app("Calculator", size=[400, 400])
    assert status == 1
    assert reply.startswith("Cannot resize Calculator")
    assert "maximized" in reply
    # Round-4 R4-I7: the hint named a keyboard shortcut, which acts on the focused window.
    assert 'mode="restore"' in reply and "win+down" not in reply


def _switch(desktop, name):
    with (
        patch(f"{SERVICE}.uia.IsIconic", return_value=False),
        patch.object(Desktop, "bring_window_to_top") as bring,
    ):
        return desktop.switch_app(name), bring


# c. replies keep the window's own title
def test_switch_echoes_real_title():
    (reply, status), _ = _switch(_desktop([_window("WMCP Harness", 1)]), "WMCP Harness")
    assert status == 0
    assert reply == "Switched to WMCP Harness window."


# d. a vague name that matches several windows says which others it matched
def test_switch_lists_other_matches():
    windows = [_window("WMCP Harness", 1), _window("Shell", 2), _window("Settings", 3)]
    (reply, status), bring = _switch(_desktop(windows), "h")
    assert status == 0
    # "Shell" is the best fuzzy match; "WMCP Harness" only contains "h" but must not be hidden.
    bring.assert_called_once_with(2)
    assert reply.startswith("Switched to Shell window.")
    assert 'Also matched "WMCP Harness"' in reply
    assert "Settings" not in reply


def test_switch_single_match_has_no_note():
    windows = [_window("WMCP Harness", 1), _window("Settings", 2)]
    (reply, _), _ = _switch(_desktop(windows), "WMCP Harness")
    assert "Also matched" not in reply


# e. an empty name switches to nothing
@pytest.mark.parametrize("name", ["", "   ", None])
def test_switch_refuses_empty_name(name):
    (reply, status), bring = _switch(_desktop([_window("WMCP Harness", 1)]), name)
    assert status == 1
    assert "name" in reply
    bring.assert_not_called()


def test_resize_refuses_empty_name(control):
    reply, status = _desktop([_window("WMCP Harness", 1)]).resize_app("", size=[800, 600])
    assert status == 1
    control.MoveWindow.assert_not_called()


# f. an empty launch name is refused before the Start Menu is read
@pytest.mark.parametrize("name", ["", "  ", None])
def test_launch_refuses_empty_name(name):
    desktop = Desktop.__new__(Desktop)
    desktop.get_apps_from_start_menu = lambda: pytest.fail("start menu read")
    reply, status, _ = desktop.launch_app(name)
    assert status == 1
    assert reply.startswith("Provide")


def test_launch_not_found_echoes_typed_text():
    desktop = Desktop.__new__(Desktop)
    desktop.get_apps_from_start_menu = lambda: {"calculator": "Microsoft.Calc"}
    reply, status, _ = desktop.launch_app("zzqx wmcp")
    assert status == 1
    assert '"zzqx wmcp"' in reply


# h. a bare executable name is looked up on PATH
def test_bare_executable_name_is_found_on_path(tmp_path):
    exe = tmp_path / "tool.exe"
    exe.write_bytes(b"")
    with patch("windows_mcp.tools.app.shutil.which", return_value=str(exe)) as which:
        assert _resolve_executable("tool.exe") == exe.resolve()
    which.assert_called_once_with("tool.exe")


def test_bare_executable_name_missing_from_path():
    with patch("windows_mcp.tools.app.shutil.which", return_value=None):
        with pytest.raises(ValueError, match="not found on PATH"):
            _resolve_executable("no-such-wmcp.exe")


@pytest.mark.parametrize("name", ["tool.exe", "tool"])
def test_bare_name_off_path_is_found_in_app_paths(tmp_path, monkeypatch, name):
    # Round-3 R3-I5: msedge.exe is registered under App Paths, not on PATH.
    exe = tmp_path / "tool.exe"
    exe.write_bytes(b"")
    monkeypatch.setenv("WMCP_TEST_DIR", str(tmp_path))
    asked = []

    def query(hive, subkey):
        asked.append(subkey)
        if hive == winreg.HKEY_LOCAL_MACHINE and subkey.endswith("\\tool.exe"):
            return '"%WMCP_TEST_DIR%\\tool.exe"'  # quoted, with a variable, as installers write
        raise FileNotFoundError

    with (
        patch("windows_mcp.tools.app.shutil.which", return_value=None),
        patch("windows_mcp.tools.app.winreg.QueryValue", side_effect=query),
    ):
        assert _resolve_executable(name) == exe.resolve()
    assert all(
        s.startswith("SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\") for s in asked
    )


def test_bare_name_missing_everywhere_names_both_places():
    with (
        patch("windows_mcp.tools.app.shutil.which", return_value=None),
        patch("windows_mcp.tools.app.winreg.QueryValue", side_effect=FileNotFoundError),
    ):
        with pytest.raises(ValueError, match="not found on PATH or in App Paths"):
            _resolve_executable("no-such-wmcp.exe")


def test_path_executable_skips_path_search(tmp_path):
    exe = tmp_path / "tool.exe"
    exe.write_bytes(b"")
    with patch("windows_mcp.tools.app.shutil.which") as which:
        assert _resolve_executable(str(exe)) == exe.resolve()
    which.assert_not_called()
