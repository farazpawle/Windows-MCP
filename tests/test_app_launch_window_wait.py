"""Round-3 R3-10: App launch finds the new window without a UIA tree walk.

The UIA search walked every top-level window; one slow window made it time out
after ~15 s with COMError -2146233083 although the app had opened.
"""

from unittest.mock import patch

import pytest

import windows_mcp.desktop.service as service
from windows_mcp.desktop.service import Desktop


def _launch(monkeypatch, windows, pid=0, name="calculator", opened=()):
    """Run App launch with *windows* = [(title, pid), ...] as the visible top-level windows.

    *windows* exist before the launch; *opened* appear when the app starts.
    """
    desktop = Desktop.__new__(Desktop)
    handles = {i + 1: w for i, w in enumerate(windows)}

    def launch_app(_):
        for w in opened:
            handles[len(handles) + 1] = w
        return name, 0, pid

    monkeypatch.setattr(desktop, "launch_app", launch_app)
    monkeypatch.setattr(Desktop, "_LAUNCH_WAIT", 0.3)
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


def test_a_window_open_before_the_launch_is_not_named(monkeypatch):
    # Round-4 R4-2: "*report.txt - Notepad launched." while the new one was "Untitled - Notepad".
    reply = _launch(
        monkeypatch,
        [("*report.txt - Notepad", 5)],
        name="notepad",
        opened=[("Untitled - Notepad", 6)],
    )
    assert reply == "Untitled - Notepad launched (handle 2)."


def test_only_old_windows_matching_is_not_detected(monkeypatch):
    with patch.object(service.win32gui, "GetForegroundWindow", lambda: 99):
        reply = _launch(monkeypatch, [("Calculator", 5)])
    assert reply == "Launching calculator sent, but window not detected yet."


def test_an_old_window_brought_to_the_front_is_named_as_reused(monkeypatch):
    # Store Notepad can open a new tab in its running window instead of a new window.
    with patch.object(service.win32gui, "GetForegroundWindow", lambda: 1):
        reply = _launch(monkeypatch, [("*report.txt - Notepad", 5)], name="notepad")
    assert reply == (
        "Launching notepad sent; no new window appeared, but the open window "
        '"*report.txt - Notepad" (handle 1) came to the front (it may have opened there).'
    )


def test_window_found_by_title_without_uia(monkeypatch):
    reply = _launch(monkeypatch, [("Other", 5)], opened=[("Calculator", 9)])
    assert reply == "Calculator launched (handle 2)."


def test_window_found_by_process_id(monkeypatch):
    reply = _launch(monkeypatch, [], pid=42, name="wmcp harness", opened=[("Harness Window", 42)])
    assert reply == "Harness Window launched (handle 1)."


def test_no_window_yet_is_not_an_error(monkeypatch):
    reply = _launch(monkeypatch, [("Other", 5)])
    assert reply == "Launching calculator sent, but window not detected yet."


@pytest.mark.parametrize("title", ["", "Calculatorish helper"])
def test_untitled_or_partial_titles_still_match_like_before(monkeypatch, title):
    # Untitled windows are skipped; a title containing the name matches (old regex rule).
    reply = _launch(monkeypatch, [], opened=[(title, 5)])
    expected = (
        f"{title} launched (handle 1)."
        if title
        else "Launching calculator sent, but window not detected yet."
    )
    assert reply == expected
