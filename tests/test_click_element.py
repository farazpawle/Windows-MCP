"""Round-2 C.5: Click element="button:Save" finds the element by name at click time."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from windows_mcp.tools import input as input_tools
from windows_mcp.tree import utils

SAVE = ("button", "Save", 10, 20)
SAVE_AS = ("button", "Save As...", 30, 20)
MENU_SAVE = ("menu item", "Save", 50, 5)


# --- pick_element (pure) ---------------------------------------------------------------


def test_exact_name_wins_over_partial():
    assert utils.pick_element([SAVE_AS, SAVE], "", "save", "Notepad") == SAVE


def test_one_partial_match_is_taken():
    assert utils.pick_element([SAVE_AS], "button", "save as", "Notepad") == SAVE_AS


def test_several_partial_matches_are_refused_with_candidates():
    with pytest.raises(ValueError) as e:
        utils.pick_element([SAVE_AS, ("button", "Save All", 1, 1)], "", "sav", "Notepad")
    assert 'button "Save As..."' in str(e.value) and 'button "Save All"' in str(e.value)


def test_several_exact_matches_are_refused():
    with pytest.raises(ValueError, match="2 elements"):
        utils.pick_element([SAVE, MENU_SAVE], "", "Save", "Notepad")


COPY_A = ("menu item", "Copy as path", 100, 200)
COPY_B = ("menu item", "Copy as path", 100, 900)


def test_identical_duplicates_pick_the_one_on_top():
    # R3-5: Explorer's context menu lists "Copy as path" twice; only one is shown.
    shown = {COPY_B}
    assert (
        utils.pick_element([COPY_A, COPY_B], "", "Copy as path", "Menu", shown.__contains__)
        == COPY_B
    )


def test_identical_duplicates_at_the_same_spot_are_one_target():
    # Measured live: Explorer reports the one "Copy as path" item twice, same box.
    twin = ("menu item", "Copy as path", 100, 200)
    assert utils.pick_element([COPY_A, twin], "", "Copy as path", "Menu", lambda f: True) == COPY_A


def test_identical_duplicates_both_shown_are_refused():
    with pytest.raises(ValueError, match="2 elements"):
        utils.pick_element([COPY_A, COPY_B], "", "Copy as path", "Menu", lambda f: True)


def test_partial_matches_are_not_narrowed_by_visibility():
    # "sav" matching a hidden "Save As..." and a shown "Save" must not quietly pick one.
    with pytest.raises(ValueError, match="2 elements"):
        utils.pick_element([SAVE_AS, SAVE], "", "sav", "Notepad", {SAVE}.__contains__)


def test_the_type_narrows_the_choice():
    assert utils.pick_element([SAVE, MENU_SAVE], "Menu Item", "Save", "Notepad") == MENU_SAVE


def test_wrong_type_lists_what_has_that_name():
    with pytest.raises(ValueError) as e:
        utils.pick_element([MENU_SAVE], "button", "Save", "Notepad")
    assert 'No button named "Save" in "Notepad"' in str(e.value)
    assert 'menu item "Save"' in str(e.value)


def test_nothing_found():
    with pytest.raises(ValueError, match='No element named "Print" in "Notepad"'):
        utils.pick_element([], "", "Print", "Notepad")


# --- find_element (reads the window) ---------------------------------------------------


def _element(name, kind="button", rect=(0, 0, 20, 40), offscreen=False):
    left, top, right, bottom = rect
    return SimpleNamespace(
        CurrentName=name,
        CurrentLocalizedControlType=kind,
        CurrentBoundingRectangle=SimpleNamespace(left=left, top=top, right=right, bottom=bottom),
        CurrentIsOffscreen=offscreen,
    )


@pytest.fixture
def window(monkeypatch):
    """A readable window whose name search returns .elements; the spot check passes."""
    state = SimpleNamespace(elements=[], readable=True, still_at=True, cover="", searched=[])

    def find_all(scope, condition):
        return SimpleNamespace(Length=len(state.elements), GetElement=lambda i: state.elements[i])

    def create_condition(prop, text, flags):
        state.searched.append(text)
        return text

    ia = SimpleNamespace(
        CreatePropertyConditionEx=create_condition,
        ElementFromHandle=lambda h: SimpleNamespace(FindAll=find_all),
    )
    monkeypatch.setattr(
        utils.uia.core._AutomationClient, "instance", lambda: SimpleNamespace(IUIAutomation=ia)
    )
    monkeypatch.setattr(utils, "_readable_window", lambda h: state.readable)
    monkeypatch.setattr(
        utils, "spot_on_element", lambda n, k, x, y, **kw: (x, y) if state.still_at else None
    )
    monkeypatch.setattr(utils, "covering_window", lambda *a: state.cover)
    return state


def test_finds_by_type_and_name_and_returns_the_centre(window):
    window.elements = [_element("Save", rect=(100, 200, 140, 220)), _element("Save", "menu item")]
    assert utils.find_element(1, "Notepad", "button:Save") == ("button", "Save", 120, 210)
    assert window.searched == ["Save"]


def test_without_a_type_any_element_matches(window):
    window.elements = [_element("OK", rect=(0, 0, 10, 10))]
    assert utils.find_element(1, "Notepad", "OK") == ("button", "OK", 5, 5)


def test_hidden_and_zero_size_elements_are_ignored(window):
    window.elements = [
        _element("Save", offscreen=True),
        _element("Save", rect=(5, 5, 5, 5)),
        _element("Save", rect=(0, 0, 10, 10)),
    ]
    assert utils.find_element(1, "Notepad", "Save")[2:] == (5, 5)


def test_unreadable_window_is_refused_unread(window):
    window.readable = False
    with pytest.raises(ValueError, match="cannot be read"):
        utils.find_element(1, "Code", "Save")
    assert window.searched == []


def test_a_covered_element_is_refused_naming_the_cover(window):
    window.elements = [_element("Save")]
    window.still_at = False
    window.cover = "Avast"
    with pytest.raises(ValueError, match='covered by "Avast"; bring "Notepad" to the front'):
        utils.find_element(1, "Notepad", "Save")


def test_something_else_at_the_spot_in_the_same_window_is_not_called_covered(window):
    window.elements = [_element("Save")]
    window.still_at = False
    with pytest.raises(ValueError, match="something else of .*Notepad") as e:
        utils.find_element(1, "Notepad", "Save")
    assert "covered" not in str(e.value)


def test_a_free_spot_replaces_a_covered_centre(window, monkeypatch):
    window.elements = [_element("Address", "edit", rect=(100, 10, 500, 40))]
    monkeypatch.setattr(utils, "spot_on_element", lambda *a, **k: (460, 25))
    assert utils.find_element(1, "Explorer", "edit:Address") == ("edit", "Address", 460, 25)


def test_empty_name_is_refused(window):
    with pytest.raises(ValueError, match="name"):
        utils.find_element(1, "Notepad", "button:")


# --- the Click tool --------------------------------------------------------------------


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _click(desktop, **kw):
    mcp = FakeMCP()
    input_tools.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return asyncio.run(mcp.tools["Click"](**kw))


def _desktop():
    desktop = MagicMock()
    desktop.pick_window.return_value = (SimpleNamespace(handle=7, name="Notepad"), "")
    desktop.release_held_button.return_value = False
    return desktop


def test_click_element_clicks_the_found_point(monkeypatch):
    found = MagicMock(return_value=("button", "Save", 120, 210))
    monkeypatch.setattr(input_tools, "find_element", found)
    desktop = _desktop()
    reply = _click(desktop, element="button:Save", window="Note")
    desktop.pick_window.assert_called_once_with("Note", None)
    found.assert_called_once_with(7, "Notepad", "button:Save")
    assert desktop.click.call_args.kwargs["loc"] == [120, 210]
    assert "at (120,210)" in reply


def test_click_element_defaults_to_the_front_window(monkeypatch):
    monkeypatch.setattr(input_tools, "find_element", lambda *a: ("button", "OK", 1, 2))
    desktop = _desktop()
    _click(desktop, element="OK")
    desktop.pick_window.assert_called_once_with(None, None)


@pytest.mark.parametrize("extra", [{"loc": [1, 2]}, {"label": 3}])
def test_element_with_loc_or_label_is_refused(extra):
    desktop = _desktop()
    with pytest.raises(ValueError, match="only one"):
        _click(desktop, element="OK", **extra)
    desktop.click.assert_not_called()


def test_window_without_element_is_refused():
    desktop = _desktop()
    with pytest.raises(ValueError, match="window"):
        _click(desktop, loc=[1, 2], window="Notepad")
    desktop.click.assert_not_called()
