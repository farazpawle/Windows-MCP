"""Round-3 R3-10: App launch finds the new window without a UIA tree walk.

The UIA search walked every top-level window; one slow window made it time out
after ~15 s with COMError -2146233083 although the app had opened.
"""

from unittest.mock import patch

import pytest

import windows_mcp.desktop.service as service
from windows_mcp.desktop.service import Desktop


def _launch(monkeypatch, windows, pid=0, name="calculator"):
    """Run App launch with *windows* = [(title, pid), ...] as the visible top-level windows."""
    desktop = Desktop.__new__(Desktop)
    monkeypatch.setattr(desktop, "launch_app", lambda _: (name, 0, pid))
    monkeypatch.setattr(Desktop, "_LAUNCH_WAIT", 0.3)
    handles = {i + 1: w for i, w in enumerate(windows)}
    with (
        patch.object(
            service.win32gui, "EnumWindows", lambda cb, extra: [cb(h, extra) for h in handles]
        ),
        patch.object(service.win32gui, "IsWindowVisible", lambda h: True),
        patch.object(service.win32gui, "GetWindowText", lambda h: handles[h][0]),
        patch.object(
            service.win32process, "GetWindowThreadProcessId", lambda h: (0, handles[h][1])
        ),
        patch.object(service.uia, "WindowControl", side_effect=AssertionError("UIA tree walk")),
    ):
        return desktop.app("launch", name=name)


def test_window_found_by_title_without_uia(monkeypatch):
    assert _launch(monkeypatch, [("Other", 5), ("Calculator", 9)]) == "Calculator launched."


def test_window_found_by_process_id(monkeypatch):
    reply = _launch(monkeypatch, [("Harness Window", 42)], pid=42, name="wmcp harness")
    assert reply == "Harness Window launched."


def test_no_window_yet_is_not_an_error(monkeypatch):
    reply = _launch(monkeypatch, [("Other", 5)])
    assert reply == "Launching calculator sent, but window not detected yet."


@pytest.mark.parametrize("title", ["", "Calculatorish helper"])
def test_untitled_or_partial_titles_still_match_like_before(monkeypatch, title):
    # Untitled windows are skipped; a title containing the name matches (old regex rule).
    reply = _launch(monkeypatch, [(title, 5)])
    expected = (
        f"{title} launched." if title else "Launching calculator sent, but window not detected yet."
    )
    assert reply == expected
