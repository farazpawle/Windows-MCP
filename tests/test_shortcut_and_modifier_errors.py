"""Round-2 3.4 and 3.5: one wording for shortcut errors, and modifier parsing."""

import asyncio
from unittest.mock import MagicMock

import pytest

from windows_mcp.desktop.service import _shortcut_keys
from windows_mcp.tools import input as input_tool_module
from windows_mcp.tools.input import _as_modifiers


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
    input_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return lambda **kwargs: asyncio.run(mcp.tools[name](**kwargs))


# 3.4a - the hold limits are worded the same way everywhere
class TestHoldWording:
    def test_zero_hold_uses_the_same_sentence_as_the_other_limits(self):
        desktop = MagicMock()
        with pytest.raises(ValueError) as e:
            _tool("Shortcut", desktop)(shortcut="a", hold=0)
        assert str(e.value) == "hold must be more than 0 and at most 10 seconds (got 0)"
        desktop.shortcut.assert_not_called()

    def test_too_long_hold_uses_the_same_sentence(self):
        with pytest.raises(ValueError) as e:
            _tool("Shortcut", MagicMock())(shortcut="a", hold=99)
        assert str(e.value) == "hold must be more than 0 and at most 10 seconds (got 99)"

    def test_negative_hold_uses_the_same_sentence(self):
        with pytest.raises(ValueError) as e:
            _tool("Shortcut", MagicMock())(shortcut="a", hold=-1)
        assert str(e.value) == "hold must be more than 0 and at most 10 seconds (got -1)"

    def test_wait_duration_still_allows_zero(self):
        desktop = MagicMock()
        with pytest.raises(ValueError) as e:
            _tool("Wait", desktop)(duration=-1)
        assert str(e.value) == "duration must be 0 or more and at most 300 seconds (got -1)"

    def test_a_valid_hold_still_works(self):
        desktop = MagicMock()
        reply = _tool("Shortcut", desktop)(shortcut="a", hold=2)
        desktop.shortcut.assert_called_once_with("a", repeat=1, hold=2.0)
        assert "2 seconds" in reply


# 3.4b - an empty shortcut says so
@pytest.mark.parametrize("shortcut", ["", "   ", "	"])
def test_empty_shortcut_says_it_is_empty(shortcut):
    with pytest.raises(ValueError, match="shortcut is empty"):
        _shortcut_keys(shortcut)


# 3.4c - one message for an unknown key, on both the press and the hold path
class TestUnknownKeyWording:
    @pytest.mark.parametrize("shortcut", ["bogus", "ctrl+bogus"])
    def test_unknown_key_is_refused_before_anything_is_sent(self, shortcut):
        with pytest.raises(ValueError) as e:
            _shortcut_keys(shortcut)
        assert str(e.value) == "Unknown key 'bogus'"

    @pytest.mark.parametrize("hold", [None, 2])
    def test_both_paths_give_the_same_message(self, hold):
        desktop = MagicMock()
        desktop.shortcut.side_effect = lambda s, **kw: _shortcut_keys(s)
        with pytest.raises(ValueError) as e:
            _tool("Shortcut", desktop)(shortcut="ctrl+bogus", hold=hold)
        assert str(e.value) == "Unknown key 'bogus'"

    # The up-front resolution must not start refusing shortcuts that worked before.
    @pytest.mark.parametrize(
        "shortcut",
        [
            "ctrl+c",
            "ctrl+v",
            "ctrl+z",
            "ctrl+s",
            "alt+tab",
            "alt+f4",
            "win+r",
            "win",
            "ctrl+shift+esc",
            "f1",
            "f5",
            "f12",
            "enter",
            "tab",
            "esc",
            "escape",
            "space",
            "backspace",
            "delete",
            "del",
            "up",
            "down",
            "home",
            "end",
            "pageup",
            "pagedown",
            "insert",
            "shift+tab",
            "ctrl++",
            "ctrl+plus",
            "ctrl+minus",
            "+",
            "a",
            "1",
            "ctrl+comma",
            "ctrl+slash",
            "ctrl+bracketleft",
            "ctrl+alt+delete",
        ],
    )
    def test_known_shortcuts_still_parse(self, shortcut):
        assert _shortcut_keys(shortcut)


# 3.5a - commas and spaces separate modifiers
class TestModifierSeparators:
    @pytest.mark.parametrize(
        "value",
        ["ctrl+shift", "ctrl, shift", "ctrl shift", "ctrl,shift", " ctrl , shift ", "ctrl+ shift"],
    )
    def test_separators_all_parse(self, value):
        assert _as_modifiers(value) == ["ctrl", "shift"]

    def test_lists_still_parse(self):
        assert _as_modifiers(["ctrl", "shift"]) == ["ctrl", "shift"]

    def test_json_list_strings_still_parse(self):
        assert _as_modifiers('["ctrl", "shift"]') == ["ctrl", "shift"]

    def test_aliases_still_parse(self):
        assert _as_modifiers("control, windows") == ["ctrl", "win"]

    def test_empty_stays_empty(self):
        assert _as_modifiers(None) == [] and _as_modifiers("") == []


# 3.5c - the error names only the bad token
class TestModifierErrors:
    @pytest.mark.parametrize("value", ["ctrl+bogus", "ctrl, bogus", "bogus shift"])
    def test_only_the_bad_token_is_named(self, value):
        with pytest.raises(ValueError) as e:
            _as_modifiers(value)
        assert "'bogus'" in str(e.value)
        assert value not in str(e.value)


# 3.5b - the aliases are documented on the tools that take modifiers
@pytest.mark.parametrize("name", ["Click", "Scroll"])
def test_modifier_aliases_are_documented(name):
    mcp = FakeMCP()
    descriptions = {}

    def tool(*, name, description="", **kwargs):
        descriptions[name] = description
        return lambda func: func

    mcp.tool = tool
    input_tool_module.register(mcp, get_desktop=MagicMock, get_analytics=lambda: None)
    text = descriptions[name].lower()
    assert "control" in text and "windows" in text
