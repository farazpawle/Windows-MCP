"""Round-2 2.13: a failed operation reaches the client as a tool error (is_error=True).

The services report expected failures as "Error: ..." text; returned as-is, FastMCP
sent them as successful results, so the model could mistake a failure for success.
"""

import asyncio
from unittest.mock import patch

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from windows_mcp.desktop.service import Desktop
from windows_mcp.powershell import PowerShellExecutor
from windows_mcp.tools import (
    app,
    clipboard,
    filesystem,
    notification,
    process,
    registry,
    shell,
    snapshot,
)

EXECUTE = "windows_mcp.powershell.PowerShellExecutor.execute_command"


def _call(module, tool, desktop=None, **args):
    mcp = FastMCP("test")
    module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
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


def test_app_switch_to_unknown_window_is_a_tool_error():
    desktop = Desktop.__new__(Desktop)
    desktop.get_windows = lambda: ([], set())
    with pytest.raises(ToolError, match="No windows found"):
        _call(app, "App", desktop, mode="switch", name="Nowhere")


def test_app_launch_of_unknown_app_is_a_tool_error():
    desktop = Desktop.__new__(Desktop)
    desktop.get_apps_from_start_menu = lambda: {}
    with pytest.raises(ToolError, match="not found in start menu"):
        _call(app, "App", desktop, mode="launch", name="Nowhere")


def test_powershell_nonzero_exit_is_a_tool_error_with_the_output():
    with patch(EXECUTE, return_value=("oops", 3)):
        with pytest.raises(ToolError, match="(?s)oops.*Status Code: 3"):
            _call(shell, "PowerShell", command="exit 3")


def test_powershell_listed_exit_code_is_a_success():
    # findstr exits 1 when nothing matches; robocopy uses 1-7 for success.
    with patch(EXECUTE, return_value=("", 1)):
        result = _call(shell, "PowerShell", command="findstr x y", success_exit_codes=[0, 1])
    assert result.content[0].text.endswith("Status Code: 1")


def test_powershell_timeout_is_an_error_even_when_1_is_listed():
    with patch(EXECUTE, return_value=("Command execution timed out", PowerShellExecutor.NOT_RUN)):
        with pytest.raises(ToolError, match="timed out"):
            _call(shell, "PowerShell", command="sleep 99", success_exit_codes=[0, 1])


def test_executor_reports_a_timeout_as_not_run(monkeypatch):
    import subprocess

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("pwsh", 1)

    monkeypatch.setattr("windows_mcp.powershell.service.run_with_graceful_timeout", timeout)
    _, status = PowerShellExecutor.execute_command("sleep 99", timeout=1)
    assert status == PowerShellExecutor.NOT_RUN


def test_clipboard_set_without_text_is_a_tool_error():
    # Fails before the clipboard is opened, so the real clipboard is untouched.
    with pytest.raises(ToolError, match="text parameter required"):
        _call(clipboard, "Clipboard", mode="set")


def test_notification_to_unknown_app_is_a_tool_error():
    with patch(EXECUTE, return_value=("UNKNOWN_APP_ID", 3)):  # no real toast is shown
        with pytest.raises(ToolError, match="not an installed app"):
            _call(notification, "Notification", title="T", message="M", app_id="Made.Up.App")


@pytest.mark.parametrize(
    ("tool", "message"), [("Screenshot", "screenshot"), ("Snapshot", "desktop")]
)
def test_capture_failure_is_a_tool_error(tool, message):
    bad_display = ValueError("Invalid display index 7. Available displays: 0")
    with patch.object(snapshot, "capture_desktop_state", side_effect=bad_display):
        with pytest.raises(ToolError, match=f"Error capturing {message}.*Invalid display index 7"):
            _call(snapshot, tool, object(), display=[7])
