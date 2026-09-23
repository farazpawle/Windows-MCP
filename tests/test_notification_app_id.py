"""Round-2 3.14: an empty app_id is refused instead of reaching Windows."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError

from windows_mcp.notifications import send_notification
from windows_mcp.tools import notification as notification_tool_module

EXECUTE = "windows_mcp.powershell.PowerShellExecutor.execute_command"


def _tool():
    tools = {}

    class FakeMCP:
        def tool(self, *, name, **_):
            return lambda func: tools.setdefault(name, func)

    notification_tool_module.register(
        FakeMCP(), get_desktop=MagicMock(), get_analytics=lambda: None
    )
    return lambda **kwargs: asyncio.run(tools["Notification"](**kwargs))


@pytest.mark.parametrize("app_id", ["", "   ", "\t"])
def test_blank_app_id_is_refused_before_powershell(app_id):
    # "" made the registry check test the AppUserModelId folder itself, which exists,
    # so Windows was asked and the reply was "Windows reports the setting ''".
    with patch(EXECUTE) as execute:
        reply = send_notification("t", "m", app_id)
    assert reply.startswith("Error: app_id is required")
    execute.assert_not_called()


def test_blank_app_id_is_a_tool_error():
    with patch(EXECUTE) as execute:
        with pytest.raises(ToolError, match="app_id is required"):
            _tool()(title="t", message="m", app_id="")
    execute.assert_not_called()
