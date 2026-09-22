"""Regression tests for Plan/windows-mcp-open-issues.md section 6 (missing abilities)."""

import asyncio
from unittest.mock import MagicMock, call, patch

import pytest

from windows_mcp.desktop.service import Desktop
from windows_mcp.tools import input as input_tool_module
import windows_mcp.uia as uia


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _tool(name, desktop):
    mcp = FakeMCP()
    input_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    tool = mcp.tools[name]
    return lambda **kwargs: asyncio.run(tool(**kwargs))


def _desktop() -> Desktop:
    return Desktop.__new__(Desktop)


# 6.1 / 6.4 modifiers on Click, Scroll and Move drag
class TestModifiersArgument:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("shift", ["shift"]),
            ("Ctrl+Shift", ["ctrl", "shift"]),
            (["control", "alt"], ["ctrl", "alt"]),
            ('["win"]', ["win"]),
            (None, []),
        ],
    )
    def test_click_passes_normalized_modifiers(self, value, expected):
        desktop = MagicMock()
        reply = _tool("Click", desktop)(loc=[5, 6], modifiers=value)
        desktop.click.assert_called_once_with(
            loc=[5, 6], button="left", clicks=1, modifiers=expected
        )
        if expected:
            assert "+".join(expected) in reply

    @pytest.mark.parametrize("value", ["capslock", "ctrl+a", ["shift", 3]])
    def test_unknown_modifier_is_rejected(self, value):
        desktop = MagicMock()
        with pytest.raises(ValueError, match="modifiers"):
            _tool("Click", desktop)(loc=[5, 6], modifiers=value)
        desktop.click.assert_not_called()

    def test_scroll_passes_modifiers(self):
        desktop = MagicMock()
        desktop.scroll.return_value = None
        reply = _tool("Scroll", desktop)(loc=[5, 6], direction="up", modifiers="ctrl")
        desktop.scroll.assert_called_once_with([5, 6], "vertical", "up", 1, modifiers=["ctrl"])
        assert "ctrl" in reply

    def test_drag_passes_modifiers(self):
        desktop = MagicMock()
        desktop.drag.return_value = {"start": [1, 2], "end": [5, 6], "duration": None}
        _tool("Move", desktop)(loc=[5, 6], drag=True, modifiers="alt")
        assert desktop.drag.call_args.kwargs["modifiers"] == ["alt"]

    def test_modifiers_on_plain_move_are_rejected(self):
        with pytest.raises(ValueError, match="modifiers"):
            _tool("Move", MagicMock())(loc=[5, 6], modifiers="ctrl")


