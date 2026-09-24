"""1.6: never walk the UI tree of VS Code-family windows (one read locks VS Code up)."""

from unittest.mock import MagicMock, patch

import pytest

from windows_mcp.desktop.service import Desktop
from windows_mcp.tree import utils
from windows_mcp.tree.budget import TreeElementBudget
from windows_mcp.tree.service import Tree

VSCODE, NOTEPAD = 111, 222


@pytest.fixture
def process_names(monkeypatch):
    names = {VSCODE: "Code.exe", NOTEPAD: "Notepad.exe"}
    monkeypatch.setattr(utils, "_process_name", lambda handle: names.get(handle, ""))
    monkeypatch.delenv("WINDOWS_MCP_READ_VSCODE", raising=False)


@pytest.mark.parametrize(
    "exe", ["Code.exe", "Cursor.exe", "Windsurf.exe", "Antigravity.exe", "VSCodium.exe"]
)
def test_vscode_family_blocked(monkeypatch, exe):
    monkeypatch.setattr(utils, "_process_name", lambda handle: exe)
    monkeypatch.delenv("WINDOWS_MCP_READ_VSCODE", raising=False)
    assert utils.is_unreadable_window(1) is True


def test_other_apps_not_blocked(process_names):
    assert utils.is_unreadable_window(NOTEPAD) is False


def test_setting_turns_reading_back_on(process_names, monkeypatch):
    monkeypatch.setenv("WINDOWS_MCP_READ_VSCODE", "1")
    assert utils.is_unreadable_window(VSCODE) is False


def test_tree_walk_skips_vscode(process_names):
    tree = Tree.__new__(Tree)
    tree.desktop = MagicMock()
    tree.desktop.is_window_browser.return_value = False
    tree.element_budget = TreeElementBudget(500)
    with (
        patch("windows_mcp.tree.service.ControlFromHandle") as control,
        patch.object(Tree, "get_nodes", return_value=([], [], [], None)) as get_nodes,
    ):
        control.return_value.ClassName = "Chrome_WidgetWin_1"
        control.return_value.Name = "file.py - Visual Studio Code"
        *_, window_nodes = tree.get_window_wise_nodes([VSCODE, NOTEPAD], active_window_flag=True)
    assert [c.args[0] for c in get_nodes.call_args_list] == [NOTEPAD]
    assert "not read" in window_nodes[0].name


def test_find_text_skips_vscode(process_names):
    desktop = Desktop.__new__(Desktop)
    with patch("windows_mcp.desktop.service.uia") as uia:
        assert desktop.find_text("hello", [VSCODE]) is False
    uia.core._AutomationClient.instance.return_value.IUIAutomation.ElementFromHandle.assert_not_called()
