"""Round-2 3.11: PowerShell output details."""

import asyncio
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from windows_mcp.powershell import PowerShellExecutor
from windows_mcp.powershell.service import decode_clixml
from windows_mcp.tools import shell as shell_tool_module

RUN_PATH = "windows_mcp.powershell.service.run_with_graceful_timeout"

# Real stderr from pwsh 7.x on 2026-09-23 for:
# Write-Warning 'warn-stream'; Write-Error 'boom'; Write-Verbose -Verbose 'verb-x';
# Write-Debug -Debug 'dbg-x'   (information records trimmed)
CLIXML_STREAMS = (
    "#< CLIXML\r\n"
    '<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04">'
    '<S S="warning">warn-stream</S>'
    '<S S="Error">_x001B_[31;1mWrite-Error: _x001B_[31;1mboom_x001B_[0m_x000D__x000A_</S>'
    '<S S="verbose">verb-x</S>'
    '<S S="debug">dbg-x</S>'
    "</Objs>"
)


def _tool():
    tools = {}

    class FakeMCP:
        def tool(self, *, name, **kwargs):
            return lambda func: tools.setdefault(name, func)

    shell_tool_module.register(FakeMCP(), get_desktop=MagicMock(), get_analytics=lambda: None)
    return lambda **kwargs: asyncio.run(tools["PowerShell"](**kwargs))


# b, c. every stream on its own line, verbose and debug kept
def test_streams_are_separate_lines_and_verbose_is_kept():
    assert decode_clixml(CLIXML_STREAMS) == (
        "WARNING: warn-stream\nWrite-Error: boom\nVERBOSE: verb-x\nDEBUG: dbg-x"
    )


def test_multi_line_error_is_not_split_further():
    clixml = (
        "#< CLIXML\r\n"
        '<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04">'
        '<S S="Error">line one_x000D__x000A_</S><S S="Error">line two_x000D__x000A_</S>'
        "</Objs>"
    )
    assert decode_clixml(clixml) == "line one\nline two"


def test_other_streams_after_output_are_headed_errors_and_messages():
    # A verbose/debug note is not an error; the old "Errors:" heading said it was.
    completed = subprocess.CompletedProcess([], 0, b"done\r\n", CLIXML_STREAMS.encode())
    with patch(RUN_PATH, return_value=completed):
        output, _ = PowerShellExecutor.execute_command("x", include_errors=True)
    assert output == (
        "done\n\nErrors and messages:\n"
        "WARNING: warn-stream\nWrite-Error: boom\nVERBOSE: verb-x\nDEBUG: dbg-x"
    )


# a. partial output survives a timeout
def _timeout(stdout, stderr):
    def run(*args, **kwargs):
        raise subprocess.TimeoutExpired("pwsh", 2, output=stdout, stderr=stderr)

    return run


def test_timeout_keeps_output_printed_before_it():
    with patch(RUN_PATH, side_effect=_timeout(b"start\r\n", b"")):
        output, status = PowerShellExecutor.execute_command("'start'; Start-Sleep 10", timeout=2)
    assert status == PowerShellExecutor.NOT_RUN
    assert output.startswith("start")
    assert output.rstrip().endswith("Command execution timed out after 2 s")


def test_timeout_keeps_errors_printed_before_it():
    with patch(RUN_PATH, side_effect=_timeout(None, CLIXML_STREAMS.encode())):
        output, _ = PowerShellExecutor.execute_command("x", timeout=2)
    assert "WARNING: warn-stream" in output
    assert "timed out" in output


def test_timeout_without_output_is_just_the_note():
    with patch(RUN_PATH, side_effect=_timeout(None, None)):
        output, status = PowerShellExecutor.execute_command("x", timeout=3)
    assert (output, status) == ("Command execution timed out after 3 s", PowerShellExecutor.NOT_RUN)


# d. empty command refused before PowerShell starts
@pytest.mark.parametrize("command", ["", "   ", "\n\t"])
def test_empty_command_is_refused(command):
    with patch.object(PowerShellExecutor, "execute_command") as execute:
        with pytest.raises(ValueError, match="command is empty"):
            _tool()(command=command)
    execute.assert_not_called()
