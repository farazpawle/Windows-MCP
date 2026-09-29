"""FindText tool - find text on screen by OCR, for UIs with no accessibility tree (round-2 C.6)."""

from collections.abc import Callable
from typing import Any

from fastmcp import Context
from mcp.types import ToolAnnotations

import windows_mcp.uia as uia
from windows_mcp.infrastructure import with_analytics
from windows_mcp.ocr.service import find_on_screen
from windows_mcp.tools._coords import to_model, to_screen
from windows_mcp.tools._snapshot_helpers import _as_region

_MAX_SPOTS = 10
_LINE_CHARS = 60


def screen_rect(desktop: Any, region: list | str | None) -> uia.Rect:
    """The screen-pixel rectangle to read: the caller's region, else every display."""
    rect = desktop.parse_region_selection(to_screen(desktop, _as_region(region), count=4))
    if rect is None:
        box = desktop.get_screen_box()
        rect = uia.Rect(box.left, box.top, box.right, box.bottom)
    return rect


def window_rect(window: Any, rect: uia.Rect) -> uia.Rect:
    """The part of *rect* the window covers; ValueError when nothing of it can be read."""
    if window.status.value == "Minimized":
        raise ValueError(f'"{window.name}" is minimized; restore it first (App mode="restore").')
    box = window.bounding_box
    left, top = max(rect.left, box.left), max(rect.top, box.top)
    right, bottom = min(rect.right, box.right), min(rect.bottom, box.bottom)
    if left >= right or top >= bottom:
        raise ValueError(f'"{window.name}" is outside the region or off screen.')
    return uia.Rect(left, top, right, bottom)


def describe_matches(desktop: Any, text: str, matches: list[tuple[str, int, int]]) -> str:
    """'"Sign in" 2 times: (x,y) in "line"; ...' with positions in the caller's space."""
    spots = []
    for line, x, y in matches[:_MAX_SPOTS]:
        mx, my = to_model(desktop, (x, y))
        shown = line if len(line) <= _LINE_CHARS else f"{line[:_LINE_CHARS]}..."
        spots.append(f'({mx},{my}) in "{shown}"')
    more = f" and {len(matches) - _MAX_SPOTS} more" if len(matches) > _MAX_SPOTS else ""
    times = "1 time" if len(matches) == 1 else f"{len(matches)} times"
    return f'"{text}" {times}: {"; ".join(spots)}{more}'


def register(
    mcp: Any,
    *,
    get_desktop: Callable[[], Any],
    get_analytics: Callable[[], Any],
) -> None:
    @mcp.tool(
        name="FindText",
        description=(
            "Finds text on screen by reading the pixels (Windows' built-in OCR), for apps with "
            "no accessibility data: games, remote desktops, canvas and drawing apps. Returns "
            "every place the phrase appears (case ignored, words in order on one line, may be "
            "part of a word) with a clickable [x, y] position. Searches every screen, or "
            "region=[left, top, right, bottom] only (faster, fewer stray matches), or "
            "window= one window's title or handle (a number, from App mode='list'): only its "
            "visible part is read and text of windows over it is left out. About 1.1 s "
            "for a full screen, about 0.5 s for a small region. Prefer Snapshot or Click element= "
            "where UI elements exist. To wait for text to appear, use WaitFor "
            "condition='screen_text'."
        ),
        annotations=ToolAnnotations(
            title="FindText",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "FindText-Tool")
    def find_text_tool(
        text: str,
        region: list[int] | str | None = None,
        window: str | int | None = None,
        ctx: Context = None,
    ) -> str:
        if not text or not text.strip():
            raise ValueError("text must name the words to find.")
        desktop = get_desktop()
        rect = screen_rect(desktop, region)
        handle = None
        if window is not None:
            by_handle = isinstance(window, int)
            target, _ = desktop.pick_window(
                None if by_handle else window, window if by_handle else None, required=True
            )
            rect = window_rect(target, rect)
            handle = target.handle
        matches = find_on_screen(text, rect, handle)
        if matches:
            return f"Found {describe_matches(desktop, text, matches)}."
        if window is not None:
            where = f'in "{target.name}"'
        else:
            where = "in the region" if region is not None else "on screen"
        return (
            f'"{text}" was not found {where}. OCR reads only what is visible; very small, '
            "stylised or low-contrast text can be missed (try a Screenshot with zoom)."
        )
