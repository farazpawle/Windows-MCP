"""Round-2 B.10: Click, Type and Scroll replies report what was really there."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from windows_mcp.tools import input as input_tools
from windows_mcp.tree import utils

VALUE = utils.uia.PatternId.ValuePattern
SCROLL = utils.uia.PatternId.ScrollPattern


def _control(name="", kind="button", parent=None, patterns=None, password=False):
    patterns = patterns or {}
    return SimpleNamespace(
        Name=name,
        LocalizedControlType=kind,
        ControlTypeName=kind.title().replace(" ", "") + "Control",
        IsPassword=password,
        GetParentControl=lambda: parent,
        GetPattern=lambda pattern_id: patterns.get(pattern_id),
    )


def _scroller(vertical=None, horizontal=None):
    return SimpleNamespace(
        VerticallyScrollable=vertical is not None,
        VerticalScrollPercent=vertical if vertical is not None else -1,
        HorizontallyScrollable=horizontal is not None,
        HorizontalScrollPercent=horizontal if horizontal is not None else -1,
    )


@pytest.fixture
def screen(monkeypatch):
    """A readable "Notepad" window everywhere; set .control / .focused for what UIA finds."""
    state = SimpleNamespace(control=None, focused=None, window=5, hung=False, unreadable=False)
    reads = MagicMock(side_effect=lambda x, y: state.control)
    monkeypatch.setattr(utils, "top_level_window_at", lambda x, y: state.window)
    monkeypatch.setattr(utils.win32gui, "GetForegroundWindow", lambda: state.window)
    monkeypatch.setattr(utils.win32gui, "GetWindowText", lambda h: "Notepad")
    monkeypatch.setattr(utils, "is_window_hung", lambda h: state.hung)
    monkeypatch.setattr(utils, "is_unreadable_window", lambda h: state.unreadable)
    monkeypatch.setattr(utils.uia, "ControlFromPoint", reads)
    monkeypatch.setattr(utils.uia, "GetFocusedControl", lambda: state.focused)
    state.reads = reads
    return state


# --- describe_point --------------------------------------------------------------------


def test_names_the_element_and_window(screen):
    screen.control = _control("Save")
    assert utils.describe_point(1, 2) == 'button "Save" in "Notepad"'


def test_an_unnamed_hit_takes_its_named_parent(screen):
    screen.control = _control("", kind="text", parent=_control("Save"))
    assert utils.describe_point(1, 2) == 'button "Save" in "Notepad"'


@pytest.mark.parametrize("attr", ["hung", "unreadable"])
def test_hung_or_unreadable_window_is_named_not_read(screen, attr):
    setattr(screen, attr, True)
    assert utils.describe_point(1, 2) == 'in "Notepad" (not read)'
    screen.reads.assert_not_called()


def test_an_unnamed_field_is_not_renamed_after_its_window(screen):
    screen.control = _control("", kind="edit", parent=_control("LiveTest", kind="window"))
    assert utils.describe_point(1, 2) == 'edit in "Notepad"'


def test_nothing_at_the_point(screen):
    screen.window = 0
    assert utils.describe_point(1, 2) == ""


def test_uia_error_still_names_the_window(screen):
    screen.reads.side_effect = OSError("COM")
    assert utils.describe_point(1, 2) == 'in "Notepad"'


# --- focused_value -------------------------------------------------------------------


def test_reports_the_field_value(screen):
    value = SimpleNamespace(Value="hello")
    screen.focused = _control("Search", kind="edit", patterns={VALUE: value})
    assert utils.focused_value() == ' The field (edit "Search") now reads "hello".'


def test_password_contents_are_never_shown(screen):
    value = SimpleNamespace(Value="hunter2")
    screen.focused = _control("Password", kind="edit", patterns={VALUE: value}, password=True)
    reply = utils.focused_value()
    assert "hunter2" not in reply
    assert "password box; its contents are not shown" in reply


def test_long_value_is_shortened(screen):
    value = SimpleNamespace(Value="x" * 500)
    screen.focused = _control("Body", kind="edit", patterns={VALUE: value})
    reply = utils.focused_value()
    assert len(reply) < 200 and "(500 characters)" in reply


def test_unnamed_field_value(screen):
    screen.focused = _control("", kind="edit", patterns={VALUE: SimpleNamespace(Value="hi")})
    assert utils.focused_value() == ' The field (edit) now reads "hi".'


def test_no_value_pattern_says_nothing(screen):
    screen.focused = _control("Canvas", kind="pane")
    assert utils.focused_value() == ""


def test_unreadable_foreground_is_not_read(screen):
    screen.unreadable = True
    screen.focused = MagicMock(side_effect=AssertionError("read"))
    assert utils.focused_value() == ""


# --- scroll_position -----------------------------------------------------------------


def test_finds_the_scrolling_parent(screen):
    lst = _control("Files", kind="list", patterns={SCROLL: _scroller(vertical=45.0)})
    screen.control = _control("row 3", kind="list item", parent=lst)
    assert utils.scroll_position(1, 2, "vertical") == ('list "Files"', 45.0)


def test_horizontal_uses_the_horizontal_percent(screen):
    pane = _control(
        "Sheet", kind="pane", patterns={SCROLL: _scroller(vertical=10.0, horizontal=70.0)}
    )
    screen.control = pane
    assert utils.scroll_position(1, 2, "horizontal") == ('pane "Sheet"', 70.0)


def test_nothing_scrollable_is_none(screen):
    screen.control = _control("OK")
    assert utils.scroll_position(1, 2, "vertical") is None


def test_unreadable_window_scroll_is_not_read(screen):
    screen.unreadable = True
    assert utils.scroll_position(1, 2, "vertical") is None
    screen.reads.assert_not_called()


# --- the tools use them --------------------------------------------------------------


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


def test_click_names_what_it_clicked_before_clicking(monkeypatch):
    order = []
    desktop = MagicMock()
    desktop.click.side_effect = lambda **kw: order.append("click")
    monkeypatch.setattr(
        input_tools,
        "describe_point",
        lambda x, y: order.append("read") or 'button "Save" in "Notepad"',
    )
    reply = _tool("Click", desktop)(loc=[5, 6])
    assert 'clicked button "Save" in "Notepad" at (5,6)' in reply
    assert order == ["read", "click"]


def test_type_reports_the_field_afterwards(monkeypatch):
    monkeypatch.setattr(
        input_tools, "focused_value", lambda: ' The field (edit "Search") now reads "hi".'
    )
    reply = _tool("Type", MagicMock())(text="hi", loc=[5, 6])
    assert reply.endswith('The field (edit "Search") now reads "hi".')


def _readings(monkeypatch, name, values, *args):
    """Make input_tools.<name> return *values* in turn, then keep the last one."""
    values = list(values)
    monkeypatch.setattr(input_tools, "_SETTLE_GAP", 0.001)
    monkeypatch.setattr(
        input_tools, name, lambda *a: values.pop(0) if len(values) > 1 else values[0]
    )


def test_scroll_reports_before_and_after(monkeypatch):
    _readings(monkeypatch, "scroll_position", [('list "Files"', 30.0), ('list "Files"', 45.0)])
    desktop = MagicMock()
    desktop.scroll.return_value = None
    reply = _tool("Scroll", desktop)(loc=[5, 6])
    assert reply.endswith('list "Files" is now at 45% (was 30%).')


def test_scroll_reports_the_position_once_it_settles(monkeypatch):
    # Round-4 R4-7: "now at 87.3%" while the next call found "was 100%".
    doc = 'document "Text editor"'
    _readings(monkeypatch, "scroll_position", [(doc, 62.0), (doc, 87.3), (doc, 96.0), (doc, 100.0)])
    desktop = MagicMock()
    desktop.scroll.return_value = None
    reply = _tool("Scroll", desktop)(loc=[5, 6])
    assert reply.endswith(f"{doc} is now at 100% (was 62%).")


def test_type_reports_the_field_once_it_settles(monkeypatch):
    # Round-4 R4-7: "(213 characters)" while Notepad went on to hold 215.
    _readings(
        monkeypatch, "focused_value", [" 213 characters.", " 214 characters.", " 215 characters."]
    )
    reply = _tool("Type", MagicMock())(text="hi", loc=[5, 6])
    assert reply.endswith(" 215 characters.")


def test_a_reading_that_never_settles_stops_at_the_cap(monkeypatch):
    count = iter(range(10**6))
    monkeypatch.setattr(input_tools, "_SETTLE_GAP", 0.01)
    started = input_tools.time.monotonic()
    assert input_tools._settled(lambda: next(count)) > 0
    assert input_tools.time.monotonic() - started < input_tools._SETTLE_CAP + 0.1


def test_scroll_says_when_the_position_is_unknown(monkeypatch):
    monkeypatch.setattr(input_tools, "scroll_position", lambda x, y, axis: None)
    desktop = MagicMock()
    desktop.scroll.return_value = None
    reply = _tool("Scroll", desktop)(loc=[5, 6])
    assert reply.endswith("The scroll position could not be read.")
