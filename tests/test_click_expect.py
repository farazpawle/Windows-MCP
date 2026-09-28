"""R6-3: Click/Type by position refuse when the element there is not the expected one."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from windows_mcp.tools import input as input_tools
from windows_mcp.tree import utils


def _control(name="", kind="button", parent=None):
    return SimpleNamespace(
        Name=name,
        LocalizedControlType=kind,
        ControlTypeName=kind.title().replace(" ", "") + "Control",
        GetParentControl=lambda: parent,
    )


@pytest.fixture
def screen(monkeypatch):
    """A readable "Notepad" window everywhere; set .control for what UIA finds."""
    state = SimpleNamespace(control=None, window=5, hung=False, unreadable=False)
    reads = MagicMock(side_effect=lambda x, y: state.control)
    monkeypatch.setattr(utils, "top_level_window_at", lambda x, y: state.window)
    monkeypatch.setattr(utils.win32gui, "GetWindowText", lambda h: "Notepad")
    monkeypatch.setattr(utils, "is_window_hung", lambda h: state.hung)
    monkeypatch.setattr(utils, "is_unreadable_window", lambda h: state.unreadable)
    monkeypatch.setattr(utils.uia, "ControlFromPoint", reads)
    state.reads = reads
    return state


# --- expect_at -------------------------------------------------------------------------


def test_the_element_itself_matches(screen):
    screen.control = _control("Save")
    assert utils.expect_at(1, 2, "save") is None


def test_a_third_ancestor_matches(screen):
    # A click on a button's text hits a Text child, sometimes nested deeper.
    button = _control("Save file", parent=_control("Toolbar", kind="tool bar"))
    screen.control = _control("", "text", _control("", "image", _control("", "group", button)))
    assert utils.expect_at(1, 2, "SAVE") is None


def test_a_fourth_ancestor_is_too_far(screen):
    far = _control("Save")
    screen.control = _control(
        "", "text", _control("", "text", _control("", "text", _control("", "text", far)))
    )
    assert utils.expect_at(1, 2, "Save") is not None


def test_something_else_is_named(screen):
    screen.control = _control("Don't save")
    reason = utils.expect_at(1, 2, "Cancel")
    assert reason == 'found button "Don\'t save" in "Notepad"'


def test_nothing_at_the_point(screen):
    screen.window = 0
    assert utils.expect_at(1, 2, "Save") == "nothing is there"


@pytest.mark.parametrize("attr", ["hung", "unreadable"])
def test_hung_or_vscode_window_refuses_unread(screen, attr):
    setattr(screen, attr, True)
    reason = utils.expect_at(1, 2, "Save")
    assert reason.startswith('the window there ("Notepad") is not read')
    screen.reads.assert_not_called()


def test_a_uia_error_refuses(screen):
    screen.reads.side_effect = OSError("COM")
    assert utils.expect_at(1, 2, "Save") == 'the element there could not be read (in "Notepad")'


# --- the tools ---------------------------------------------------------------------------


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _tool(name, desktop):
    mcp = FakeMCP()
    input_tools.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return lambda **kw: asyncio.run(mcp.tools[name](**kw))


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(input_tools, "describe_point", lambda x, y: 'button "Save" in "Notepad"')
    monkeypatch.setattr(input_tools, "focused_value", lambda typed: "")


def test_click_with_a_matching_expect_clicks(monkeypatch, quiet):
    monkeypatch.setattr(input_tools, "expect_at", lambda x, y, expect: None)
    desktop = MagicMock()
    reply = _tool("Click", desktop)(loc=[5, 6], expect="Save")
    desktop.click.assert_called_once()
    assert 'clicked button "Save" in "Notepad" at (5,6)' in reply


def test_click_with_something_else_there_refuses_without_clicking(monkeypatch, quiet):
    monkeypatch.setattr(
        input_tools, "expect_at", lambda x, y, expect: 'found button "Cancel" in "Notepad"'
    )
    desktop = MagicMock()
    with pytest.raises(ValueError) as err:
        _tool("Click", desktop)(loc=[5, 6], expect="Save")
    desktop.click.assert_not_called()
    assert 'Not clicked: expected "Save" at (5,6) but found button "Cancel"' in str(err.value)


def test_click_without_expect_does_not_check(monkeypatch, quiet):
    monkeypatch.setattr(input_tools, "expect_at", MagicMock(side_effect=AssertionError("read")))
    desktop = MagicMock()
    _tool("Click", desktop)(loc=[5, 6])
    desktop.click.assert_called_once()


def test_blank_expect_is_refused(quiet):
    with pytest.raises(ValueError, match="expect"):
        _tool("Click", MagicMock())(loc=[5, 6], expect="  ")


def test_type_with_something_else_there_refuses_without_typing(monkeypatch, quiet):
    monkeypatch.setattr(input_tools, "expect_at", lambda x, y, expect: "nothing is there")
    desktop = MagicMock()
    with pytest.raises(ValueError) as err:
        _tool("Type", desktop)(text="hi", loc=[5, 6], expect="Search")
    desktop.type.assert_not_called()
    assert 'Not typed: expected "Search" at (5,6) but nothing is there' in str(err.value)


def test_type_with_a_matching_expect_types(monkeypatch, quiet):
    monkeypatch.setattr(input_tools, "expect_at", lambda x, y, expect: None)
    desktop = MagicMock()
    _tool("Type", desktop)(text="hi", loc=[5, 6], expect="Search")
    desktop.type.assert_called_once()


def test_type_expect_needs_a_point(quiet):
    desktop = MagicMock()
    with pytest.raises(ValueError, match="expect needs loc or label"):
        _tool("Type", desktop)(text="hi", expect="Search")
    desktop.type.assert_not_called()
