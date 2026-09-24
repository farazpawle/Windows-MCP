"""Round-2 B.9: a label is refused when its element is no longer at its spot."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from windows_mcp.desktop import service
from windows_mcp.desktop.service import Desktop
from windows_mcp.tree import utils
from windows_mcp.tree.views import BoundingBox, Center, TreeElementNode, TreeState


def _control(name="", automation_id="", kind="button", parent=None, rect=(0, 0, 0, 0)):
    return SimpleNamespace(
        Name=name,
        AutomationId=automation_id,
        LocalizedControlType=kind,
        GetParentControl=lambda: parent,
        BoundingRectangle=SimpleNamespace(left=rect[0], top=rect[1], right=rect[2], bottom=rect[3]),
    )


@pytest.fixture
def screen(monkeypatch):
    """A readable window at every point; set .control to what UIA finds there."""
    state = SimpleNamespace(control=None, window=5, hung=False, unreadable=False, title="Explorer")
    reads = MagicMock(
        side_effect=lambda x, y: state.control(x, y) if callable(state.control) else state.control
    )
    monkeypatch.setattr(utils, "top_level_window_at", lambda x, y: state.window)
    monkeypatch.setattr(utils.win32gui, "GetWindowText", lambda h: state.title)
    monkeypatch.setattr(utils, "is_window_hung", lambda h: state.hung)
    monkeypatch.setattr(utils, "is_unreadable_window", lambda h: state.unreadable)
    monkeypatch.setattr(utils.uia, "ControlFromPoint", reads)
    state.reads = reads
    return state


def test_same_element_is_still_there(screen):
    screen.control = _control("Save")
    assert utils.element_still_at("Save", "Button", 10, 10)


def test_name_on_a_parent_counts(screen):
    screen.control = _control("inner text", kind="text", parent=_control("Save"))
    assert utils.element_still_at("Save", "Button", 10, 10)


def test_name_match_ignores_case_and_spaces(screen):
    screen.control = _control("  save ")
    assert utils.element_still_at("Save", "Button", 10, 10)


def test_other_element_is_refused(screen):
    screen.control = _control("Delete", parent=_control("Toolbar", kind="tool bar"))
    assert not utils.element_still_at("Save", "Button", 10, 10)


def test_unnamed_field_matches_by_type(screen):
    screen.control = _control("", kind="edit")
    assert utils.element_still_at("", "Edit", 10, 10)


def test_unnamed_field_over_a_button_is_refused(screen):
    screen.control = _control("OK", kind="button")
    assert not utils.element_still_at("", "Edit", 10, 10)


def test_scroll_area_named_after_its_type_matches(screen):
    screen.control = _control("Row 3", kind="list item", parent=_control("", kind="list"))
    assert utils.element_still_at("List", "List", 10, 10)


def test_automation_id_counts(screen):
    screen.control = _control("", automation_id="searchBox", kind="edit")
    assert utils.element_still_at("searchBox", "Edit", 10, 10)


@pytest.mark.parametrize("attr", ["hung", "unreadable"])
def test_hung_or_unreadable_window_is_refused_without_reading_it(screen, attr):
    setattr(screen, attr, True)
    screen.control = _control("Save")
    assert not utils.element_still_at("Save", "Button", 10, 10)
    screen.reads.assert_not_called()


def test_no_window_at_the_point_is_refused(screen):
    screen.window = 0
    assert not utils.element_still_at("Save", "Button", 10, 10)


def test_word_labels_skip_the_name_check(screen):
    screen.control = _control("Document", kind="document")
    assert utils.element_still_at("hello", "Word", 10, 10)
    screen.reads.assert_not_called()


def test_unreadable_uia_does_not_block(screen):
    screen.reads.side_effect = OSError("COM error")
    assert utils.element_still_at("Save", "Button", 10, 10)


# --- R3-3: something else of the same window drawn at the spot ----------------------

BOX = (100, 10, 500, 40)  # the element's rectangle; centre (300, 25)
PATH_BUTTON = _control("Documents", kind="button", rect=(110, 12, 330, 38))
ADDRESS = _control("Address", kind="edit", rect=BOX)


def _address_bar(x, y):
    # Explorer's Address Bar: path buttons are drawn over the left part of the edit box.
    return PATH_BUTTON if x < 330 else ADDRESS


def test_part_drawn_over_the_centre_is_not_the_element(screen):
    screen.control = _address_bar
    assert not utils.element_still_at("Address", "Edit", 300, 25, rect=BOX, window="Explorer")


def test_a_free_point_of_the_element_is_used_instead(screen):
    screen.control = _address_bar
    x, y = utils.spot_on_element("Address", "Edit", 300, 25, rect=BOX, window="Explorer")
    assert 330 <= x < 500 and 10 <= y < 40


def test_centre_is_kept_when_it_is_the_element(screen):
    screen.control = ADDRESS
    assert utils.spot_on_element("Address", "Edit", 300, 25, rect=BOX, window="Explorer") == (
        300,
        25,
    )


def test_container_around_it_in_the_same_window_counts(screen):
    # An embedded web page answers with its page pane, not the button.
    screen.control = _control("", kind="pane", rect=(0, 0, 800, 600))
    assert utils.element_still_at("More options", "Button", 300, 25, rect=BOX, window="Explorer")


def test_container_of_another_window_is_refused(screen):
    screen.title = "Notepad"
    screen.control = _control("", kind="pane", rect=(0, 0, 800, 600))
    assert utils.spot_on_element("Address", "Edit", 300, 25, rect=BOX, window="Explorer") is None


def test_other_element_in_the_same_rectangle_is_refused(screen):
    # A list scrolled by one row: a different row fills exactly the old row's box.
    screen.control = _control("Row 4", kind="list item", rect=BOX)
    assert utils.spot_on_element("Row 3", "List item", 300, 25, rect=BOX, window="E") is None


def test_covering_window_names_the_other_window(screen):
    screen.title = "Avast"
    assert utils.covering_window(150, 25, "Explorer") == "Avast"
    screen.title = "Explorer"
    assert utils.covering_window(150, 25, "Explorer") == ""


# --- the label lookup uses it ------------------------------------------------------


def _desktop():
    desktop = Desktop.__new__(Desktop)
    desktop.label_tree_state = TreeState(
        interactive_nodes=[
            TreeElementNode(
                bounding_box=BoundingBox(0, 0, 20, 20, 20, 20),
                center=Center(x=10, y=10),
                name="Save",
                control_type="Button",
                window_name="Harness",
            )
        ]
    )
    return desktop


def test_stale_label_is_refused(monkeypatch):
    monkeypatch.setattr(service, "spot_on_element", lambda *a, **k: None)
    monkeypatch.setattr(service, "covering_window", lambda *a: "")
    with pytest.raises(ValueError, match=r"label 0 .*Save.* no longer .*new Snapshot"):
        _desktop().get_coordinates_from_labels([0])


def test_covered_label_names_the_covering_window(monkeypatch):
    monkeypatch.setattr(service, "spot_on_element", lambda *a, **k: None)
    monkeypatch.setattr(service, "covering_window", lambda *a: "Avast")
    with pytest.raises(ValueError, match=r'label 0 .*Save.* covered by "Avast".*"Harness"'):
        _desktop().get_coordinates_from_labels([0])


def test_label_resolves_to_the_free_spot(monkeypatch):
    seen = []
    monkeypatch.setattr(service, "spot_on_element", lambda *a, **k: seen.append((a, k)) or (15, 5))
    assert _desktop().get_coordinates_from_labels([0]) == [(15, 5)]
    assert seen == [(("Save", "Button", 10, 10), {"rect": (0, 0, 20, 20), "window": "Harness"})]
