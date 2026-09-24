"""Type(clear=True) must empty the field even where Ctrl+A is ignored.

Legacy Win32 EDIT boxes (apps without visual styles) ignore Ctrl+A, so the old
Ctrl+A, Backspace sequence deleted one character and appended the new text.
"""

from unittest.mock import MagicMock, patch

import pytest

import windows_mcp.uia as uia
from windows_mcp.desktop.service import Desktop


@pytest.fixture
def desktop():
    with patch.object(Desktop, "__init__", lambda self: None):
        return Desktop()


def _type_with_focused(desktop, pattern):
    focused = MagicMock()
    focused.GetPattern.return_value = pattern
    with (
        patch.object(uia, "Click"),
        patch.object(uia, "SendKeys"),
        patch.object(uia, "GetFocusedControl", return_value=focused),
        patch("windows_mcp.desktop.service.sleep"),
    ):
        desktop.type((10, 10), text="new", clear=True)


def test_leftover_text_is_cleared_through_value_pattern(desktop):
    pattern = MagicMock(IsReadOnly=False, Value="XYZHelloWorlda")
    _type_with_focused(desktop, pattern)
    pattern.SetValue.assert_called_once()
    assert pattern.SetValue.call_args.args == ("",)


def test_already_empty_field_is_left_alone(desktop):
    pattern = MagicMock(IsReadOnly=False, Value="")
    _type_with_focused(desktop, pattern)
    pattern.SetValue.assert_not_called()


def test_read_only_or_patternless_fields_are_left_alone(desktop):
    read_only = MagicMock(IsReadOnly=True, Value="text")
    _type_with_focused(desktop, read_only)
    read_only.SetValue.assert_not_called()
    _type_with_focused(desktop, None)  # must not raise


def test_value_pattern_error_does_not_break_typing(desktop):
    pattern = MagicMock(IsReadOnly=False, Value="left")
    pattern.SetValue.side_effect = RuntimeError("provider refused")
    _type_with_focused(desktop, pattern)  # must not raise
