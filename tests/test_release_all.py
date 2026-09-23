"""Round-2 C.2: Shortcut release_all lets go of every held modifier key and mouse button."""

import asyncio
from unittest.mock import MagicMock, call, patch

import pytest

import windows_mcp.uia as uia
from windows_mcp.desktop.service import Desktop
from windows_mcp.tools import input as input_tool_module


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _shortcut(desktop):
    mcp = FakeMCP()
    input_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    tool = mcp.tools["Shortcut"]
    return lambda **kwargs: asyncio.run(tool(**kwargs))


class TestTool:
    def test_reply_names_what_was_released(self):
        desktop = MagicMock()
        desktop.release_all.return_value = ["left Shift", "left mouse button"]
        reply = _shortcut(desktop)(release_all=True)
        assert reply == "Released: left Shift, left mouse button."
        desktop.shortcut.assert_not_called()

    def test_reply_when_nothing_was_held(self):
        desktop = MagicMock()
        desktop.release_all.return_value = []
        assert _shortcut(desktop)(release_all="true") == "Nothing was held; nothing was sent."

    @pytest.mark.parametrize("extra", [{"shortcut": "ctrl+c"}, {"hold": 1}, {"repeat": 3}])
    def test_cannot_be_combined(self, extra):
        with pytest.raises(ValueError, match="release_all"):
            _shortcut(MagicMock())(release_all=True, **extra)

    def test_shortcut_still_required_without_release_all(self):
        with pytest.raises(ValueError, match="shortcut"):
            _shortcut(MagicMock())()


def _held(*codes):
    return lambda code: code in codes


class TestService:
    def _release_all(self, held, left_held=False):
        desktop = Desktop.__new__(Desktop)
        desktop._left_held = left_held
        with (
            patch.object(uia, "IsKeyPressed", side_effect=_held(*held)),
            patch.object(uia, "PressKey") as press,
            patch.object(uia, "ReleaseKey") as release_key,
            patch.object(uia, "ReleaseMouse") as left,
            patch.object(uia, "RightReleaseMouse") as right,
            patch.object(uia, "MiddleReleaseMouse") as middle,
        ):
            names = desktop.release_all()
        return desktop, names, press, release_key, left, right, middle

    def test_releases_only_what_is_down(self):
        _, names, _, release_key, left, right, middle = self._release_all(
            [uia.Keys.VK_LSHIFT, uia.Keys.VK_LBUTTON]
        )
        assert names == ["left Shift", "left mouse button"]
        release_key.assert_called_once_with(uia.Keys.VK_LSHIFT, waitTime=0.05)
        left.assert_called_once()
        right.assert_not_called()
        middle.assert_not_called()

    def test_nothing_down_sends_nothing(self):
        _, names, press, release_key, left, right, middle = self._release_all([])
        assert names == []
        for sent in (press, release_key, left, right, middle):
            sent.assert_not_called()

    def test_win_release_is_masked(self):
        _, names, press, release_key, *_ = self._release_all([uia.Keys.VK_LWIN])
        assert names == ["left Win"]
        # The mask key goes down and up before Win is let go, so Start does not open.
        assert press.call_args_list == [call(0xE8, waitTime=0)]
        assert release_key.call_args_list == [
            call(0xE8, waitTime=0),
            call(uia.Keys.VK_LWIN, waitTime=0.05),
        ]

    def test_button_this_server_holds_is_released_and_forgotten(self):
        desktop, names, *_, left, _, _ = self._release_all([], left_held=True)
        assert names == ["left mouse button"]
        left.assert_called_once()
        assert desktop._left_held is False

    def test_keys_are_released_before_buttons(self):
        order = MagicMock()
        desktop = Desktop.__new__(Desktop)
        with (
            patch.object(
                uia, "IsKeyPressed", side_effect=_held(uia.Keys.VK_LCONTROL, uia.Keys.VK_LBUTTON)
            ),
            patch.object(uia, "ReleaseKey", order.key),
            patch.object(uia, "ReleaseMouse", order.button),
        ):
            desktop.release_all()
        # A drop with Ctrl still down would copy instead of move.
        assert [c[0] for c in order.mock_calls] == ["key", "button"]
