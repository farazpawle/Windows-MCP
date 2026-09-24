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
    monkeypatch.setattr(_new_windows, "_seen_dialogs", set())
    monkeypatch.setattr(_new_windows, "_front_dialogs", lambda: dict(dialogs))
    dialogs.clear()
    return windows


# In-window dialogs of the front window as {runtime id: description}, changeable per test.
dialogs: dict[tuple, str] = {}


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


SAVE = '"Notepad" in "Untitled - Notepad": "Do you want to save changes to Untitled.txt?"'


def test_a_dialog_inside_the_front_window_is_named_once(desktop):
    # Round-4 R4-5: Notepad's "save changes?" is drawn inside its own window, so no new
    # top-level window appeared and the note stayed silent.
    click = _tool(desktop)
    assert click() == "Clicked."
    dialogs[(42, 1)] = SAVE  # came up after the previous reply
    assert click() == f"Clicked.\n\nNote: a dialog is open: {SAVE}."
    assert click() == "Clicked."  # reported once while it stays open


def test_a_dialog_and_a_new_window_are_both_named(desktop):
    dialogs[(42, 1)] = SAVE
    reply = _tool(desktop, {7: ("Avast Antivirus", 5678)})()
    assert '"Avast Antivirus"' in reply and f"a dialog is open: {SAVE}" in reply


def test_the_question_is_the_first_text_other_than_the_dialog_title():
    # Live, Notepad's first text element was the title "Notepad", not the question.
    names = ["", "Notepad", "Do you want to save changes to Untitled.txt?", "Save"]
    assert _new_windows._question(names, "Notepad") == (
        "Do you want to save changes to Untitled.txt?"
    )
    assert _new_windows._question(["Notepad"], "Notepad") == ""


def test_only_newer_toolkit_windows_are_searched(monkeypatch):
    # The UIA search costs ~0.03-0.18 s; only XAML (WinUI/UWP) apps draw dialogs inside.
    # Child "handles" are their class names here.
    children = {
        "notepad": ["NotepadTextBox", "Microsoft.UI.Content.DesktopChildSiteBridge"],
        "settings": ["Windows.UI.Core.CoreWindow"],
        "excel": ["XLDESK", "EXCEL7"],
    }
    monkeypatch.setattr(
        _new_windows.win32gui,
        "EnumChildWindows",
        lambda h, cb, extra: all(cb(c, extra) for c in children[h]),
    )
    monkeypatch.setattr(_new_windows.win32gui, "GetClassName", lambda c: c)
    assert _new_windows._is_xaml_window("notepad")
    assert _new_windows._is_xaml_window("settings")
    assert not _new_windows._is_xaml_window("excel")


def test_a_failed_action_still_raises(desktop):
    @_new_windows.note_new_windows
    def fails():
        raise ValueError("no")

    with pytest.raises(ValueError):
        fails()
