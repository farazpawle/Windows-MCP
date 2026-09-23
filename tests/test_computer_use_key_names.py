"""Round-2 3.24 / B.3: xdotool-style key names that computer-use models send."""

from unittest.mock import patch

import pytest

import windows_mcp.uia as uia
from windows_mcp.desktop.service import Desktop, _virtual_key
from windows_mcp.tools.input import _as_modifiers


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("Page_Down", uia.Keys.VK_NEXT),
        ("Page_Up", uia.Keys.VK_PRIOR),
        ("KP_Enter", uia.Keys.VK_RETURN),
        ("KP_Add", uia.Keys.VK_ADD),
        ("KP_Subtract", uia.Keys.VK_SUBTRACT),
        ("KP_Multiply", uia.Keys.VK_MULTIPLY),
        ("KP_Divide", uia.Keys.VK_DIVIDE),
        ("KP_Decimal", uia.Keys.VK_DECIMAL),
        ("KP_5", uia.Keys.VK_NUMPAD5),
        ("super", uia.Keys.VK_LWIN),
        ("Super_L", uia.Keys.VK_LWIN),
        ("cmd", uia.Keys.VK_LWIN),
        ("meta", uia.Keys.VK_LWIN),
        ("Control_L", uia.Keys.VK_LCONTROL),
        ("Shift_R", uia.Keys.VK_RSHIFT),
        ("Alt_L", uia.Keys.VK_LMENU),
        ("Caps_Lock", uia.Keys.VK_CAPITAL),
        ("Num_Lock", uia.Keys.VK_NUMLOCK),
        ("Menu", uia.Keys.VK_APPS),
        # names that already worked keep working
        ("Return", uia.Keys.VK_RETURN),
        ("BackSpace", uia.Keys.VK_BACK),
        ("pagedown", uia.Keys.VK_NEXT),
        ("browser_back", uia.Keys.VK_BROWSER_BACK),
    ],
)
def test_alias_resolves(name, code):
    assert _virtual_key(name) == code


def _sent(shortcut: str) -> str:
    with patch.object(uia, "SendKeys") as send:
        Desktop.__new__(Desktop).shortcut(shortcut)
    return send.call_args.args[0]


@pytest.mark.parametrize(
    ("shortcut", "keys"),
    [
        ("Page_Down", "{pagedown}"),
        ("KP_Enter", "{enter}"),
        ("super+e", "{Win}e"),
        ("ctrl+KP_Add", "{ctrl}{add}"),
    ],
)
def test_shortcut_sends_the_resolved_key(shortcut, keys):
    assert _sent(shortcut) == keys


def test_unknown_key_is_still_refused():
    with pytest.raises(ValueError, match="Unknown key"):
        _sent("Page_Sideways")


@pytest.mark.parametrize(
    ("value", "names"),
    [
        ("super", ["win"]),
        ("cmd+shift", ["win", "shift"]),
        ("meta", ["win"]),
        ("command", ["win"]),
        ("option", ["alt"]),
        ("Control_L", ["ctrl"]),
    ],
)
def test_modifier_aliases(value, names):
    assert _as_modifiers(value) == names
