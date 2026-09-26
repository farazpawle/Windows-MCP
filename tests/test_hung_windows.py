"""Hung (not-responding) windows must be skipped before any UIA call.

UIA calls such as ControlFromHandle block indefinitely on a window whose thread
has stopped pumping messages, which previously stalled Snapshot/App switch forever.
"""

from unittest.mock import patch

import pytest

from windows_mcp.desktop.service import Desktop

HUNG = 2


@pytest.fixture
def desktop():
    with patch.object(Desktop, "__init__", lambda self: None):
        return Desktop()


def _fake_enum(callback, _):
    for hwnd in (1, HUNG, 3):
        callback(hwnd, None)


def test_get_controls_handles_skips_hung_windows(desktop):
    with (
        patch("windows_mcp.desktop.service.win32gui.EnumWindows", side_effect=_fake_enum),
        patch("windows_mcp.desktop.service.win32gui.IsWindow", return_value=True),
        patch("windows_mcp.desktop.service.win32gui.IsWindowVisible", return_value=True),
        patch("windows_mcp.desktop.service.win32gui.FindWindow", return_value=0),
        patch("windows_mcp.desktop.service.is_window_on_current_desktop", return_value=True),
        patch("windows_mcp.desktop.service.is_window_hung", side_effect=lambda h: h == HUNG),
    ):
        assert desktop.get_controls_handles() == [1, 3]


def test_get_controls_handles_keeps_front_to_back_order(desktop):
    # Round-4 R4-I6: a set lost EnumWindows' z-order, so App list and Depth were random.
    def enum(callback, _):
        for hwnd in (30, 10, 20):
            callback(hwnd, None)

    with (
        patch("windows_mcp.desktop.service.win32gui.EnumWindows", side_effect=enum),
        patch("windows_mcp.desktop.service.win32gui.IsWindow", return_value=True),
        patch("windows_mcp.desktop.service.win32gui.IsWindowVisible", return_value=True),
        # Progman is already listed; the taskbars are not.
        patch("windows_mcp.desktop.service.win32gui.FindWindow", side_effect=[20, 40, 0]),
        patch("windows_mcp.desktop.service.is_window_on_current_desktop", return_value=True),
        patch("windows_mcp.desktop.service.is_window_hung", return_value=False),
    ):
        assert desktop.get_controls_handles() == [30, 10, 20, 40]


def test_get_foreground_window_returns_none_when_hung(desktop):
    with (
        patch("windows_mcp.desktop.service.uia.GetForegroundWindow", return_value=HUNG),
        patch("windows_mcp.desktop.service.is_window_hung", return_value=True),
        patch.object(Desktop, "get_window_from_element_handle") as resolve,
    ):
        assert desktop.get_foreground_window() is None
        resolve.assert_not_called()
