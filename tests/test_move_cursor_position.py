"""Round-2 C.1: Move with no target reports the cursor position instead of refusing."""

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


def _move(desktop):
    mcp = FakeMCP()
    input_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    tool = mcp.tools["Move"]
    return lambda **kwargs: asyncio.run(tool(**kwargs))


def test_move_without_target_reports_cursor_position():
    desktop = MagicMock()
    desktop.get_cursor_location.return_value = (812, 430)
    reply = _move(desktop)()
    assert reply == "The cursor is at (812,430)."
    desktop.move.assert_not_called()
    desktop.drag.assert_not_called()


def test_drag_without_target_is_still_refused():
    with pytest.raises(ValueError, match="loc or label"):
        _move(MagicMock())(drag=True)


def test_from_loc_without_target_is_still_refused():
    with pytest.raises(ValueError, match="loc or label"):
        _move(MagicMock())(from_loc=[1, 2])
