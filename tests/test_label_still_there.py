"""Round-2 B.9: a label is refused when its element is no longer at its spot."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from windows_mcp.desktop import service
from windows_mcp.desktop.service import Desktop
from windows_mcp.tree import utils
from windows_mcp.tree.views import BoundingBox, Center, TreeElementNode, TreeState


def _control(name="", automation_id="", kind="button", parent=None):
    return SimpleNamespace(
        Name=name,
        AutomationId=automation_id,
        LocalizedControlType=kind,
        GetParentControl=lambda: parent,
    )


@pytest.fixture
def screen(monkeypatch):
    """A readable window at every point; set .control to what UIA finds there."""
    state = SimpleNamespace(control=None, window=5, hung=False, unreadable=False)
    reads = MagicMock(side_effect=lambda x, y: state.control)
    monkeypatch.setattr(utils, "top_level_window_at", lambda x, y: state.window)
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
    monkeypatch.setattr(service, "element_still_at", lambda *a: False)
    with pytest.raises(ValueError, match=r"label 0 .*Save.* no longer .*new Snapshot"):
        _desktop().get_coordinates_from_labels([0])


def test_label_still_there_resolves(monkeypatch):
    seen = []
    monkeypatch.setattr(service, "element_still_at", lambda *a: seen.append(a) or True)
    assert _desktop().get_coordinates_from_labels([0]) == [(10, 10)]
    assert seen == [("Save", "Button", 10, 10)]
