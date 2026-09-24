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


def _typed_sequence(text):
    """Type *text* and return the calls in order: ("text", run) or ("key", keys)."""
    calls = []
    with (
        patch.object(uia, "SendUnicodeText", lambda t, *a, **k: calls.append(("text", t))),
        patch.object(uia, "SendKeys", lambda keys, *a, **k: calls.append(("key", keys))),
    ):
        Desktop.__new__(Desktop).type(None, text)
    return calls


def test_multi_line_text_goes_as_unicode_runs_with_enter_between():
    # Round-4 R4-1: per-key SendKeys at 0.04 s a key took 26 s for 622 characters.
    assert _typed_sequence("one\ntwo\tthree\n") == [
        ("text", "one"),
        ("key", "{Enter}"),
        ("text", "two"),
        ("key", "{Tab}"),
        ("text", "three"),
        ("key", "{Enter}"),
    ]


def test_braces_are_typed_literally_as_unicode():
    assert _typed_sequence("{x}\n{Enter}") == [
        ("text", "{x}"),
        ("key", "{Enter}"),
        ("text", "{Enter}"),
    ]


def test_crlf_is_one_line_break():
    assert _typed_sequence("a\r\nb\r\n\r\nc") == [
        ("text", "a"),
        ("key", "{Enter}"),
        ("text", "b"),
        ("key", "{Enter}"),
        ("key", "{Enter}"),
        ("text", "c"),
    ]


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
