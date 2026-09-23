"""Round-2 C.4: Clipboard reports images/files/HTML, saves an image, sets an image or files.

A fake clipboard stands in for win32clipboard, so the user's real clipboard is never touched.
"""

import asyncio
import struct
from unittest.mock import patch

import pytest
import pywintypes
import win32con
from PIL import Image

from windows_mcp.clipboard import service
from windows_mcp.tools import clipboard as clipboard_tool_module

REGISTERED = {"HTML Format": 49000, "PNG": 49001, "Preferred DropEffect": 49002}


class FakeClipboard:
    def __init__(self, data=None):
        self.data = dict(data or {})
        self.emptied = False
        self.is_open = False

    def OpenClipboard(self):
        assert not self.is_open
        self.is_open = True

    def CloseClipboard(self):
        self.is_open = False

    def EmptyClipboard(self):
        assert self.is_open
        self.data.clear()
        self.emptied = True

    def CountClipboardFormats(self):
        # Like pywin32: a count of 0 comes back as an error, not as 0.
        if not self.data:
            raise pywintypes.error(0, "CountClipboardFormats", "No error message is available")
        return len(self.data)

    def EnumClipboardFormats(self, after):
        formats = list(self.data)
        index = formats.index(after) + 1 if after else 0
        return formats[index] if index < len(formats) else 0

    def IsClipboardFormatAvailable(self, fmt):
        return fmt in self.data

    def GetClipboardData(self, fmt):
        assert self.is_open
        return self.data[fmt]

    def SetClipboardData(self, fmt, value):
        assert self.is_open
        self.data[fmt] = value

    def SetClipboardText(self, text, fmt):
        self.SetClipboardData(fmt, text)

    def RegisterClipboardFormat(self, name):
        return REGISTERED[name]


@pytest.fixture
def board():
    fake = FakeClipboard()
    with patch.object(service, "win32clipboard", fake):
        yield fake


def _grab(image):
    return patch.object(service.ImageGrab, "grabclipboard", return_value=image)


# --- get: what the clipboard holds -------------------------------------------------------


def test_text_only_reads_as_before(board):
    board.data = {win32con.CF_UNICODETEXT: "hello"}
    assert service.describe() == "Clipboard content:\nhello"


def test_text_with_image_and_html_names_the_extras(board):
    board.data = {win32con.CF_UNICODETEXT: "hi", win32con.CF_DIB: b"", 49000: b""}
    with _grab(Image.new("RGB", (800, 600))):
        reply = service.describe()
    assert reply == "Clipboard content:\nhi\n\nAlso on the clipboard: an image (800x600), HTML."


def test_image_only(board):
    board.data = {win32con.CF_DIB: b""}
    with _grab(Image.new("RGB", (32, 16))):
        assert service.describe() == "Clipboard holds an image (32x16)."


def test_files_are_listed(board):
    board.data = {win32con.CF_HDROP: ("C:\\a.txt", "C:\\b.pdf")}
    assert service.describe() == "Clipboard holds 2 files:\n  C:\\a.txt\n  C:\\b.pdf"


def test_empty(board):
    assert service.describe() == "Clipboard is empty."


def test_unreadable_format(board):
    board.data = {12345: b"x"}
    assert service.describe() == "Clipboard holds data in a format this tool cannot read."


# --- get with save_image -----------------------------------------------------------------


def test_save_image_writes_a_png(tmp_path):
    target = tmp_path / "snip.png"
    with _grab(Image.new("RGB", (40, 30), "red")):
        reply = service.save_image(str(target))
    assert reply == f"Saved the clipboard image (40x30) to {target}."
    with Image.open(target) as saved:
        assert saved.format == "PNG" and saved.size == (40, 30)


def test_save_image_never_overwrites(tmp_path):
    target = tmp_path / "snip.png"
    target.write_bytes(b"keep me")
    with _grab(Image.new("RGB", (4, 4))):
        with pytest.raises(ValueError, match="already exists"):
            service.save_image(str(target))
    assert target.read_bytes() == b"keep me"