class TestHeldModifiersInService:
    def test_click_holds_and_releases_modifiers_around_the_click(self):
        events = []
        with (
            patch.object(uia, "PressKey", side_effect=lambda k, **_: events.append(("down", k))),
            patch.object(uia, "ReleaseKey", side_effect=lambda k, **_: events.append(("up", k))),
            patch.object(uia, "Click", side_effect=lambda *a, **_: events.append(("click",))),
        ):
            _desktop().click([5, 6], modifiers=["ctrl", "shift"])
        ctrl, shift = uia.Keys.VK_CONTROL, uia.Keys.VK_SHIFT
        assert events == [("down", ctrl), ("down", shift), ("click",), ("up", shift), ("up", ctrl)]

    @pytest.mark.parametrize("action", ["click", "scroll"])
    def test_alt_holds_only_alt_and_masks_the_menu_before_release(self, action):
        # Round-2 2.1: Alt must not bring Ctrl along, and a tap of the unassigned
        # key 0xE8 before Alt-up keeps the window's menu bar from opening.
        events = []
        with (
            patch.object(uia, "PressKey", side_effect=lambda k, **_: events.append(("down", k))),
            patch.object(uia, "ReleaseKey", side_effect=lambda k, **_: events.append(("up", k))),
            patch.object(uia, "Click"),
            patch.object(uia, "WheelUp"),
            patch.object(Desktop, "_require_on_screen"),
        ):
            if action == "click":
                _desktop().click([5, 6], modifiers=["alt"])
            else:
                _desktop().scroll(None, "vertical", "up", 1, modifiers=["alt"])
        alt = uia.Keys.VK_MENU
        assert events == [("down", alt), ("down", 0xE8), ("up", 0xE8), ("up", alt)]

    def test_win_is_masked_before_release_so_start_stays_closed(self):
        # Round-2 2.2: a bare Win-up opens the Start menu.
        events = []
        with (
            patch.object(uia, "PressKey", side_effect=lambda k, **_: events.append(("down", k))),
            patch.object(uia, "ReleaseKey", side_effect=lambda k, **_: events.append(("up", k))),
            patch.object(uia, "Click"),
            patch.object(Desktop, "_require_on_screen"),
        ):
            _desktop().click([5, 6], modifiers=["win"])
        win = uia.Keys.VK_LWIN
        assert events == [("down", win), ("down", 0xE8), ("up", 0xE8), ("up", win)]

    def test_modifiers_are_released_even_when_the_action_fails(self):
        released = []
        with (
            patch.object(uia, "PressKey"),
            patch.object(uia, "ReleaseKey", side_effect=lambda k, **_: released.append(k)),
            patch.object(uia, "WheelUp", side_effect=RuntimeError("boom")),
        ):
            with pytest.raises(RuntimeError):
                _desktop().scroll(None, "vertical", "up", 1, modifiers=["ctrl"])
        assert released == [uia.Keys.VK_CONTROL]


# 6.2 / 6.5 Shortcut hold and repeat
class TestShortcutHoldRepeat:
    def test_repeat_is_passed_and_named(self):
        desktop = MagicMock()
        reply = _tool("Shortcut", desktop)(shortcut="down", repeat=5)
        desktop.shortcut.assert_called_once_with("down", repeat=5, hold=None)
        assert "5 times" in reply

    def test_hold_is_passed_and_named(self):
        desktop = MagicMock()
        reply = _tool("Shortcut", desktop)(shortcut="shift", hold=1.5)
        desktop.shortcut.assert_called_once_with("shift", repeat=1, hold=1.5)
        assert "1.5" in reply

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"repeat": 0},
            {"repeat": 101},
            {"repeat": True},
            {"hold": 0},
            {"hold": 11},
            {"hold": float("nan")},
            {"hold": 1, "repeat": 2},
        ],
    )
    def test_bad_values_are_rejected(self, kwargs):
        desktop = MagicMock()
        with pytest.raises(ValueError):
            _tool("Shortcut", desktop)(shortcut="a", **kwargs)
        desktop.shortcut.assert_not_called()

    def test_service_repeats_the_combination(self):
        with patch.object(uia, "SendKeys") as send:
            _desktop().shortcut("ctrl+z", repeat=3)
        assert send.call_count == 3
        assert send.call_args_list[0].args[0] == "{ctrl}z"

    def test_service_hold_presses_waits_then_releases_in_reverse(self):
        events = []
        with (
            patch.object(uia, "PressKey", side_effect=lambda k, **_: events.append(("down", k))),
            patch.object(uia, "ReleaseKey", side_effect=lambda k, **_: events.append(("up", k))),
            patch("windows_mcp.desktop.service.sleep", side_effect=lambda s: events.append(s)),
        ):
            _desktop().shortcut("shift+a", hold=2.0)
        shift, a = uia.Keys.VK_SHIFT, ord("A")
        assert events == [("down", shift), ("down", a), 2.0, ("up", a), ("up", shift)]

    def test_service_hold_of_win_masks_before_release(self):
        events = []
        with (
            patch.object(uia, "PressKey", side_effect=lambda k, **_: events.append(("down", k))),
            patch.object(uia, "ReleaseKey", side_effect=lambda k, **_: events.append(("up", k))),
            patch("windows_mcp.desktop.service.sleep"),
        ):
            _desktop().shortcut("win", hold=0.1)
        win = uia.Keys.VK_LWIN
        assert events == [("down", win), ("down", 0xE8), ("up", 0xE8), ("up", win)]

    def test_service_hold_rejects_unknown_key_before_pressing(self):
        with patch.object(uia, "PressKey") as press:
            with pytest.raises(ValueError, match="nosuchkey"):
                _desktop().shortcut("ctrl+nosuchkey", hold=1)
        press.assert_not_called()


