"""Horizontal scroll must move content sideways in native apps, not vertically.

Shift+wheel (the old approach) is only a browser/Explorer convention: a WinForms
panel scrolled down instead of right in live testing on 2026-09-22.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import windows_mcp.uia as uia
from windows_mcp.desktop.service import Desktop


@pytest.fixture
def desktop():
    with patch.object(Desktop, "__init__", lambda self: None):
        return Desktop()


def _control(pattern=None, parent=None):
    return SimpleNamespace(GetPattern=lambda pid: pattern, GetParentControl=lambda: parent)


def test_uses_scroll_pattern_of_nearest_horizontal_ancestor(desktop):
    pattern = MagicMock(HorizontallyScrollable=True)
    leaf = _control(parent=_control(pattern=pattern))
    with (
        patch.object(uia, "ControlFromCursor", return_value=leaf),
        patch.object(uia, "mouse_event") as mouse_event,
        patch.object(uia, "PressKey") as press_key,
    ):
        desktop.scroll(type="horizontal", direction="right", wheel_times=2)
    assert pattern.Scroll.call_count == 6  # 3 small increments per wheel notch
    pattern.Scroll.assert_called_with(uia.ScrollAmount.SmallIncrement, uia.ScrollAmount.NoAmount)
    mouse_event.assert_not_called()
    press_key.assert_not_called()


def test_left_scrolls_by_small_decrement(desktop):
    pattern = MagicMock(HorizontallyScrollable=True)
    with patch.object(uia, "ControlFromCursor", return_value=_control(pattern=pattern)):
        desktop.scroll(type="horizontal", direction="left", wheel_times=1)
    pattern.Scroll.assert_called_with(uia.ScrollAmount.SmallDecrement, uia.ScrollAmount.NoAmount)


def test_falls_back_to_horizontal_wheel_without_pattern(desktop):
    vertical_only = MagicMock(HorizontallyScrollable=False)
    with (
        patch.object(uia, "ControlFromCursor", return_value=_control(pattern=vertical_only)),
        patch.object(uia, "mouse_event") as mouse_event,
        patch("windows_mcp.desktop.service.sleep"),
    ):
        desktop.scroll(type="horizontal", direction="left", wheel_times=2)
    assert mouse_event.call_count == 2
    mouse_event.assert_called_with(uia.MouseEventFlag.HWheel, 0, 0, -120, 0)
    vertical_only.Scroll.assert_not_called()


def test_falls_back_when_uia_lookup_fails(desktop):
    with (
        patch.object(uia, "ControlFromCursor", side_effect=TimeoutError),
        patch.object(uia, "mouse_event") as mouse_event,
        patch("windows_mcp.desktop.service.sleep"),
    ):
        desktop.scroll(type="horizontal", direction="right", wheel_times=1)
    mouse_event.assert_called_once_with(uia.MouseEventFlag.HWheel, 0, 0, 120, 0)
