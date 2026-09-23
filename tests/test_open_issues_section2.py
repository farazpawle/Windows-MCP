"""Regression tests for Plan/windows-mcp-open-issues.md section 2 (Medium)."""

import asyncio
import inspect
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image as PILImage

from windows_mcp import registry
from windows_mcp.desktop.service import Desktop, draw_grid
from windows_mcp.powershell import PowerShellExecutor
from windows_mcp.notifications import send_notification
from windows_mcp.powershell.service import decode_clixml
from windows_mcp.registry.service import parse_binary
from windows_mcp.tools import scrape as scrape_tool_module
from windows_mcp.tools import shell as shell_tool_module
from windows_mcp.tools._snapshot_helpers import capture_desktop_state

EXECUTE_COMMAND_PATH = "windows_mcp.powershell.PowerShellExecutor.execute_command"
RUN_PATH = "windows_mcp.powershell.service.run_with_graceful_timeout"

# Real stderr captured from pwsh 7 for `Get-Item C:/nope_missing` (progress record added
# from the Windows PowerShell 5.1 capture of the same command).
CLIXML_ERR = (
    "#< CLIXML\r\n"
    '<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04">'
    '<Obj S="progress" RefId="0"><TN RefId="0"><T>System.Object</T></TN><MS>'
    '<PR N="Record"><AV>Preparing modules for first use.</AV></PR></MS></Obj>'
    '<S S="Error">_x001B_[31;1mGet-Item: _x001B_[31;1mCannot find path '
    "'C:\\nope_missing' because it does not exist._x001B_[0m_x000D__x000A_</S>"
    '<S S="warning">careful_x000D__x000A_</S>'
    "</Objs>"
)


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _shell_tool():
    mcp = FakeMCP()
    shell_tool_module.register(mcp, get_desktop=MagicMock(), get_analytics=lambda: None)
    tool = mcp.tools["PowerShell"]
    return lambda **kwargs: asyncio.run(tool(**kwargs))


def _completed(stdout: str, stderr: str, code: int) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], code, stdout.encode(), stderr.encode())


# 2.1 PowerShell errors are returned as plain text, even at exit code 0
class TestPowerShellErrors:
    def test_decode_clixml_keeps_errors_and_warnings_as_plain_text(self):
        text = decode_clixml(CLIXML_ERR)
        assert "Get-Item: Cannot find path 'C:\\nope_missing' because it does not exist." in text
        assert "WARNING: careful" in text
        assert "\x1b" not in text and "_x00" not in text
        assert "Preparing modules" not in text

    def test_decode_clixml_passes_plain_stderr_through(self):
        assert decode_clixml("native tool failed\r\n") == "native tool failed"

    def test_errors_readable_on_failure(self):
        with patch(RUN_PATH, return_value=_completed("", CLIXML_ERR, 1)):
            output, code = PowerShellExecutor.execute_command("x")
        assert code == 1
        assert output.startswith("Get-Item: Cannot find path")

    def test_errors_hidden_from_internal_callers_on_success(self):
        # Internal callers parse stdout (numbers, JSON); stray error text would break them.
        with patch(RUN_PATH, return_value=_completed("42\r\n", CLIXML_ERR, 0)):
            output, _ = PowerShellExecutor.execute_command("x")
        assert output == "42\r\n"

    def test_errors_included_on_success_when_asked(self):
        with patch(RUN_PATH, return_value=_completed("after\r\n", CLIXML_ERR, 0)):
            output, code = PowerShellExecutor.execute_command("x", include_errors=True)
        assert code == 0
        assert output.startswith("after")
        assert "Errors and messages:\nGet-Item: Cannot find path" in output

    def test_tool_includes_errors_at_exit_zero(self):
        with patch(RUN_PATH, return_value=_completed("after\r\n", CLIXML_ERR, 0)):
            reply = _shell_tool()(command="x")
        assert "Cannot find path" in reply
        assert "Status Code: 0" in reply