# 6.3 Move mouse_button down / up
class TestMouseButtonDownUp:
    def test_down_at_location(self):
        desktop = MagicMock()
        reply = _tool("Move", desktop)(loc=[5, 6], mouse_button="down")
        desktop.mouse_button.assert_called_once_with([5, 6], "down")
        assert "pressed" in reply.lower()

    def test_up_without_location_uses_cursor(self):
        desktop = MagicMock()
        desktop.get_cursor_location.return_value = (7, 8)
        reply = _tool("Move", desktop)(mouse_button="up")
        desktop.mouse_button.assert_called_once_with([7, 8], "up")
        assert "released" in reply.lower()

    def test_cannot_combine_with_drag(self):
        with pytest.raises(ValueError, match="mouse_button"):
            _tool("Move", MagicMock())(loc=[5, 6], drag=True, mouse_button="down")

    def test_invalid_value_rejected(self):
        with pytest.raises(ValueError, match="mouse_button"):
            _tool("Move", MagicMock())(loc=[5, 6], mouse_button="left")

    def test_service_down_and_up(self):
        with (
            patch.object(uia, "PressMouse") as press,
            patch.object(uia, "SetCursorPos") as move,
            patch.object(uia, "ReleaseMouse") as release,
        ):
            _desktop().mouse_button([5, 6], "down")
            _desktop().mouse_button([7, 8], "up")
        press.assert_called_once_with(5, 6, waitTime=0.05)
        move.assert_called_once_with(7, 8)
        release.assert_called_once_with(waitTime=0.05)


# 6.6 Click / Type without a location
class TestNoLocation:
    def test_click_without_location_uses_cursor(self):
        desktop = MagicMock()
        desktop.get_cursor_location.return_value = (7, 8)
        reply = _tool("Click", desktop)()
        desktop.click.assert_called_once_with(loc=[7, 8], button="left", clicks=1, modifiers=[])
        assert "(7,8)" in reply

    def test_type_without_location_types_into_focus(self):
        desktop = MagicMock()
        reply = _tool("Type", desktop)(text="hi")
        assert desktop.type.call_args.kwargs["loc"] is None
        assert "focused" in reply

    def test_service_type_without_location_does_not_click(self):
        with patch.object(uia, "Click") as click, patch.object(uia, "SendKeys") as send:
            _desktop().type(None, "hi")
        click.assert_not_called()
        assert send.call_args_list[-1] == call("hi", interval=0.04, waitTime=0.05)


# 6.7 Wait accepts decimals
class TestWaitDecimals:
    def test_half_second(self):
        with patch.object(input_tool_module.time, "sleep") as sleep:
            reply = _tool("Wait", MagicMock())(duration=0.5)
        sleep.assert_called_once_with(0.5)
        assert "0.5" in reply

    def test_numeric_string_is_accepted(self):
        with patch.object(input_tool_module.time, "sleep") as sleep:
            _tool("Wait", MagicMock())(duration="1.5")
        sleep.assert_called_once_with(1.5)

    @pytest.mark.parametrize("value", [-1, float("inf"), "soon", True])
    def test_bad_values_rejected(self, value):
        with patch.object(input_tool_module.time, "sleep") as sleep:
            with pytest.raises(ValueError, match="duration"):
                _tool("Wait", MagicMock())(duration=value)
        sleep.assert_not_called()
