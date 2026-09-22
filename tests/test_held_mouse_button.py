"""Round-2 2.4: Move mouse_button remembers the held button; other mouse actions release it."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

import windows_mcp.uia as uia
from windows_mcp.desktop.service import Desktop
from windows_mcp.tools import input as input_tools
from windows_mcp.tools import multi as multi_tools


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
    for module in (input_tools, multi_tools):
        module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    tool = mcp.tools[name]
    return lambda **kwargs: asyncio.run(tool(**kwargs))


@pytest.fixture
def mouse():
    with (
        patch.object(Desktop, "_require_on_screen"),
        patch.object(uia, "PressMouse") as press,
        patch.object(uia, "SetCursorPos"),
        patch.object(uia, "ReleaseMouse") as release,
    ):
        yield press, release


class TestServiceState:
    def test_up_without_down_sends_nothing(self, mouse):
        press, release = mouse
        assert Desktop.__new__(Desktop).mouse_button([5, 6], "up") is False
        release.assert_not_called()

    def test_second_down_is_refused(self, mouse):
        press, _ = mouse
        desktop = Desktop.__new__(Desktop)
        desktop.mouse_button([5, 6], "down")
        with pytest.raises(ValueError, match="already held"):
            desktop.mouse_button([5, 6], "down")
        press.assert_called_once()

    def test_down_then_up_then_up(self, mouse):
        _, release = mouse
        desktop = Desktop.__new__(Desktop)
        assert desktop.mouse_button([5, 6], "down") is True
        assert desktop.mouse_button([7, 8], "up") is True
        assert desktop.mouse_button([7, 8], "up") is False
        release.assert_called_once()

    def test_release_held_button(self, mouse):
        _, release = mouse
        desktop = Desktop.__new__(Desktop)
        assert desktop.release_held_button() is False
        desktop.mouse_button([5, 6], "down")
        assert desktop.release_held_button() is True
        assert desktop.release_held_button() is False
        release.assert_called_once()


class TestToolReplies:
    def test_up_with_nothing_held_says_so(self):
        desktop = MagicMock()
        desktop.mouse_button.return_value = False
        reply = _tool("Move", desktop)(loc=[5, 6], mouse_button="up")
        assert "no mouse button was held" in reply.lower()

    @pytest.mark.parametrize(
        ("name", "kwargs"),
        [
            ("Click", {"loc": [5, 6]}),
            ("Type", {"loc": [5, 6], "text": "x"}),
            ("Scroll", {"loc": [5, 6]}),
            ("Move", {"loc": [5, 6], "drag": True}),
            ("MultiSelect", {"locs": [[5, 6]]}),
            ("MultiEdit", {"locs": [[5, 6, "x"]]}),
        ],
    )
    def test_mouse_actions_release_a_held_button_and_say_so(self, name, kwargs):
        desktop = MagicMock()
        desktop.scroll.return_value = None
        desktop.drag.return_value = {"start": [1, 2], "end": [5, 6], "duration": None}
        desktop.release_held_button.return_value = True
        reply = _tool(name, desktop)(**kwargs)
        desktop.release_held_button.assert_called_once()
        assert "released the held left mouse button first" in reply.lower()

    def test_hover_click_keeps_the_button_held(self):
        # clicks=0 only moves the pointer: that is how a held drag is steered.
        desktop = MagicMock()
        _tool("Click", desktop)(loc=[5, 6], clicks=0)
        desktop.release_held_button.assert_not_called()

    def test_type_without_location_keeps_the_button_held(self):
        desktop = MagicMock()
        _tool("Type", desktop)(text="x")
        desktop.release_held_button.assert_not_called()