# 2.2 PowerShell timeout below 1 is rejected with a clear message
class TestPowerShellTimeout:
    @pytest.mark.parametrize("timeout", [0, -5])
    def test_rejects_timeout_below_one(self, timeout):
        with patch(RUN_PATH) as run:
            with pytest.raises(ValueError, match="timeout"):
                _shell_tool()(command="x", timeout=timeout)
        run.assert_not_called()


# 2.3 Registry binary values accept several bytes
class TestRegistryBinary:
    @pytest.mark.parametrize(
        "value",
        ["01,02,ff", "01 02 FF", "0x01, 0x02, 0xff", "0102ff", "[1, 2, 255]", " 01;02;ff "],
    )
    def test_parse_binary_formats(self, value):
        assert parse_binary(value) == bytes([1, 2, 255])

    def test_parse_binary_empty(self):
        assert parse_binary("") == b""

    @pytest.mark.parametrize("value", ["zz", "102", "[256]", "[-1]", "1,2,300", "[1, 'a']"])
    def test_parse_binary_rejects_bad_input(self, value):
        with pytest.raises(ValueError):
            parse_binary(value)

    def test_set_binary_builds_byte_array(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as run:
            result = registry.set_value(r"HKCU:\Software\T", "b", "01,02,ff", "Binary")
        command = run.call_args[0][0]
        assert "-Value ([byte[]](1,2,255))" in command
        assert "set to" in result

    def test_set_binary_bad_value_is_error_without_running(self):
        with patch(EXECUTE_COMMAND_PATH) as run:
            result = registry.set_value(r"HKCU:\Software\T", "b", "zz", "Binary")
        assert result.startswith("Error")
        run.assert_not_called()


# 2.4 Notification validates the app id and reports blocked delivery
class TestNotification:
    def _send(self, response):
        with patch(EXECUTE_COMMAND_PATH, return_value=response) as run:
            result = send_notification("T", "M", "Made.Up.App")
        return result, run.call_args[0][0]

    def test_script_checks_app_and_setting_before_showing(self):
        _, script = self._send(("", 0))
        assert "Get-StartApps" in script
        assert ".Setting" in script
        assert script.index(".Setting") < script.index(".Show(")

    def test_unknown_app_id_is_error(self):
        result, _ = self._send(("UNKNOWN_APP_ID\r\n", 3))
        assert result.startswith("Error")
        assert "Made.Up.App" in result and "Get-StartApps" in result

    @pytest.mark.parametrize(
        ("setting", "words"),
        [
            ("DisabledForApplication", "this app"),
            ("DisabledForUser", "all apps"),
            ("DisabledByGroupPolicy", "group policy"),
        ],
    )
    def test_blocked_setting_is_error(self, setting, words):
        result, _ = self._send((f"BLOCKED:{setting}\r\n", 4))
        assert result.startswith("Error")
        assert words in result

    def test_success_mentions_do_not_disturb(self):
        result, _ = self._send(("", 0))
        assert result.startswith("Notification sent")
        assert "Do Not Disturb" in result

    def test_other_failure_is_error(self):
        result, _ = self._send(("boom", 1))
        assert result.startswith("Error")
        assert "boom" in result


def _capture(**kwargs):
    desktop = MagicMock()
    args = dict(
        use_vision=True,
        use_dom=False,
        use_annotation=False,
        use_ui_tree=False,
        width_reference_line=None,
        height_reference_line=None,
        display=None,
        region=None,
        tool_name="Screenshot tool",
    )
    args.update(kwargs)
    return capture_desktop_state(desktop, **args), desktop


# 2.5 Screenshot says the window list was skipped, not that there are no windows
class TestWindowListSkipped:
    def test_screenshot_only_reports_skipped(self):
        result, _ = _capture(use_ui_tree=False)
        assert result["windows"].startswith("Skipped")
        assert result["active_window"].startswith("Skipped")

    def test_ui_tree_capture_lists_windows(self):
        result, desktop = _capture(use_ui_tree=True)
        state = desktop.get_state.return_value
        assert result["windows"] is state.windows_to_string.return_value


# 2.6 Grid lines are drawn on plain screenshots too, and one direction alone works
class TestGridLines:
    def test_draw_grid_draws_both_directions(self):
        image = PILImage.new("RGB", (100, 100), "black")
        draw_grid(image, (2, 4))
        assert image.getpixel((50, 10)) != (0, 0, 0)  # vertical line at x=50
        assert image.getpixel((10, 25)) != (0, 0, 0)  # horizontal line at y=25
        assert image.getpixel((10, 10)) == (0, 0, 0)

    @pytest.mark.parametrize(
        ("width", "height", "expected"),
        [(4, 3, (4, 3)), (4, None, (4, 1)), (None, 3, (1, 3)), (None, None, None)],
    )
    def test_grid_lines_from_either_reference_line(self, width, height, expected):
        _, desktop = _capture(width_reference_line=width, height_reference_line=height)
        assert desktop.get_state.call_args.kwargs["grid_lines"] == expected

    def test_grid_drawn_without_annotation(self):
        # The plain (non-annotated) screenshot path must honour grid_lines as well.
        source = inspect.getsource(Desktop.get_state)
        plain_branch = source.split("screenshot = self.get_screenshot(capture_rect=capture_rect)")[
            1
        ]
        assert (
            "draw_grid(screenshot, grid_lines)" in plain_branch.split("screenshot_original_size")[0]
        )


# 2.7 Scrape says when the summary could not be made
class TestScrapeSummaryNote:
    def _scrape(self, ctx, **kwargs):
        mcp = FakeMCP()
        desktop = MagicMock()
        desktop.scrape.return_value = "raw page"
        scrape_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
        return asyncio.run(mcp.tools["Scrape"](url="https://example.com", ctx=ctx, **kwargs))

    def test_note_when_client_cannot_summarise(self):
        ctx = MagicMock()
        ctx.sample = AsyncMock(side_effect=RuntimeError("sampling not supported"))
        reply = self._scrape(ctx)
        assert "raw page" in reply
        assert "summary unavailable" in reply

    def test_note_when_no_context(self):
        assert "summary unavailable" in self._scrape(None)

    def test_no_note_when_summarised(self):
        ctx = MagicMock()
        ctx.sample = AsyncMock(return_value=MagicMock(text="short summary"))
        reply = self._scrape(ctx)
        assert "short summary" in reply and "summary unavailable" not in reply

    def test_no_note_when_raw_requested(self):
        assert "summary unavailable" not in self._scrape(MagicMock(), use_sampling=False)


# 4.1 follow-up: Scrape use_dom reads the page's scroll position from the DOM node metadata
class TestScrapeDomScrollStatus:
    def _scrape(self, metadata):
        mcp = FakeMCP()
        desktop = MagicMock()
        tree = desktop.get_state.return_value.tree_state
        tree.dom_node = SimpleNamespace(metadata=metadata)
        tree.dom_informative_nodes = [SimpleNamespace(text="page text")]
        scrape_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
        return asyncio.run(
            mcp.tools["Scrape"](url="https://x", use_dom=True, use_sampling=False, ctx=None)
        )

    def test_page_without_scrolling(self):
        reply = self._scrape({"vertical_scrollable": False, "vertical_scroll_percent": 0})
        assert "Whole page visible" in reply
        assert "Scroll down" not in reply

    def test_middle_of_page(self):
        reply = self._scrape({"vertical_scrollable": True, "vertical_scroll_percent": 40})
        assert "Scroll up to see more" in reply and "Scroll down to see more" in reply

    def test_top_and_bottom(self):
        top = self._scrape({"vertical_scrollable": True, "vertical_scroll_percent": 0})
        bottom = self._scrape({"vertical_scrollable": True, "vertical_scroll_percent": 100})
        assert "Reached top" in top and "Scroll down to see more" in top
        assert "Scroll up to see more" in bottom and "Reached bottom" in bottom
