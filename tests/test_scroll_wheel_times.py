"""Round-2 3.2: Scroll requires wheel_times of 1 or more."""

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


def _scroll(desktop):
    mcp = FakeMCP()
    input_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return lambda **kwargs: asyncio.run(mcp.tools["Scroll"](**kwargs))


@pytest.mark.parametrize("wheel_times", [0, -1, -3])
def test_zero_or_negative_is_refused_without_scrolling(wheel_times):
    desktop = MagicMock()
    with pytest.raises(ValueError, match="wheel_times"):
        _scroll(desktop)(loc=[5, 6], wheel_times=wheel_times)
    desktop.scroll.assert_not_called()


@pytest.mark.parametrize("wheel_times", [1.5, "3", None, True])
def test_non_integers_are_refused_without_scrolling(wheel_times):
    desktop = MagicMock()
    with pytest.raises(ValueError, match="wheel_times"):
        _scroll(desktop)(loc=[5, 6], wheel_times=wheel_times)
    desktop.scroll.assert_not_called()


@pytest.mark.parametrize("wheel_times", [1, 3, 20])
def test_positive_counts_still_scroll(wheel_times):
    desktop = MagicMock()
    desktop.scroll.return_value = ""
    reply = _scroll(desktop)(loc=[5, 6], wheel_times=wheel_times)
    desktop.scroll.assert_called_once_with([5, 6], "vertical", "down", wheel_times, modifiers=[])
    assert f"by {wheel_times} wheel times" in reply
