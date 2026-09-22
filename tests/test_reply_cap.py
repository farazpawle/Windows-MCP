"""Round-2 2.10: large replies are capped with a note; Process list refuses a limit below 1."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from windows_mcp import process
from windows_mcp.powershell import PowerShellExecutor
from windows_mcp.tools import filesystem, shell
from windows_mcp.tools import process as process_tools
from windows_mcp.tools._output import MAX_REPLY_CHARS, cap_text


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _tool(module, name):
    mcp = FakeMCP()
    module.register(mcp, get_desktop=MagicMock(), get_analytics=lambda: None)
    return lambda **kwargs: asyncio.run(mcp.tools[name](**kwargs))


def test_short_text_is_unchanged():
    text = "a" * MAX_REPLY_CHARS
    assert cap_text(text) == text


def test_long_text_is_cut_with_the_number_dropped():
    capped = cap_text("a" * (MAX_REPLY_CHARS + 1234))
    assert capped == "a" * MAX_REPLY_CHARS + "\n... [truncated - 1,234 more characters]"


def test_powershell_output_is_capped_and_keeps_the_status_code():
    with patch.object(PowerShellExecutor, "execute_command", return_value=("a" * 300_000, 0)):
        result = _tool(shell, "PowerShell")(command="'a' * 300000")
    assert "[truncated - 250,000 more characters]" in result
    assert result.endswith("Status Code: 0")
    assert len(result) < MAX_REPLY_CHARS + 200


def test_filesystem_read_is_capped(tmp_path):
    f = tmp_path / "long.txt"
    f.write_text("b" * (MAX_REPLY_CHARS * 2), encoding="utf-8")
    result = _tool(filesystem, "FileSystem")(mode="read", path=str(f))
    assert "more characters]" in result
    assert len(result) < MAX_REPLY_CHARS + 200


def test_process_list_is_capped():
    with patch.object(process, "list_processes", return_value="p" * (MAX_REPLY_CHARS + 10)):
        result = _tool(process_tools, "Process")(mode="list")
    assert result.endswith("[truncated - 10 more characters]")


@pytest.mark.parametrize("limit", [0, -5])
def test_process_list_refuses_limit_below_1(limit):
    with patch.object(process, "list_processes") as listing:
        with pytest.raises(ValueError, match="limit"):
            _tool(process_tools, "Process")(mode="list", limit=limit)
    listing.assert_not_called()
