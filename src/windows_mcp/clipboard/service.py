"""Clipboard reads and writes beyond plain text: images, file lists, HTML (round-2 C.4)."""

import io
import struct
from contextlib import contextmanager
from pathlib import Path

import win32clipboard
import win32con
from PIL import Image, ImageGrab

_IMAGE_FORMATS = (win32con.CF_DIB, win32con.CF_DIBV5, win32con.CF_BITMAP)
_DROPEFFECT_COPY = 1


@contextmanager
def _opened():
    win32clipboard.OpenClipboard()
    try:
        yield
    finally:
        win32clipboard.CloseClipboard()


def _clipboard_image() -> Image.Image | None:
    # grabclipboard opens the clipboard itself, so call it while ours is closed.
    image = ImageGrab.grabclipboard()
    return image if isinstance(image, Image.Image) else None


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def describe() -> str:
    """What the clipboard holds: its text as before, plus any image, files or HTML."""
    with _opened():
        # Not CountClipboardFormats: pywin32 raises on its 0 instead of returning it.
        if not win32clipboard.EnumClipboardFormats(0):
            return "Clipboard is empty."
        has = win32clipboard.IsClipboardFormatAvailable
        text = None
        if has(win32con.CF_UNICODETEXT):
            text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        files = []
        if has(win32con.CF_HDROP):
            files = list(win32clipboard.GetClipboardData(win32con.CF_HDROP))
        has_image = any(has(fmt) for fmt in _IMAGE_FORMATS)
        has_html = has(win32clipboard.RegisterClipboardFormat("HTML Format"))

    extras = []
    if has_image:
        image = _clipboard_image()
        extras.append(f"an image ({image.width}x{image.height})" if image else "an image")
    if has_html:
        extras.append("HTML")
    if files:
        head = f"Clipboard holds {_plural(len(files), 'file')}:\n" + "\n".join(
            f"  {path}" for path in files
        )
    elif text is not None:
        head = f"Clipboard content:\n{text}"
    elif extras:
        return f"Clipboard holds {', '.join(extras)}."
    else:
        return "Clipboard holds data in a format this tool cannot read."
    return head + (f"\n\nAlso on the clipboard: {', '.join(extras)}." if extras else "")


def save_image(path: str) -> str:
    """Save the clipboard's image as a new PNG file; an existing file is never overwritten."""
    target = Path(path).expanduser()
    if target.suffix.lower() != ".png":
        raise ValueError(f"save_image must name a .png file (got {path!r}).")
    if not target.is_absolute():
        raise ValueError(f"save_image must be a full path, e.g. C:\\Temp\\snip.png (got {path!r}).")
    if not target.parent.is_dir():
        raise ValueError(f"The folder {target.parent} does not exist.")
    if target.exists():
        raise ValueError(f"{target} already exists; choose another name (nothing was overwritten).")
    image = _clipboard_image()
    if image is None:
        raise ValueError("The clipboard holds no image; nothing was saved.")
    with open(target, "xb") as file:  # "x": fails rather than overwrite a file made meanwhile
        image.save(file, format="PNG")
    return f"Saved the clipboard image ({image.width}x{image.height}) to {target}."


def set_text(text: str) -> str:
    with _opened():
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
    return f"Clipboard set to: {text[:100]}{'...' if len(text) > 100 else ''}"


def _dib(image: Image.Image) -> bytes:
    """CF_DIB data: a BMP file without its 14-byte file header."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="BMP")
    return buffer.getvalue()[14:]


def set_image(path: str) -> str:
    """Put an image file on the clipboard, for pasting into Paint, Word, a chat."""
    source = Path(path).expanduser()
    if not source.is_file():
        raise ValueError(f"No file at {source}.")
    try:
        with Image.open(source) as opened:
            image = opened.copy()
    except Exception as e:
        raise ValueError(f"{source} is not an image this tool can read ({e}).") from e
    png = io.BytesIO()
    image.convert("RGBA").save(png, format="PNG")
    dib = _dib(image)
    with _opened():
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, dib)
        # Every app reads CF_DIB; "PNG" keeps transparency for apps that prefer it (Office, browsers).
        win32clipboard.SetClipboardData(
            win32clipboard.RegisterClipboardFormat("PNG"), png.getvalue()
        )
    return f"Clipboard set to the image {source.name} ({image.width}x{image.height})."


def _dropfiles(paths: list[str]) -> bytes:
    """CF_HDROP data: a DROPFILES header, then the paths as a double-null-terminated wide list."""
    header = struct.pack("<IiiII", 20, 0, 0, 0, 1)  # pFiles offset, pt.x, pt.y, fNC, fWide
    return header + ("\0".join(paths) + "\0\0").encode("utf-16-le")


def set_files(paths: list[str]) -> str:
    """Put files on the clipboard as Explorer's Ctrl+C does, so a paste in a folder copies them."""
    if not paths:
        raise ValueError("files is empty; give at least one full path.")
    checked = []
    for path in paths:
        item = Path(path).expanduser()
        if not item.is_absolute():
            raise ValueError(f"files must be full paths (got {path!r}).")
        if not item.exists():
            raise ValueError(f"{item} does not exist; nothing was put on the clipboard.")
        checked.append(str(item))
    with _opened():
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_HDROP, _dropfiles(checked))
        win32clipboard.SetClipboardData(
            win32clipboard.RegisterClipboardFormat("Preferred DropEffect"),
            struct.pack("<I", _DROPEFFECT_COPY),  # paste copies rather than moves
        )
    return f"Clipboard set to {_plural(len(checked), 'file')} (paste in a folder to copy them)."
