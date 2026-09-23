import logging
import os
import random
from collections.abc import Callable

import psutil
import win32con
import win32gui
import win32process

import windows_mcp.uia as uia
from windows_mcp.desktop.utils import is_window_hung, remove_private_use_chars, repair_surrogates
from windows_mcp.uia import Control

logger = logging.getLogger(__name__)

# The desktop icons live in Progman on some builds and in a WorkerW on others.
_DESKTOP_CLASSES = {"Progman", "WorkerW"}

# VS Code and its forks lock up (main process pinned at 100% CPU, "Not Responding"
# until restarted) after a single UI Automation tree read, and the read returns
# nothing anyway (measured 2026-09-22: 21 s, 0 elements). Never walk them.
_UNREADABLE_PROCESSES = {
    "code.exe",
    "code - insiders.exe",
    "cursor.exe",
    "windsurf.exe",
    "antigravity.exe",
    "antigravity ide.exe",  # the name its installer uses on this PC (froze 2026-09-22)
    "vscodium.exe",
}


def _process_name(handle: int) -> str:
    try:
        _, pid = win32process.GetWindowThreadProcessId(handle)
        return psutil.Process(pid).name()
    except Exception:
        return ""


def is_unreadable_window(handle: int) -> bool:
    """True for windows whose UI tree must not be read (VS Code family).

    Set WINDOWS_MCP_READ_VSCODE=1 to read them anyway.
    """
    if os.getenv("WINDOWS_MCP_READ_VSCODE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    return _process_name(handle).lower() in _UNREADABLE_PROCESSES


def random_point_within_bounding_box(node: Control, scale_factor: float = 1.0) -> tuple[int, int]:
    """
    Generate a random point within a scaled-down bounding box.

    Args:
        node (Control): The node with a bounding rectangle
        scale_factor (float, optional): The factor to scale down the bounding box. Defaults to 1.0.

    Returns:
        tuple: A random point (x, y) within the scaled-down bounding box
    """
    box = node.BoundingRectangle
    scaled_width = int(box.width() * scale_factor)
    scaled_height = int(box.height() * scale_factor)
    scaled_left = box.left + (box.width() - scaled_width) // 2
    scaled_top = box.top + (box.height() - scaled_height) // 2
    x = random.randint(scaled_left, scaled_left + scaled_width)
    y = random.randint(scaled_top, scaled_top + scaled_height)
    return (x, y)


def top_level_window_at(x: int, y: int) -> int:
    """Handle of the top-level window that owns the screen point, or 0."""
    hwnd = win32gui.WindowFromPoint((x, y))
    return win32gui.GetAncestor(hwnd, win32con.GA_ROOT) if hwnd else 0


def element_still_at(name: str, control_type: str, x: int, y: int, max_depth: int = 10) -> bool:
    """True when the element under (x, y), or one of its parents, still is the listed one.

    Guards label actions (round-2 B.9): a label is a remembered position, so after the
    screen changes it would act on whatever moved there. The listed name may be the
    element's Name, its AutomationId (unnamed fields) or its type (unnamed scroll areas).
    """
    handle = top_level_window_at(x, y)
    # Snapshot never lists elements in these, and reading a hung or VS Code window stalls it.
    if not handle or is_window_hung(handle) or is_unreadable_window(handle):
        return False
    if control_type == "Word":  # one word of a text element: no UIA element carries its name
        return True
    wanted = name.strip().lower()
    wanted = "" if wanted == "''" else wanted
    kind = control_type.strip().lower()
    try:
        control = uia.ControlFromPoint(x, y)
        for _ in range(max_depth):
            if control is None:
                break
            own_type = control.LocalizedControlType.strip().lower()
            seen = {control.Name.strip().lower(), control.AutomationId.strip().lower(), own_type}
            if (wanted and wanted in seen) or (not wanted and own_type == kind):
                return True
            control = control.GetParentControl()
    except Exception:
        # ponytail: an unreadable element acts as before B.9 rather than blocking the action.
        logger.debug("Could not re-check the element at (%s, %s)", x, y, exc_info=True)
        return True
    return False


# Round-2 B.10: what Click, Type and Scroll replies report. Each read is guarded like
# element_still_at: a hung or VS Code-family window is named but never read.


def _clean(text: str, limit: int = 60) -> str:
    text = repair_surrogates(remove_private_use_chars(text or "")).strip()
    return text if len(text) <= limit else f"{text[:limit]}..."


def _readable_window(handle: int) -> bool:
    return bool(handle) and not is_window_hung(handle) and not is_unreadable_window(handle)


def _described(control) -> str:
    name = _clean(control.Name)
    return f'{control.LocalizedControlType} "{name}"' if name else control.LocalizedControlType


# Nameless parts a click lands on inside the real target (the text inside a button).
_INNER_PARTS = {"TextControl", "ImageControl"}


def describe_point(x: int, y: int, max_depth: int = 3) -> str:
    """'button "Save" in "Notepad"' for the element at (x, y); "" when nothing is there."""
    handle = top_level_window_at(x, y)
    if not handle:
        return ""
    window = f'in "{_clean(win32gui.GetWindowText(handle))}"'
    if not _readable_window(handle):
        return f"{window} (not read)"
    try:
        control = uia.ControlFromPoint(x, y)
        for _ in range(max_depth):
            if control is None or control.Name.strip():
                break
            if control.ControlTypeName not in _INNER_PARTS:
                break  # an unnamed field is itself the target, not its window
            control = control.GetParentControl()
        return f"{_described(control)} {window}" if control is not None else window
    except Exception:
        logger.debug("Could not describe the element at (%s, %s)", x, y, exc_info=True)
        return window


def focused_value() -> str:
    """' The field (edit "Search") now reads "hi".' for the focused field, else ""."""
    if not _readable_window(win32gui.GetForegroundWindow()):
        return ""
    try:
        focused = uia.GetFocusedControl()
        pattern = focused.GetPattern(uia.PatternId.ValuePattern) if focused else None
        if pattern is None:
            return ""
        field = _described(focused)
        if focused.IsPassword:
            return f" The field ({field}) is a password box; its contents are not shown."
        value = pattern.Value or ""
        shown = _clean(value, 100)
        size = f" ({len(value):,} characters)" if len(value) > 100 else ""
        return f' The field ({field}) now reads "{shown}"{size}.'
    except Exception:
        logger.debug("Could not read the focused field", exc_info=True)
        return ""


def scroll_position(x: int, y: int, axis: str, max_depth: int = 15) -> tuple[str, float] | None:
    """(description, percent) of the nearest area at (x, y) that scrolls along *axis*."""
    if not _readable_window(top_level_window_at(x, y)):
        return None
    vertical = axis == "vertical"
    try:
        control = uia.ControlFromPoint(x, y)
        for _ in range(max_depth):
            if control is None:
                break
            pattern = control.GetPattern(uia.PatternId.ScrollPattern)
            if pattern is not None and (
                pattern.VerticallyScrollable if vertical else pattern.HorizontallyScrollable
            ):
                percent = (
                    pattern.VerticalScrollPercent if vertical else pattern.HorizontalScrollPercent
                )
                return _described(control), round(percent, 1)
            control = control.GetParentControl()
    except Exception:
        logger.debug("Could not read the scroll position at (%s, %s)", x, y, exc_info=True)
    return None


def z_order_rank() -> dict[int, int]:
    """Top-level window handle -> position in z-order (0 = frontmost, topmost first)."""
    handles: list[int] = []
    win32gui.EnumWindows(lambda h, _: handles.append(h) or True, None)
    return {h: i for i, h in enumerate(handles)}


def is_fully_covered(
    handle: int,
    rect,
    window_at: Callable[[int, int], int] = top_level_window_at,
    steps: int = 8,
) -> bool:
    """True when other windows cover every sampled point of *rect* (a uia Rect).

    Lets a region capture skip a window it cannot see before walking its tree.
    """
    # ponytail: an 8x8 point grid; a visible sliver narrower than one grid step
    # (1/8 of the rect) is missed and the window skipped. Add steps if that bites.
    width, height = rect.right - rect.left, rect.bottom - rect.top
    for i in range(steps):
        for j in range(steps):
            x = rect.left + width * (2 * i + 1) // (2 * steps)
            y = rect.top + height * (2 * j + 1) // (2 * steps)
            if _same_window(handle, window_at(x, y)):
                return False
    return True


def _same_window(handle: int, hit: int) -> bool:
    if hit == handle:
        return True
    try:
        classes = {win32gui.GetClassName(handle), win32gui.GetClassName(hit)}
    except Exception:
        return False
    return classes <= _DESKTOP_CLASSES


def drop_occluded(
    handle: int,
    interactive_nodes: list,
    scrollable_nodes: list,
    semantic_root,
    window_at: Callable[[int, int], int] = top_level_window_at,
) -> tuple[list, list]:
    """Remove elements of a background window whose centre another window covers.

    A click at such an element lands on the covering window, so listing it only
    misleads. Filters the flat lists and, in place, the window's semantic tree.
    """
    cache: dict[tuple[int, int], bool] = {}

    def visible(center) -> bool:
        key = (center.x, center.y)
        if key not in cache:
            cache[key] = _same_window(handle, window_at(center.x, center.y))
        return cache[key]

    def prune(node) -> None:
        node.children = [
            child
            for child in node.children
            if child.center is None
            or child.element_type not in ("interactive", "scrollable")
            or visible(child.center)
        ]
        for child in node.children:
            prune(child)

    if semantic_root is not None:
        prune(semantic_root)
    return (
        [n for n in interactive_nodes if visible(n.center)],
        [n for n in scrollable_nodes if visible(n.center)],
    )
