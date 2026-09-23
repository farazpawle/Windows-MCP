"""Round-2 3.22: commands that ask for input fail clearly instead of hanging or lying."""

import subprocess
from unittest.mock import patch

import pytest

from windows_mcp.powershell import PowerShellExecutor

RUN_PATH = "windows_mcp.powershell.service.run_with_graceful_timeout"

# Real stderr from pwsh 7.x (2026-09-23) for a Remove-Item that wanted confirmation,
# run with -NonInteractive: a non-terminating error, so the exit code stays 0.
PROMPT_CLIXML = (
    "#< CLIXML\r\n"
    '<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04">'
    '<S S="Error">_x001B_[31;1mRemove-Item: _x001B_[31;1mPowerShell is in NonInteractive '
    "mode. Read and Prompt functionality is not available._x001B_[0m_x000D__x000A_</S>"
    "</Objs>"
)


def _run(exit_code: int, stdout: bytes = b"", stderr: str = PROMPT_CLIXML):
    completed = subprocess.CompletedProcess([], exit_code, stdout, stderr.encode())
    with patch(RUN_PATH, return_value=completed) as run:
        output, status = PowerShellExecutor.execute_command("x", include_errors=True)
    return output, status, run.call_args.args[0]


def test_powershell_runs_non_interactive():
    _, _, argv = _run(0, b"ok", "")
    assert "-NonInteractive" in argv


@pytest.mark.parametrize("exit_code", [0, 1])
def test_a_prompt_is_reported_with_a_failing_status(exit_code):
    output, status, _ = _run(exit_code, b"exists=True\r\n")
    assert status != 0
    assert "interactive input is not available" in output
    assert "exists=True" in output  # what the command printed is kept


def test_windows_powershell_wording_is_recognised_too():
    stderr = (
        "#< CLIXML\r\n"
        '<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04">'
        '<S S="Error">Read-Host : Windows PowerShell is in NonInteractive mode. Read and '
        "Prompt functionality is not available._x000D__x000A_</S></Objs>"
    )
    output, status, _ = _run(1, b"", stderr)
    assert status != 0
    assert "interactive input is not available" in output


def test_ordinary_success_is_untouched():
    output, status, _ = _run(0, b"hello\r\n", "")
    assert (output.strip(), status) == ("hello", 0)
