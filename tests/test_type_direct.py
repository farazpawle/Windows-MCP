"""Round-2 2.14: long text is typed as Unicode key events and never touches the clipboard.

Pasting through the clipboard restored only text, so an image or copied files were lost.
"""

from unittest.mock import MagicMock, patch

import pytest

import windows_mcp.uia as uia
import windows_mcp.uia.core as core
from windows_mcp.desktop.service import Desktop

LONG = "hello from windows-mcp drive test, 46 chars.."


def test_long_text_is_typed_without_the_clipboard():
    typed = MagicMock()
    clipboard = MagicMock(side_effect=AssertionError("clipboard touched"))
    with (
        patch.object(uia, "SendUnicodeText", typed, create=True),
        patch.object(uia, "SetClipboardText", clipboard),
        patch.object(uia, "GetClipboardText", clipboard),
        patch.object(uia, "SendKeys"),
    ):
        Desktop.__new__(Desktop).type(None, LONG)
    typed.assert_called_once_with(LONG)


@pytest.mark.parametrize("text", ["hello", "a+b^c%~"])
def test_short_plain_text_is_typed_as_unicode(text):
    # Round-3 R3-I2: per-key SendKeys made 10 characters slower than 60.
    typed, keys = MagicMock(), MagicMock()
    with patch.object(uia, "SendUnicodeText", typed), patch.object(uia, "SendKeys", keys):
        Desktop.__new__(Desktop).type(None, text)
    typed.assert_called_once_with(text)
    keys.assert_not_called()


def test_text_with_line_breaks_still_uses_sendkeys():
    typed, keys = MagicMock(), MagicMock()
    with patch.object(uia, "SendUnicodeText", typed), patch.object(uia, "SendKeys", keys):
        Desktop.__new__(Desktop).type(None, "a\nb")
    typed.assert_not_called()
    keys.assert_called_once()


@pytest.fixture
def batches(monkeypatch):
    sent = []

    def send(inputs):
        sent.append([(i.union.ki.wScan, i.union.ki.dwFlags) for i in inputs])
        return len(inputs)

    monkeypatch.setattr(core, "_send_inputs", send, raising=False)
    monkeypatch.setattr(core.time, "sleep", lambda s: None)
    return sent


def test_text_goes_out_in_chunks_with_surrogate_pairs_kept_together(batches):
    core.SendUnicodeText("a\U0001f600b", chunkSize=2)
    down, up = core.KeyboardEventFlag.KeyUnicode, core.KeyboardEventFlag.KeyUnicode | 2
    assert batches == [
        [(0x61, down), (0x61, up), (0xD83D, down), (0xD83D, up), (0xDE00, down), (0xDE00, up)],
        [(0x62, down), (0x62, up)],
    ]


def test_blocked_input_is_an_error(monkeypatch):
    monkeypatch.setattr(core, "_send_inputs", lambda inputs: 0, raising=False)
    with pytest.raises(OSError, match="blocked"):
        core.SendUnicodeText("abc")
