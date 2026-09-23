"""WaitFor conditions that read the screen's pixels instead of the UI tree.

screen_text (round-2 C.6) finds text by OCR; screen_changed and screen_idle (C.7)
compare captures, for apps with no accessibility data, to replace fixed Waits.
"""

import time
from collections.abc import Callable
from typing import Any

from PIL import Image, ImageChops

import windows_mcp.uia as uia
from windows_mcp.desktop import screenshot as screenshot_capture
from windows_mcp.tools import find_text as find_text_tools
from windows_mcp.tools._coords import to_model

SCREEN_CONDITIONS = {"screen_text", "screen_changed", "screen_idle"}

# A pixel counts as changed when its grey level moves more than this (of 255), so
# fades and compression noise do not; the change counts when at least MIN_CHANGED_PIXELS
# do, so a blinking caret (~40 px) does not while a 16x16 icon (256 px) does.
CHANGE_LEVEL = 24
MIN_CHANGED_PIXELS = 100


def capture(rect: uia.Rect) -> Image.Image:
    # The screenshot module directly: Desktop.get_screenshot flashes a border each time.
    return screenshot_capture.capture(rect)[0]


def changed_box(before: Image.Image, after: Image.Image) -> tuple[int, int, int, int] | None:
    """The box (left, top, right, bottom) around what changed, or None for no real change."""
    if before.size != after.size:
        return (0, 0, *before.size)
    diff = ImageChops.difference(before.convert("L"), after.convert("L"))
    mask = diff.point(lambda v: 255 if v > CHANGE_LEVEL else 0)
    if mask.histogram()[255] < MIN_CHANGED_PIXELS:
        return None
    return mask.getbbox()


def _seconds(value: float) -> str:
    return f"{value:g} second" + ("" if value == 1 else "s")


def screen_check(
    desktop: Any, condition: str, text: str | None, rect: uia.Rect, settle: float
) -> Callable[[], tuple[bool, str]]:
    """A check WaitFor calls once per attempt: (matched, detail)."""
    if condition == "screen_text":

        def text_check() -> tuple[bool, str]:
            spots = find_text_tools.find_on_screen(text, rect)
            if spots:
                return True, find_text_tools.describe_matches(desktop, text, spots)
            return False, f"text {text!r} was not on screen"

        return text_check

    if condition == "screen_changed":
        # ponytail: compared with the screen when WaitFor starts, so a change that happened
        # during the preceding click is missed; screen_idle covers "wait until done".
        baseline = capture(rect)

        def changed_check() -> tuple[bool, str]:
            box = changed_box(baseline, capture(rect))
            if box is None:
                return False, "the screen did not change"
            left, top, right, bottom = box
            screen = (rect.left + left, rect.top + top, rect.left + right, rect.top + bottom)
            return True, f"the screen changed around {list(to_model(desktop, screen, count=4))}"

        return changed_check

    state = {"frame": capture(rect), "since": time.monotonic()}

    def idle_check() -> tuple[bool, str]:
        frame, now = capture(rect), time.monotonic()
        if changed_box(state["frame"], frame) is not None:
            state["since"] = now
        state["frame"] = frame
        still = now - state["since"]
        if still >= settle:
            return True, f"the screen was still for {_seconds(settle)}"
        return False, f"the screen kept changing (last change {still:.2f}s ago)"

    return idle_check
