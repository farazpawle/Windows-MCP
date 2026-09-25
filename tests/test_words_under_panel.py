"""R4-13: words under a panel drawn inside their own window (Notepad's Find panel) are hidden.

Notepad's panel is a XAML island child window. The compositor draws it over the document,
yet it sits below the document in the window stacking order, so WindowFromPoint still
reports the document under it (measured live 2026-09-25): the check lists the island
windows instead of hit-testing.
"""

import pytest

from windows_mcp.tree import utils

ROOT, DOC, DOC_CHILD, OUTER = 1, 10, 11, 12
PANEL, HIDDEN_PANEL, TOOLBAR = 20, 21, 22
BRIDGE = "Microsoft.UI.Content.DesktopChildSiteBridge"
WINDOWS = {  # handle: (class, visible, rect)
    OUTER: ("NotepadTextBox", True, (0, 100, 1000, 600)),
    DOC: ("RichEditD2DPT", True, (0, 100, 1000, 600)),
    DOC_CHILD: (BRIDGE, True, (0, 100, 1000, 600)),
    PANEL: (BRIDGE, True, (300, 100, 900, 220)),
    HIDDEN_PANEL: (BRIDGE, False, (0, 100, 1000, 600)),
    TOOLBAR: ("ToolbarWindow32", True, (0, 100, 1000, 600)),
}
DESCENDANTS = {OUTER: {DOC, DOC_CHILD}, DOC: {DOC_CHILD}}


@pytest.fixture(autouse=True)
def windows(monkeypatch):
    g = utils.win32gui

    def enum_children(parent, callback, extra):
        for handle in WINDOWS:
            callback(handle, extra)

    monkeypatch.setattr(g, "EnumChildWindows", enum_children)
    monkeypatch.setattr(g, "GetAncestor", lambda h, f: ROOT)
    monkeypatch.setattr(g, "GetClassName", lambda h: WINDOWS[h][0])
    monkeypatch.setattr(g, "IsWindowVisible", lambda h: WINDOWS[h][1])
    monkeypatch.setattr(g, "GetWindowRect", lambda h: WINDOWS[h][2])
    monkeypatch.setattr(g, "IsChild", lambda a, b: b in DESCENDANTS.get(a, ()))


def test_only_a_visible_island_beside_the_document_counts():
    # Not the document's own island child, not its ancestors, not a hidden island,
    # not a plain child window (their stacking order is honest).
    assert utils.panels_over(DOC) == [(300, 100, 900, 220)]


def test_element_without_its_own_window_has_no_panels():
    assert utils.panels_over(0) == []
