"""Round-2 3.29: Scroll's direction argument is `axis`; the old name `type` still works."""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastmcp import Client, FastMCP

from windows_mcp.tools import input as input_tool_module


def _server():
    desktop = MagicMock()
    desktop.scroll.return_value = None
    desktop.release_held_button.return_value = False
    mcp = FastMCP("t")
    input_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return mcp, desktop


def _call(args):
    mcp, desktop = _server()

    async def run():
        async with Client(mcp) as client:
            return await client.call_tool("Scroll", args)

    return asyncio.run(run()).content[0].text, desktop


def test_schema_names_axis_not_type():
    mcp, _ = _server()
    props = asyncio.run(mcp.get_tool("Scroll")).parameters["properties"]
    assert "axis" in props
    assert "type" not in props


@pytest.mark.parametrize("name", ["axis", "type"])
def test_both_names_scroll_horizontally(name):
    reply, desktop = _call({name: "horizontal", "direction": "right", "loc": [5, 6]})
    assert desktop.scroll.call_args.args[1] == "horizontal"
    assert reply.startswith("Scrolled horizontal right by 1 wheel times at (5,6)")


def test_default_is_vertical():
    _, desktop = _call({"direction": "up"})
    assert desktop.scroll.call_args.args[1] == "vertical"


def test_bad_axis_is_refused():
    with pytest.raises(Exception, match="horizontal"):
        _call({"type": "diagonal"})


# 3.33: a direction that doesn't fit the axis is a tool error, and nothing is sent.
@pytest.mark.parametrize(
    ("axis", "direction"),
    [("horizontal", "up"), ("horizontal", "down"), ("vertical", "left"), ("vertical", "right")],
)
def test_direction_must_fit_axis(axis, direction):
    mcp, desktop = _server()

    async def run():
        async with Client(mcp) as client:
            return await client.call_tool(
                "Scroll", {"axis": axis, "direction": direction}, raise_on_error=False
            )

    result = asyncio.run(run())
    assert result.is_error
    assert "direction" in result.content[0].text
    desktop.scroll.assert_not_called()
    desktop.release_held_button.assert_not_called()
