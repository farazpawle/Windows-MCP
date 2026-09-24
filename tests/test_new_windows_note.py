"""Round-3 R3-N1: input replies name any window that appeared since the last action.

Both round-3 surprises (Notepad's question, Avast's alert) were found only by accident.
"""

import pytest

from windows_mcp.tools import _new_windows


@pytest.fixture
def desktop(monkeypatch):
    """Visible titled top-level windows as {handle: (title, pid)}, changeable per test."""
    windows = {1: ("Notepad", 100)}
    monkeypatch.setattr(_new_windows, "_seen", None)
    monkeypatch.setattr(
        _new_windows, "_top_windows", lambda: {h: t for h, (t, _) in windows.items()}
    )
    monkeypatch.setattr(_new_windows, "_process_of", lambda h: (windows[h][1], "app.exe"))
    return windows


def _tool(desktop, opens=None):
    @_new_windows.note_new_windows
    def click():
        if opens:
            desktop.update(opens)
        return "Clicked."

    return click


def test_a_window_opened_by_the_action_is_named(desktop):
    reply = _tool(desktop, {7: ("Avast Antivirus", 5678)})()
    assert reply == (
        'Clicked.\n\nNote: a new window appeared: "Avast Antivirus" (handle=7, pid=5678 app.exe).'
    )


def test_nothing_new_leaves_the_reply_alone(desktop):
    assert _tool(desktop)() == "Clicked."


def test_a_window_that_appeared_between_actions_is_named_on_the_next(desktop):
    click = _tool(desktop)
    assert click() == "Clicked."
    desktop[9] = ("Save changes?", 100)  # a pop-up that came up after the reply
    assert '"Save changes?" (handle=9' in click()
    assert click() == "Clicked."  # reported once


def test_several_new_windows_are_all_named(desktop):
    reply = _tool(desktop, {7: ("One", 1), 8: ("Two", 2)})()
    assert "new windows appeared:" in reply and '"One"' in reply and '"Two"' in reply


def test_a_failed_action_still_raises(desktop):
    @_new_windows.note_new_windows
    def fails():
        raise ValueError("no")

    with pytest.raises(ValueError):
        fails()
