import logging
import os
import random
from collections.abc import Callable

import psutil
import win32con
import win32gui
import win32process

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
