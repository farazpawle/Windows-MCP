"""Desktop.find_text: targeted static-text search used by WaitFor text_exists."""

from unittest.mock import MagicMock, patch

import pytest

from windows_mcp.desktop.service import Desktop


@pytest.fixture
def desktop():
    with patch.object(Desktop, "__init__", lambda self: None):
        return Desktop()


@pytest.fixture
def automation():
    ia = MagicMock()
    with patch("windows_mcp.uia.core._AutomationClient.instance") as instance:
        instance.return_value.IUIAutomation = ia
        yield ia


def test_finds_text_in_a_window(desktop, automation):
    automation.ElementFromHandle.return_value.FindFirst.return_value = MagicMock()
    with patch("windows_mcp.desktop.service.is_window_hung", return_value=False):
        assert desktop.find_text("saved", [5]) is True
    automation.ElementFromHandle.assert_called_once_with(5)


def test_skips_hung_windows(desktop, automation):
    with patch("windows_mcp.desktop.service.is_window_hung", return_value=True):
        assert desktop.find_text("saved", [5]) is False
    automation.ElementFromHandle.assert_not_called()


def test_uia_failure_counts_as_not_found(desktop, automation):
    automation.ElementFromHandle.side_effect = TimeoutError
    with patch("windows_mcp.desktop.service.is_window_hung", return_value=False):
        assert desktop.find_text("saved", [5, 6]) is False


def test_null_result_is_not_found(desktop, automation):
    automation.ElementFromHandle.return_value.FindFirst.return_value = None
    with patch("windows_mcp.desktop.service.is_window_hung", return_value=False):
        assert desktop.find_text("saved", [5]) is False
