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
        desktop.scroll(axis="horizontal", direction="right", wheel_times=2)
    assert pattern.Scroll.call_count == 6  # 3 small increments per wheel notch
    pattern.Scroll.assert_called_with(uia.ScrollAmount.SmallIncrement, uia.ScrollAmount.NoAmount)
    mouse_event.assert_not_called()
    press_key.assert_not_called()


def test_left_scrolls_by_small_decrement(desktop):
    pattern = MagicMock(HorizontallyScrollable=True)
    with patch.object(uia, "ControlFromCursor", return_value=_control(pattern=pattern)):
        desktop.scroll(axis="horizontal", direction="left", wheel_times=1)
    pattern.Scroll.assert_called_with(uia.ScrollAmount.SmallDecrement, uia.ScrollAmount.NoAmount)


def test_falls_back_to_horizontal_wheel_without_pattern(desktop):
    vertical_only = MagicMock(HorizontallyScrollable=False)
    with (
        patch.object(uia, "ControlFromCursor", return_value=_control(pattern=vertical_only)),
        patch.object(uia, "mouse_event") as mouse_event,
        patch("windows_mcp.desktop.service.sleep"),
    ):
        desktop.scroll(axis="horizontal", direction="left", wheel_times=2)
    assert mouse_event.call_count == 2
    mouse_event.assert_called_with(uia.MouseEventFlag.HWheel, 0, 0, -120, 0)
    vertical_only.Scroll.assert_not_called()


def test_falls_back_when_uia_lookup_fails(desktop):
    with (
        patch.object(uia, "ControlFromCursor", side_effect=TimeoutError),
        patch.object(uia, "mouse_event") as mouse_event,
        patch("windows_mcp.desktop.service.sleep"),
    ):
        desktop.scroll(axis="horizontal", direction="right", wheel_times=1)
    mouse_event.assert_called_once_with(uia.MouseEventFlag.HWheel, 0, 0, 120, 0)


def test_modifiers_send_a_real_wheel_instead_of_scroll_pattern(desktop):
    # Round-2 3.26: ScrollPattern ignores held keys, so "holding alt" was untrue.
    pattern = MagicMock(HorizontallyScrollable=True)
    events = []
    with (
        patch.object(uia, "ControlFromCursor", return_value=_control(pattern=pattern)),
        patch.object(uia, "mouse_event", side_effect=lambda *a: events.append(("wheel", a))),
        patch("windows_mcp.desktop.service._keys_held") as held,
        patch("windows_mcp.desktop.service.sleep"),
    ):
        held.return_value.__enter__.side_effect = lambda: events.append("down")
        held.return_value.__exit__.side_effect = lambda *a: events.append("up")
        desktop.scroll(axis="horizontal", direction="right", wheel_times=2, modifiers=["alt"])
    pattern.Scroll.assert_not_called()
    held.assert_called_once_with(["alt"])
    assert events == [
        "down",
        ("wheel", (uia.MouseEventFlag.HWheel, 0, 0, 120, 0)),
        ("wheel", (uia.MouseEventFlag.HWheel, 0, 0, 120, 0)),
        "up",
    ]


@pytest.mark.parametrize("guard", ["is_unreadable_window", "is_window_hung"])
def test_vs_code_or_hung_window_is_not_read(desktop, guard):
    """Round-2 3.34: a UIA read of VS Code freezes it, so the real wheel is used unread."""
    desktop.get_cursor_location = MagicMock(return_value=(50, 60))
    with (
        patch("windows_mcp.desktop.service.top_level_window_at", return_value=7),
        patch(f"windows_mcp.desktop.service.{guard}", return_value=True),
        patch.object(uia, "ControlFromCursor") as read,
        patch.object(uia, "mouse_event") as mouse_event,
        patch("windows_mcp.desktop.service.sleep"),
    ):
        desktop.scroll(axis="horizontal", direction="right", wheel_times=1)
    read.assert_not_called()
    mouse_event.assert_called_once_with(uia.MouseEventFlag.HWheel, 0, 0, 120, 0)