@pytest.mark.parametrize(
    ("name", "message"),
    [("snip.jpg", r"\.png"), ("missing/snip.png", "folder"), ("relative.png", "full path")],
)
def test_save_image_refuses_bad_paths(tmp_path, name, message):
    path = name if name == "relative.png" else str(tmp_path / name)
    with _grab(Image.new("RGB", (4, 4))):
        with pytest.raises(ValueError, match=message):
            service.save_image(path)


def test_save_image_without_an_image(tmp_path):
    with _grab(None):
        with pytest.raises(ValueError, match="no image"):
            service.save_image(str(tmp_path / "snip.png"))


# --- set image / files ---------------------------------------------------------------------


def test_set_image_puts_dib_and_png(board, tmp_path):
    source = tmp_path / "chart.png"
    Image.new("RGBA", (12, 8), (0, 0, 255, 128)).save(source)
    reply = service.set_image(str(source))
    assert reply == "Clipboard set to the image chart.png (12x8)."
    assert board.emptied
    header = struct.unpack("<Iii", board.data[win32con.CF_DIB][:12])
    assert header == (40, 12, 8)  # BITMAPINFOHEADER size, width, height (no file header)
    assert board.data[49001].startswith(b"\x89PNG")


def test_set_image_refuses_a_non_image(board, tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("not an image")
    with pytest.raises(ValueError, match="not an image"):
        service.set_image(str(source))
    assert not board.emptied


def test_set_files_builds_a_copy_drop(board, tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("a")
    b.write_text("b")
    reply = service.set_files([str(a), str(b)])
    assert reply == "Clipboard set to 2 files (paste in a folder to copy them)."
    drop = board.data[win32con.CF_HDROP]
    assert struct.unpack("<IiiII", drop[:20]) == (20, 0, 0, 0, 1)  # offset, point, not client, wide
    assert drop[20:].decode("utf-16-le") == f"{a}\0{b}\0\0"
    assert board.data[49002] == struct.pack("<I", 1)  # DROPEFFECT_COPY: paste copies, not moves


def test_set_files_refuses_a_missing_file_and_keeps_the_clipboard(board, tmp_path):
    board.data = {win32con.CF_UNICODETEXT: "user's text"}
    with pytest.raises(ValueError, match="does not exist"):
        service.set_files([str(tmp_path / "gone.txt")])
    assert board.data == {win32con.CF_UNICODETEXT: "user's text"}


# --- the tool's argument rules -------------------------------------------------------------


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _clipboard(**kwargs):
    mcp = FakeMCP()
    clipboard_tool_module.register(mcp, get_desktop=lambda: None, get_analytics=lambda: None)
    return asyncio.run(mcp.tools["Clipboard"](**kwargs))


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ({"mode": "set", "text": "x", "image": "C:\\a.png"}, "only one"),
        ({"mode": "set", "text": "x", "save_image": "C:\\a.png"}, "save_image"),
        ({"mode": "get", "image": "C:\\a.png"}, "set"),
        ({"mode": "get", "files": ["C:\\a.txt"]}, "set"),
    ],
)
def test_tool_refuses_wrong_argument_mixes(args, message):
    with (
        patch.object(service, "set_image") as set_image,
        patch.object(service, "describe") as describe,
    ):
        with pytest.raises(ValueError, match=message):
            _clipboard(**args)
    set_image.assert_not_called()
    describe.assert_not_called()


@pytest.mark.parametrize("files", ['["C:\\\\a.txt", "C:\\\\b.txt"]', ["C:\\a.txt", "C:\\b.txt"]])
def test_tool_accepts_files_as_list_or_json(files):
    with patch.object(service, "set_files", return_value="ok") as set_files:
        assert _clipboard(mode="set", files=files) == "ok"
    set_files.assert_called_once_with(["C:\\a.txt", "C:\\b.txt"])


def test_tool_routes_get_and_save_image():
    with (
        patch.object(service, "describe", return_value="d"),
        patch.object(service, "save_image", return_value="s") as save,
    ):
        assert _clipboard(mode="get") == "d"
        assert _clipboard(mode="get", save_image="C:\\x.png") == "s"
    save.assert_called_once_with("C:\\x.png")
