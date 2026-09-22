"""Round-2 2.15: the plus key, punctuation names and literal braces in Shortcut."""

from unittest.mock import patch

import pytest

import windows_mcp.uia as uia
from windows_mcp.desktop.service import Desktop


def _sent(shortcut: str) -> str:
    with patch.object(uia, "SendKeys") as send:
        Desktop.__new__(Desktop).shortcut(shortcut)
    return send.call_args.args[0]


@pytest.mark.parametrize(
    ("shortcut", "keys"),
    [
        # "+" is not a SendKeys character code, so Ctrl would not combine with it;
        # the "=/+" key (OEM_PLUS) is what browsers read as zoom in.
        ("ctrl++", "{ctrl}{OEM_PLUS}"),
        ("ctrl+plus", "{ctrl}{OEM_PLUS}"),
        ("ctrl+Plus", "{ctrl}{OEM_PLUS}"),
        ("+", "+"),  # alone it types the character
        ("{", "{{}"),
        ("}", "{}}"),
        ("ctrl+minus", "{ctrl}-"),
        ("ctrl+equal", "{ctrl}="),
        ("shift+braceleft", "{shift}{{}"),
        ("ctrl+a", "{ctrl}a"),
    ],
)
def test_shortcut_maps_to_valid_sendkeys(shortcut, keys):
    assert _sent(shortcut) == keys


@pytest.mark.parametrize("shortcut", ["", "  "])
def test_empty_shortcut_is_refused(shortcut):
    with pytest.raises(ValueError, match="empty"):
        _sent(shortcut)
