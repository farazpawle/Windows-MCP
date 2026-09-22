"""Keyboard and clipboard input edge cases found by live testing on 2026-09-22."""

import ctypes
from types import SimpleNamespace

import pytest

from windows_mcp.uia import core


@pytest.fixture
def sent(monkeypatch):
    """Capture SendInput scans and keybd_event calls instead of touching the real keyboard."""
    log = {"unicode": [], "vk": []}

    def fake_send_input(*inputs):
        keys = [i.union.ki for i in inputs]
        log["unicode"].extend(
            k.wScan for k in keys if k.dwFlags & core.KeyboardEventFlag.KeyUnicode
        )
        return len(inputs)

    monkeypatch.setattr(core, "SendInput", fake_send_input)
    monkeypatch.setattr(core, "keybd_event", lambda vk, *a: log["vk"].append(vk))
    monkeypatch.setattr(core.time, "sleep", lambda s: None)
    return log


def test_astral_char_sent_as_surrogate_pair(sent):
    core.SendUnicodeChar("\U0001f600")
    # Key down + key up for each UTF-16 unit.
    assert sent["unicode"] == [0xD83D, 0xD83D, 0xDE00, 0xDE00]


def test_empty_text_is_a_no_op(sent):
    core.SendKeys("", waitTime=0)
    assert sent == {"unicode": [], "vk": []}


def test_unknown_key_name_raises_before_any_key_is_pressed(sent):
    # Pressing Ctrl and then failing on the bad key used to leave Ctrl held down.
    with pytest.raises(ValueError, match="notakey"):
        core.SendKeys("{Ctrl}{notakey}", waitTime=0)
    assert sent["vk"] == []


@pytest.mark.parametrize(
    ("vk", "extended"),
    [
        (core.Keys.VK_MENU, False),  # extended Alt = right Alt = AltGr, which adds Ctrl
        (core.Keys.VK_SHIFT, False),
        (ord("A"), False),
        (core.Keys.VK_LEFT, True),
        (core.Keys.VK_DELETE, True),
        (core.Keys.VK_LWIN, True),
    ],
)
def test_extended_flag_only_on_real_extended_keys(monkeypatch, vk, extended):
    calls = []
    fake_user32 = SimpleNamespace(keybd_event=lambda *a: calls.append(a))
    monkeypatch.setattr(core, "ctypes", SimpleNamespace(windll=SimpleNamespace(user32=fake_user32)))
    flags = core.KeyboardEventFlag.KeyDown | core.KeyboardEventFlag.ExtendedKey
    core.keybd_event(vk, 0, flags, 0)
    assert bool(calls[0][2] & core.KeyboardEventFlag.ExtendedKey) is extended


def test_clipboard_buffer_counts_utf16_units(monkeypatch):
    calls = {}

    def fake_alloc(flags, size):
        calls["alloc"] = size
        return 1

    def fake_copy(dest, src, count):
        calls["copy"] = count.value

    fake_ctypes = SimpleNamespace(
        windll=SimpleNamespace(
            user32=SimpleNamespace(
                EmptyClipboard=lambda: None,
                SetClipboardData=lambda fmt, h: 1,
                CloseClipboard=lambda: None,
            ),
            kernel32=SimpleNamespace(
                GlobalAlloc=fake_alloc, GlobalLock=lambda h: 1, GlobalUnlock=lambda h: None
            ),
        ),
        cdll=SimpleNamespace(msvcrt=SimpleNamespace(wcsncpy=fake_copy)),
        c_wchar_p=lambda v: v,
        c_size_t=ctypes.c_size_t,
        c_void_p=lambda v: v,
        c_uint=lambda v: v,
    )
    monkeypatch.setattr(core, "ctypes", fake_ctypes)
    monkeypatch.setattr(core, "_OpenClipboard", lambda hwnd: True)

    assert core.SetClipboardText("a\U0001f600") is True
    # 'a' + surrogate pair + NUL terminator = 4 UTF-16 units.
    assert calls == {"alloc": 8, "copy": 4}
