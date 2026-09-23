"""Clipboard tool — copy/paste clipboard operations."""

import json
from typing import Literal

from mcp.types import ToolAnnotations
from windows_mcp.infrastructure import with_analytics
from fastmcp import Context
from windows_mcp.clipboard import service as clipboard_service
from windows_mcp.tools._output import raise_error_replies


def _as_files(value: list[str] | str | None) -> list[str] | None:
    """files as a list, a JSON list in text (some clients send that), or one path."""
    if isinstance(value, str):
        text = value.strip()
        value = json.loads(text) if text.startswith("[") else [text]
    if value is not None and not all(isinstance(path, str) for path in value):
        raise ValueError("files must be a list of full paths")
    return value


def register(mcp, *, get_desktop, get_analytics):
    @mcp.tool(
        name="Clipboard",
        description=(
            "Copy/paste clipboard operations. Keywords: copy, paste, cut, clipboard, text transfer, "
            'image, screenshot, files. mode="get" reads the clipboard: its text, and it names any '
            "image (with size), copied files (listed by path) or HTML; add save_image=<full .png "
            'path> to save a clipboard image to a new file (never overwrites). mode="set" takes '
            "exactly one of text, image=<image file path> (pastes as a picture) or files=[full "
            "paths] (as Explorer's Ctrl+C, so a paste in a folder copies them)."
        ),
        annotations=ToolAnnotations(
            title="Clipboard",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "Clipboard-Tool")
    @raise_error_replies
    def clipboard_tool(
        mode: Literal["get", "set"],
        text: str | None = None,
        image: str | None = None,
        files: list[str] | str | None = None,
        save_image: str | None = None,
        ctx: Context = None,
    ) -> str:
        files = _as_files(files)
        if mode == "get":
            if text is not None or image is not None or files is not None:
                raise ValueError("text, image and files only apply to mode='set'")
            if save_image is not None:
                return clipboard_service.save_image(save_image)
            return clipboard_service.describe()
        if mode == "set":
            if save_image is not None:
                raise ValueError("save_image only applies to mode='get'")
            given = [v for v in (text, image, files) if v is not None]
            if not given:
                return "Error: text parameter required for set mode (or image, or files)."
            if len(given) > 1:
                raise ValueError("mode='set' takes only one of text, image or files")
            if image is not None:
                return clipboard_service.set_image(image)
            if files is not None:
                return clipboard_service.set_files(files)
            return clipboard_service.set_text(text)
        return 'Error: mode must be either "get" or "set".'
