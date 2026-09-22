"""Regression tests for bugs found while filling Plan/windows-mcp-open-issues.md section 5."""

from unittest.mock import MagicMock, patch

import pytest

from windows_mcp.desktop.service import Desktop
from windows_mcp.powershell import PowerShellExecutor


def test_app_launch_names_the_matched_start_menu_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """5.1: App launch "code" must look for and name "Visual Studio Code", not "Code"."""
    app_id = "Microsoft.VisualStudioCode"
    monkeypatch.setattr(PowerShellExecutor, "execute_command", staticmethod(lambda *_: ("", 0)))
    desktop = Desktop.__new__(Desktop)
    monkeypatch.setattr(desktop, "get_apps_from_start_menu", lambda: {"visual studio code": app_id})
    monkeypatch.setattr(desktop, "_check_app_exists", lambda _: True)

    searched: list[str] = []

    def window_control(**kwargs):
        searched.append(kwargs.get("RegexName", ""))
        return MagicMock(Exists=MagicMock(return_value=True))

    with patch("windows_mcp.desktop.service.uia.WindowControl", side_effect=window_control):
        reply = desktop.app("launch", name="code")

    assert reply == "Visual Studio Code launched."
    assert searched == ["(?i).*visual\\ studio\\ code.*"]
