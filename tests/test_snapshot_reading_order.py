"""Round-6 R6-13: Snapshot listed a native window's elements bottom-to-top.

The traversal visits children last-to-first and the tree used to be flipped back once,
which listed Notepad's words last-line-first, the document after them and the title bar
last, with labels counting up the page.
"""

from unittest.mock import MagicMock

import pytest

from windows_mcp.desktop.views import Size
from windows_mcp.tree.service import Tree
from windows_mcp.tree.views import (
    BoundingBox,
    Center,
    SemanticNode,
    TreeElementNode,
    TreeState,
    sort_reading_order,
)
from windows_mcp.uia.controls import WindowControl
from windows_mcp.uia.core import Rect
from windows_mcp.uia.enums import AccessibleRole


def _box(left, top, right, bottom):
    return BoundingBox(left, top, right, bottom, right - left, bottom - top)


def _pair(name, box, control_type="Button", kind="interactive"):
    """The flat entry (label source) and its twin in the tree, as the traversal makes them."""
    center = Center((box.left + box.right) // 2, (box.top + box.bottom) // 2)
    flat = TreeElementNode(
        bounding_box=box, center=center, name=name, control_type=control_type, window_name="W"
    )
    twin = SemanticNode(
        control_type=control_type,
        element_type=kind,
        name=name,
        window_name="W",
        center=center,
        bounding_box=box,
    )
    return flat, twin


def _snapshot(entries):
    """Build a window from (name, box, control_type) in the traversal's visit order."""
    window = SemanticNode(control_type="Window", element_type="window", name="W", window_name="W")
    flat = []
    for name, box, control_type in entries:
        node, twin = _pair(name, box, control_type)
        flat.append(node)
        window.add_child(twin)
    sort_reading_order(window, flat, [])
    root = SemanticNode(control_type="Desktop", element_type="desktop", name="Desktop")
    root.add_child(window)
    lines = TreeState(interactive_nodes=flat, semantic_tree_root=root).semantic_tree_to_string()
    return [line.split('"')[1] for line in lines.splitlines()[2:]], lines


# Visit order read live from a Notepad test tab (2026-09-28): title bar first, right to
# left, then the toolbar and tabs right to left, then the document and its words.
NOTEPAD_VISIT = [
    ("Close", _box(1220, 133, 1266, 165), "Button"),
    ("Maximise", _box(1174, 133, 1220, 165), "Button"),
    ("Minimise", _box(1128, 133, 1174, 165), "Button"),
    ("Edit", _box(325, 176, 361, 206), "Menu Item"),
    ("File", _box(274, 176, 310, 206), "Menu Item"),
    ("Add New Tab", _box(1058, 147, 1086, 175), "Button"),
    ("r613doc.txt", _box(930, 145, 1044, 173), "Tab Item"),
    ("Close Tab", _box(1016, 147, 1040, 171), "Button"),
    ("RSC2021103", _box(808, 145, 922, 173), "Tab Item"),
    ("Text editor", _box(262, 220, 1272, 690), "Document"),
    ("alpha", _box(285, 226, 323, 243), "Word"),
    ("bravo", _box(330, 226, 374, 243), "Word"),
    ("charlie", _box(285, 244, 339, 261), "Word"),
    ("delta", _box(346, 244, 390, 261), "Word"),
]


def test_notepad_lists_top_of_window_first_and_words_in_reading_order():
    names, _ = _snapshot(NOTEPAD_VISIT)
    assert names == [
        "RSC2021103",
        "r613doc.txt",
        "Close Tab",
        "Add New Tab",
        "Minimise",
        "Maximise",
        "Close",
        "File",
        "Edit",
        "Text editor",
        "alpha",
        "bravo",
        "charlie",
        "delta",
    ]


def test_labels_count_down_the_page_and_still_name_the_listed_element():
    _, text = _snapshot(NOTEPAD_VISIT)
    lines = text.splitlines()[2:]
    assert [int(line.split("[label:")[1].split("]")[0]) for line in lines] == list(range(14))
    assert '[label:0] (865,159) tab item "RSC2021103"' in lines[0]
    assert '[label:13] (368,252) word "delta"' in lines[13]


def test_harness_window_title_bar_then_buttons_then_text_box():
    # Visit order read live from the harness window: title bar, buttons, then the box.
    names, _ = _snapshot(
        [
            ("Close", _box(666, 302, 712, 330), "Button"),
            ("Minimise", _box(573, 302, 619, 330), "Button"),
            ("Cancel", _box(473, 334, 548, 358), "Button"),
            ("OK", _box(311, 334, 386, 358), "Button"),
            ("", _box(310, 380, 710, 562), "Edit"),
        ]
    )
    assert names == ["Minimise", "Close", "OK", "Cancel", ""]


def test_a_group_moves_as_one_by_its_top_element():
    window = SemanticNode(control_type="Window", element_type="window", name="W", window_name="W")
    toolbar = SemanticNode(control_type="Tool Bar", element_type="structural", name="Tools")
    lower, lower_twin = _pair("Lower", _box(0, 300, 50, 320))
    upper, upper_twin = _pair("Upper", _box(0, 100, 50, 120))
    right, right_twin = _pair("Right", _box(60, 100, 110, 120))
    toolbar.children = [right_twin, upper_twin]
    window.children = [lower_twin, toolbar]
    flat = [lower, right, upper]
    sort_reading_order(window, flat, [])
    assert [c.name for c in window.children] == ["Tools", "Lower"]
    assert [c.name for c in toolbar.children] == ["Upper", "Right"]
    assert [n.name for n in flat] == ["Upper", "Right", "Lower"]


def test_scroll_entries_follow_the_tree_order_too():
    window = SemanticNode(control_type="Window", element_type="window", name="W", window_name="W")
    low, low_twin = _pair("Low", _box(0, 400, 100, 500), "Pane", "scrollable")
    high, high_twin = _pair("High", _box(0, 100, 100, 200), "Pane", "scrollable")
    window.children = [low_twin, high_twin]
    scrolls = [low, high]
    sort_reading_order(window, [], scrolls)
    assert [n.name for n in scrolls] == ["High", "Low"]


# --- a pop-up inside the window stays one group ------------------------------------------


@pytest.fixture
def tree():
    desktop = MagicMock()
    desktop.get_screen_size.return_value = Size(width=1920, height=1080)
    desktop.get_screen_box.return_value = _box(0, 0, 1920, 1080)
    return Tree(desktop)


def _element(control_type, name, rect, spec=None):
    element = MagicMock(spec=spec) if spec else MagicMock()
    element.CachedIsOffscreen = False
    element.CachedControlTypeName = control_type
    element.CachedIsControlElement = True
    element.CachedBoundingRectangle = rect
    element.CachedIsEnabled = True
    element.CachedIsKeyboardFocusable = True
    element.CachedHasKeyboardFocus = False
    element.CachedName = name
    element.CachedLocalizedControlType = control_type.removesuffix("Control").lower()
    element.CachedAcceleratorKey = ""
    element.CachedHelpText = ""
    element.CachedAutomationId = ""
    element.GetCachedPattern.return_value = None
    element.GetCachedPropertyValue.side_effect = lambda prop: (
        AccessibleRole.PushButton if control_type == "ButtonControl" else False
    )
    return element


def test_a_dialog_inside_the_window_is_its_own_group(tree, monkeypatch):
    # Notepad's "save changes?" question is drawn inside its window: sorted by position,
    # its buttons would sit among the document's words.
    window = _element("WindowControl", "Notepad", Rect(0, 0, 800, 600))
    behind = _element("ButtonControl", "Behind", Rect(10, 300, 90, 330))
    dialog = _element("WindowControl", "Save changes?", Rect(200, 200, 600, 400), WindowControl)
    save = _element("ButtonControl", "Save", Rect(220, 350, 300, 380))
    children_of = {id(window): [behind, dialog], id(dialog): [save]}
    monkeypatch.setattr(
        "windows_mcp.tree.service.CachedControlHelper.get_cached_children",
        lambda node, request: children_of.get(id(node), []),
    )
    root = SemanticNode(control_type="Window", element_type="window", name="Notepad")
    flat = []
    tree.tree_traversal(
        window, Rect(0, 0, 800, 600), "Notepad", False, flat, [], [], [], current_semantic_node=root
    )
    by_name = {c.name: c for c in root.children}
    assert set(by_name) == {"Behind", "Save changes?"}
    assert by_name["Save changes?"].element_type == "structural"
    assert [c.name for c in by_name["Save changes?"].children] == ["Save"]
