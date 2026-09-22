"""Round-2 3.1: hover (clicks=0) refuses modifiers and is worded as a move."""

import asyncio
from unittest.mock import MagicMock

import pytest

from windows_mcp.tools import input as input_tool_module


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _click(desktop):
    mcp = FakeMCP()
    input_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return lambda **kwargs: asyncio.run(mcp.tools["Click"](**kwargs))


class TestHoverRefusesModifiers:
    @pytest.mark.parametrize("modifiers", ["win", "ctrl+shift", ["alt"]])
    def test_modifiers_with_hover_are_refused_without_moving(self, modifiers):
        desktop = MagicMock()
        with pytest.raises(ValueError, match="modifiers"):
            _click(desktop)(loc=[5, 6], clicks=0, modifiers=modifiers)
        desktop.click.assert_not_called()

    def test_hover_without_modifiers_still_works(self):
        desktop = MagicMock()
        _click(desktop)(loc=[5, 6], clicks=0)
        desktop.click.assert_called_once_with(loc=[5, 6], button="left", clicks=0, modifiers=[])

    def test_modifiers_still_allowed_when_clicking(self):
        desktop = MagicMock()
        reply = _click(desktop)(loc=[5, 6], clicks=1, modifiers="shift")
        assert "holding shift" in reply


class TestHoverWording:
    def test_hover_reply_reads_as_a_move(self):
        desktop = MagicMock()
        reply = _click(desktop)(loc=[5, 6], clicks=0)
        assert reply.startswith("Moved to (5,6) (hover)")
        assert "clicked" not in reply

    @pytest.mark.parametrize("clicks", [1, 2, 3])
    def test_real_clicks_keep_their_wording(self, clicks):
        desktop = MagicMock()
        reply = _click(desktop)(loc=[5, 6], clicks=clicks)
        assert "clicked at (5,6)" in reply
