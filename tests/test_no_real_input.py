"""The test suite must never type or click on the real desktop (2026-09-28)."""

import ctypes

from windows_mcp.desktop.service import Desktop


def test_typing_in_a_test_reaches_no_real_window():
    # Desktop.type with nothing patched typed into the window in front before the
    # conftest guard stubbed user32's input functions.
    Desktop.__new__(Desktop).type(None, "x")
    assert ctypes.windll.user32.SendInput.called
