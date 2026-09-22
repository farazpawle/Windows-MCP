"""Round-2 2.13: a failed operation reaches the client as a tool error (is_error=True).

The services report expected failures as "Error: ..." text; returned as-is, FastMCP
sent them as successful results, so the model could mistake a failure for success.
"""

import asyncio
from unittest.mock import patch

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from windows_mcp.tools import filesystem, process, registry

EXECUTE = "windows_mcp.powershell.PowerShellExecutor.execute_command"


def _call(module, tool, **args):
    mcp = FastMCP("test")
    module.register(mcp, get_desktop=lambda: None, get_analytics=lambda: None)
    return asyncio.run(mcp.call_tool(tool, args))


def test_filesystem_failure_is_a_tool_error(tmp_path):
    with pytest.raises(ToolError, match="File not found"):
        _call(filesystem, "FileSystem", mode="read", path=str(tmp_path / "missing.txt"))


def test_filesystem_success_is_not_an_error(tmp_path):
    f = tmp_path / "ok.txt"
    f.write_text("hello", encoding="utf-8")
    result = _call(filesystem, "FileSystem", mode="read", path=str(f))
    assert "hello" in result.content[0].text


def test_registry_failure_is_a_tool_error():
    with patch(EXECUTE, return_value=("Property Nope does not exist", 1)):
        with pytest.raises(ToolError, match="Error reading registry"):
            _call(registry, "Registry", mode="get", path=r"HKCU:\Software", name="Nope")


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ({"pid": 999_999_999}, "No process with PID"),
        ({"name": "no-such-process-wmcp"}, "No process matching"),
    ],
)
def test_process_kill_failure_is_a_tool_error(args, message):
    with pytest.raises(ToolError, match=message):
        _call(process, "Process", mode="kill", **args)
