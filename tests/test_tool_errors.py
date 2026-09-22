"""Round-2 2.13: a failed operation reaches the client as a tool error (is_error=True).

The services report expected failures as "Error: ..." text; returned as-is, FastMCP
sent them as successful results, so the model could mistake a failure for success.
"""

import asyncio

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from windows_mcp.tools import filesystem


def _call(module, name, **args):
    mcp = FastMCP("test")
    module.register(mcp, get_desktop=lambda: None, get_analytics=lambda: None)
    return asyncio.run(mcp.call_tool(name, args))


def test_filesystem_failure_is_a_tool_error(tmp_path):
    with pytest.raises(ToolError, match="File not found"):
        _call(filesystem, "FileSystem", mode="read", path=str(tmp_path / "missing.txt"))


def test_filesystem_success_is_not_an_error(tmp_path):
    f = tmp_path / "ok.txt"
    f.write_text("hello", encoding="utf-8")
    result = _call(filesystem, "FileSystem", mode="read", path=str(f))
    assert "hello" in result.content[0].text
