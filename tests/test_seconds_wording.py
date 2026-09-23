"""Duration replies say "1 second", not "1 seconds" (round-2 3.28)."""

import asyncio
from unittest.mock import MagicMock, patch

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


def _tool(name):
    mcp = FakeMCP()
    input_tool_module.register(mcp, get_desktop=MagicMock, get_analytics=lambda: None)
    tool = mcp.tools[name]
    return lambda **kwargs: asyncio.run(tool(**kwargs))


@pytest.mark.parametrize(
    ("hold", "expected"),
    [
        (1, "for 1 second."),
        (1.0, "for 1 second."),
        (0.5, "for 0.5 seconds."),
        (2, "for 2 seconds."),
    ],
)
def test_shortcut_hold_unit(hold, expected):
    assert _tool("Shortcut")(shortcut="shift+left", hold=hold) == f"Held shift+left {expected}"


@pytest.mark.parametrize(
    ("duration", "expected"),
    [(1, "Waited for 1 second."), (0, "Waited for 0 seconds."), (2.5, "Waited for 2.5 seconds.")],
)
def test_wait_unit(duration, expected):
    with patch.object(input_tool_module.time, "sleep"):
        assert _tool("Wait")(duration=duration) == expected
