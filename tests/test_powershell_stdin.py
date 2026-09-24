"""Round-3 R3-I4: the script goes through stdin, not a base64 -EncodedCommand.

An encoded command line is what malware uses, so antivirus heuristics flag it.
"""

import subprocess
from unittest.mock import patch

import pytest

from windows_mcp.powershell import PowerShellExecutor

RUN_PATH = "windows_mcp.powershell.service.run_with_graceful_timeout"


def test_command_line_is_plain_and_script_goes_through_stdin():
    completed = subprocess.CompletedProcess([], 0, b"", b"")
    with patch(RUN_PATH, return_value=completed) as run:
        PowerShellExecutor.execute_command("'héllo'", shell="pwsh")
    args, kwargs = run.call_args.args[0], run.call_args.kwargs
    assert "-EncodedCommand" not in args and "-Command" in args
    assert "héllo" not in " ".join(args)
    assert "'héllo'" in kwargs["input"].decode("utf-8")
    assert "stdin" not in kwargs  # input= gives the child its own pipe


@pytest.mark.parametrize("shell", ["pwsh", "powershell"])
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("'héllo 🌍 مرحبا'", ("héllo 🌍 مرحبا", 0)),
        ("Get-Item C:\\nope-r3i4", ("", 1)),  # last command failed: status 1, as before
        ("cmd /c exit 3", ("", 1)),
        ("exit 7", ("", 7)),
        ("if ($true) {\n  'multi'\n}", ("multi", 0)),
    ],
)
def test_real_shell_output_and_status_match_the_encoded_way(shell, command, expected):
    output, status = PowerShellExecutor.execute_command(command, shell=shell)
    if expected[0]:
        assert output.strip() == expected[0]
    assert status == expected[1]


def test_syntax_error_is_reported_plainly():
    output, status = PowerShellExecutor.execute_command("'unclosed", shell="pwsh")
    assert status == 1
    assert "terminator" in output and "Exception calling" not in output
