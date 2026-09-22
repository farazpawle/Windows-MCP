"""A frozen app must cost a bounded, short time — never hang the whole capture.

The legacy CUIAutomation object has no call timeout, so any UIA call into a window
whose thread stopped pumping messages blocked forever. CUIAutomation8 exposes
ConnectionTimeout/TransactionTimeout; the call then fails with
HRESULT_FROM_WIN32(ERROR_TIMEOUT) instead.
"""

from unittest.mock import MagicMock, patch

from _ctypes import COMError

from windows_mcp.desktop.views import Size
from windows_mcp.tree.service import Tree
from windows_mcp.tree.views import BoundingBox
from windows_mcp.uia import core
from windows_mcp.uia.exceptions import UIATimeoutError, from_com_error

ERROR_TIMEOUT_HRESULT = -2147023436  # 0x800705B4, observed live from a hung Electron window


def test_win32_timeout_hresult_maps_to_timeout_error():
    err = COMError(ERROR_TIMEOUT_HRESULT, "timeout period expired", None)
    assert isinstance(from_com_error(err), UIATimeoutError)


def test_automation_client_uses_cuiautomation8_with_timeouts():
    automation = MagicMock()
    with (
        patch.object(core.comtypes.client, "CreateObject", return_value=automation) as create,
        patch.object(core, "safe_get_module") as get_module,
    ):
        client = core._AutomationClient()

    uia_core = get_module.return_value
    create.assert_called_once_with(uia_core.CUIAutomation8, interface=uia_core.IUIAutomation2)
    assert client.IUIAutomation is automation
    assert automation.ConnectionTimeout == core.UIA_CONNECTION_TIMEOUT_MS
    assert automation.TransactionTimeout == core.UIA_TRANSACTION_TIMEOUT_MS
    assert core.UIA_TRANSACTION_TIMEOUT_MS <= 5000


def _tree() -> Tree:
    desktop = MagicMock()
    desktop.get_screen_size.return_value = Size(width=1920, height=1080)
    desktop.get_screen_box.return_value = BoundingBox(
        left=0, top=0, right=1920, bottom=1080, width=1920, height=1080
    )
    tree = Tree(desktop)
    live_desktop = MagicMock()
    live_desktop.is_window_browser.return_value = False
    tree.desktop = live_desktop
    return tree


def test_timed_out_window_is_not_retried(monkeypatch):
    tree = _tree()
    monkeypatch.setattr(
        "windows_mcp.tree.service.ControlFromHandle",
        lambda handle: MagicMock(ClassName="SomeWindow", Name="Frozen"),
    )
    sleeps = []
    monkeypatch.setattr("windows_mcp.tree.service.sleep", sleeps.append)
    calls = []

    def fake_get_nodes(self, handle, is_browser=False, wait_time=0, use_dom=False):
        calls.append(handle)
        if handle == 111:
            raise UIATimeoutError(ERROR_TIMEOUT_HRESULT)
        return ([], [], [], None)

    monkeypatch.setattr(Tree, "get_nodes", fake_get_nodes)

    *_, failed, _ = tree.get_window_wise_nodes(windows_handles=[111, 222], active_window_flag=False)

    assert calls == [111, 222]
    assert failed == [111]
    assert sleeps == []
