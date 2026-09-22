"""Round-2 3.3: Type without a location names the focused element and warns."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from windows_mcp.desktop.service import Desktop
from windows_mcp.tools import input as input_tool_module
from windows_mcp.uia import PatternId


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _type(desktop):
    mcp = FakeMCP()
    input_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return lambda **kwargs: asyncio.run(mcp.tools["Type"](**kwargs))


def _focus(name, control_type, accepts_text):
    return {"name": name, "control_type": control_type, "accepts_text": accepts_text}


class TestTypeReplyNamesTheFocus:
    def test_editable_focus_is_named_without_a_warning(self):
        desktop = MagicMock()
        desktop.describe_focused_element.return_value = _focus("Search", "Edit", True)
        reply = _type(desktop)(text="abc")
        assert 'Edit "Search"' in reply
        assert "Warning" not in reply

    def test_button_focus_is_named_and_warned_about(self):
        desktop = MagicMock()
        desktop.describe_focused_element.return_value = _focus("ShowLater", "Button", False)
        reply = _type(desktop)(text="abc")
        assert 'Button "ShowLater"' in reply
        assert "Warning" in reply
        assert "no text" in reply or "takes no text" in reply

    def test_unnamed_element_still_reports_its_type(self):
        desktop = MagicMock()
        desktop.describe_focused_element.return_value = _focus("", "Pane", False)
        reply = _type(desktop)(text="abc")
        assert "Pane" in reply
        assert '""' not in reply

    def test_unknown_focus_falls_back_to_the_plain_reply(self):
        desktop = MagicMock()
        desktop.describe_focused_element.return_value = None
        reply = _type(desktop)(text="abc")
        assert reply == "Typed abc into the focused element."

    def test_a_located_type_is_unchanged_and_does_not_ask_about_focus(self):
        desktop = MagicMock()
        reply = _type(desktop)(text="abc", loc=[5, 6])
        assert reply.startswith("Typed abc at (5,6).")
        desktop.describe_focused_element.assert_not_called()

    def test_text_is_still_typed_when_the_focus_takes_none(self):
        desktop = MagicMock()
        desktop.describe_focused_element.return_value = _focus("OK", "Button", False)
        _type(desktop)(text="abc")
        assert desktop.type.call_args.kwargs["text"] == "abc"


def _desktop():
    with patch.object(Desktop, "__init__", lambda self: None):
        return Desktop()


class FakeControl:
    def __init__(self, name, control_type, patterns, localized=None):
        self.Name = name
        self.ControlTypeName = control_type
        # UIA's localized name is what Snapshot prints ("Button", not "ButtonControl").
        self.LocalizedControlType = control_type.lower() if localized is None else localized
        self._patterns = patterns

    def GetPattern(self, pattern_id):
        return self._patterns.get(pattern_id)


class TestDescribeFocusedElement:
    def test_editable_value_pattern_accepts_text(self):
        control = FakeControl(
            "Search", "Edit", {PatternId.ValuePattern: SimpleNamespace(IsReadOnly=False)}
        )
        with patch("windows_mcp.desktop.service.uia.GetFocusedControl", return_value=control):
            assert _desktop().describe_focused_element() == _focus("Search", "Edit", True)

    def test_read_only_value_pattern_does_not_accept_text(self):
        control = FakeControl(
            "Total", "Text", {PatternId.ValuePattern: SimpleNamespace(IsReadOnly=True)}
        )
        with patch("windows_mcp.desktop.service.uia.GetFocusedControl", return_value=control):
            assert _desktop().describe_focused_element()["accepts_text"] is False

    def test_text_pattern_alone_accepts_text(self):
        control = FakeControl("Body", "Document", {PatternId.TextPattern: object()})
        with patch("windows_mcp.desktop.service.uia.GetFocusedControl", return_value=control):
            assert _desktop().describe_focused_element()["accepts_text"] is True

    def test_control_type_is_the_localized_name_snapshot_prints(self):
        control = FakeControl("OK", "ButtonControl", {}, localized="button")
        with patch("windows_mcp.desktop.service.uia.GetFocusedControl", return_value=control):
            assert _desktop().describe_focused_element()["control_type"] == "Button"

    def test_missing_localized_name_falls_back_to_the_control_type(self):
        control = FakeControl("OK", "ButtonControl", {}, localized="")
        with patch("windows_mcp.desktop.service.uia.GetFocusedControl", return_value=control):
            assert _desktop().describe_focused_element()["control_type"] == "ButtonControl"

    def test_button_accepts_no_text(self):
        control = FakeControl("OK", "Button", {})
        with patch("windows_mcp.desktop.service.uia.GetFocusedControl", return_value=control):
            assert _desktop().describe_focused_element() == _focus("OK", "Button", False)

    @pytest.mark.parametrize("failure", [None, RuntimeError("COM error")])
    def test_no_focus_or_a_com_failure_returns_none(self, failure):
        kwargs = (
            {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": None}
        )
        with patch("windows_mcp.desktop.service.uia.GetFocusedControl", **kwargs):
            assert _desktop().describe_focused_element() is None
