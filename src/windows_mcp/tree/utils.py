import logging
import os
import random
from collections.abc import Callable

import psutil
import win32con
import win32gui
import win32process

import windows_mcp.uia as uia
from windows_mcp.desktop.utils import (
    XAML_HOSTS,
    is_window_hung,
    remove_private_use_chars,
    repair_surrogates,
)
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


def panels_over(host: int) -> list[tuple[int, int, int, int]]:
    """Screen rectangles of XAML island child windows drawn over child window *host*.

    Notepad's Find panel is one, laid over the document (R4-13). The compositor draws
    islands on top although they sit below *host* in the stacking order, so WindowFromPoint
    and UIA hit tests both report the document under them. Other windows on top are
    drop_occluded's job; an element without its own window (*host* 0) is not checked.
    """
    if not host:
        return []
    rects = []

    def add(handle: int, _) -> bool:
        if (
            win32gui.GetClassName(handle) in XAML_HOSTS
            and win32gui.IsWindowVisible(handle)
            and handle != host
            and not win32gui.IsChild(handle, host)
            and not win32gui.IsChild(host, handle)
        ):
            rects.append(win32gui.GetWindowRect(handle))
        return True

    try:
        win32gui.EnumChildWindows(win32gui.GetAncestor(host, win32con.GA_ROOT), add, None)
    except Exception as e:  # a window closing mid-enumeration
        logger.debug("Panel check of window %s failed: %s", host, e)
    return rects


def covering_window(x: int, y: int, window: str) -> str:
    """Title of the window at (x, y) when it is not *window*, else "" (for refusal replies)."""
    handle = top_level_window_at(x, y)
    title = win32gui.GetWindowText(handle).strip() if handle else ""
    return "" if title == window.strip() else title or "another window"


def _around(hit, rect: tuple[int, int, int, int]) -> bool:
    """True when the hit control's box encloses *rect* and is larger (a container of it).

    Not the same box: that is another element in its place (a list scrolled by one row).
    Not a smaller box inside it: that part is drawn over the element and takes the input.
    """
    box = (hit.left, hit.top, hit.right, hit.bottom)
    encloses = box[0] <= rect[0] and box[1] <= rect[1] and box[2] >= rect[2] and box[3] >= rect[3]
    return encloses and box != rect


def element_still_at(
    name: str,
    control_type: str,
    x: int,
    y: int,
    rect: tuple[int, int, int, int] | None = None,
    window: str | None = None,
    max_depth: int = 10,
) -> bool:
    """True when the element under (x, y), or one of its parents, still is the listed one.

    Guards label actions (round-2 B.9): a label is a remembered position, so after the
    screen changes it would act on whatever moved there. The listed name may be the
    element's Name, its AutomationId (unnamed fields) or its type (unnamed scroll areas).

    With the element's *rect* and *window* title, a container of it in that same window
    also counts (R3-3): an embedded web page answers with its page pane, not the button.
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
        hit = control = uia.ControlFromPoint(x, y)
        for _ in range(max_depth):
            if control is None:
                break
            own_type = control.LocalizedControlType.strip().lower()
            seen = {control.Name.strip().lower(), control.AutomationId.strip().lower(), own_type}
            if (wanted and wanted in seen) or (not wanted and own_type == kind):
                return True
            control = control.GetParentControl()
        # ponytail: a stale label whose spot now shows a container of the same window
        # passes too; the name check above still catches a different element in its place.
        if rect and window is not None and hit is not None and not covering_window(x, y, window):
            return _around(hit.BoundingRectangle, rect)
    except Exception:
        # ponytail: an unreadable element acts as before B.9 rather than blocking the action.
        logger.debug("Could not re-check the element at (%s, %s)", x, y, exc_info=True)
        return True
    return False


# Where to try when the centre is taken: across the middle first, right side first.
# Explorer's Address Bar (900 px window) is its own edit only in the last ~6% of its width;
# path buttons and their group cover the rest (measured 2026-09-24).
_SPOT_FRACTIONS = [
    (fx, fy) for fy in (0.5, 0.25, 0.75) for fx in (0.95, 0.9, 0.75, 0.6, 0.4, 0.25, 0.1, 0.05)
]


def spot_on_element(
    name: str,
    control_type: str,
    x: int,
    y: int,
    rect: tuple[int, int, int, int],
    window: str,
) -> tuple[int, int] | None:
    """A point where input reaches the listed element: its centre if free, else another.

    R3-3: a part drawn over the centre (a path button on Explorer's Address Bar) would
    take the click itself, so try other points inside the element's box.
    """
    if element_still_at(name, control_type, x, y, rect=rect, window=window):
        return x, y
    left, top, right, bottom = rect
    # ponytail: 24 fixed sample points; a free sliver between them is missed.
    for fx, fy in _SPOT_FRACTIONS:
        px, py = left + int((right - left) * fx), top + int((bottom - top) * fy)
        if element_still_at(name, control_type, px, py, rect=rect, window=window):
            return px, py
    return None


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


def name_element(kind: str, name: str, window: str) -> str:
    """'button "Save" in "Notepad"' for an element already found by name or label."""
    name = _clean(name)
    return f'{kind} "{name}" in "{_clean(window)}"' if name else f'{kind} in "{_clean(window)}"'


def _window_title(handle: int) -> str:
    """The window's title, or its owner's for a title-less pop-up (Edge's sign-in notice)."""
    title = win32gui.GetWindowText(handle)
    return title or win32gui.GetWindowText(win32gui.GetAncestor(handle, win32con.GA_ROOTOWNER))


# Nameless parts a click lands on inside the real target (the text inside a button).
_INNER_PARTS = {"TextControl", "ImageControl"}


def describe_point(x: int, y: int, max_depth: int = 3) -> str:
    """'button "Save" in "Notepad"' for the element at (x, y); "" when nothing is there."""
    handle = top_level_window_at(x, y)
    if not handle:
        return ""
    window = f'in "{_clean(_window_title(handle))}"'
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


def expect_at(x: int, y: int, expect: str, max_depth: int = 3) -> str | None:
    """None when the element at (x, y) or one of its first *max_depth* ancestors has a
    name containing *expect* (case ignored); else what is there, for a refusal (R6-3).

    Ancestors count because a click on a button's text hits a Text child. A hung or
    VS Code-family window is refused unread, like describe_point.
    """
    handle = top_level_window_at(x, y)
    if not handle:
        return "nothing is there"
    title = _clean(_window_title(handle))
    if not _readable_window(handle):
        return f'the window there ("{title}") is not read (VS Code-family or not responding)'
    want = expect.casefold()
    try:
        control = uia.ControlFromPoint(x, y)
        for _ in range(max_depth + 1):
            if control is None:
                break
            if want in (control.Name or "").casefold():
                return None
            control = control.GetParentControl()
    except Exception:
        logger.debug("Could not read the element at (%s, %s)", x, y, exc_info=True)
        return f'the element there could not be read (in "{title}")'
    found = describe_point(x, y)
    return f"found {found}" if found else "nothing is there"


TYPED_TEXT_MISSING = (
    " Warning: the field does not contain the typed text exactly; the app may have changed it"
    " (auto-correct, formatting) or dropped keys. Check it before relying on it."
)


def _lines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def focused_value(typed: str | None = None) -> str:
    """' The field (edit "Search") now reads "hi".' for the focused field, else "".

    With *typed*, warns when the field does not contain it: Windows 11 Notepad
    auto-corrects and garbles fast typing at any speed tried (round-4 R4-16), while
    the reply otherwise shows only the start of the field.
    """
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
        reply = f' The field ({field}) now reads "{shown}"{size}.'
        # ponytail: a field that reformats its input on purpose (a number or date box)
        # is warned too; the wording leaves room for that.
        if typed and _lines(typed) not in _lines(value):
            reply += TYPED_TEXT_MISSING
        return reply
    except Exception:
        logger.debug("Could not read the focused field", exc_info=True)
        return ""


def _scroll_percent(control, axis: str) -> float | None:
    """*control*'s scroll percent along *axis*, or None when it does not scroll that way."""
    pattern = control.GetPattern(uia.PatternId.ScrollPattern)
    if pattern is None:
        return None
    if axis == "vertical":
        percent = pattern.VerticalScrollPercent if pattern.VerticallyScrollable else None
    else:
        percent = pattern.HorizontalScrollPercent if pattern.HorizontallyScrollable else None
    # Notepad reports 100.1 at the bottom (round-5 R5-3).
    return None if percent is None else round(min(max(percent, 0), 100), 1)


def _scroll_area(x: int, y: int, axis: str, max_depth: int = 15) -> tuple | None:
    """(control, description, percent) of the nearest area at (x, y) scrolling along *axis*."""
    try:
        control = uia.ControlFromPoint(x, y)
        for _ in range(max_depth):
            if control is None:
                break
            percent = _scroll_percent(control, axis)
            if percent is not None:
                return control, _described(control), percent
            control = control.GetParentControl()
    except Exception:
        logger.debug("Could not read the scroll position at (%s, %s)", x, y, exc_info=True)
    return None


def scroll_reader(x: int, y: int, axis: str) -> Callable[[], tuple[str, float] | None]:
    """A reader of (description, percent) for the area at (x, y) that scrolls along *axis*.

    R6-5: the first read walks up from the point; later reads ask only the area found,
    walking again if it is gone. The window is checked before every read.
    """
    area = None

    def read() -> tuple[str, float] | None:
        nonlocal area
        if not _readable_window(top_level_window_at(x, y)):
            return None
        if area is not None:
            try:
                percent = _scroll_percent(area[0], axis)
            except Exception:
                percent = None  # the element is gone
            if percent is not None:
                return area[1], percent
        found = _scroll_area(x, y, axis)
        area = found[:2] if found else None
        return (found[1], found[2]) if found else None

    return read


# Round-2 C.5: Click element="button:Save" resolves the element when it clicks, so no
# Snapshot label can go stale. A found element is (localized type, name, centre x, centre y).

_MAX_CANDIDATES = 10


def _listed(found: list[tuple[str, str, int, int]]) -> str:
    names = [f'{kind} "{_clean(name)}"' for kind, name, _, _ in found[:_MAX_CANDIDATES]]
    more = f" and {len(found) - _MAX_CANDIDATES} more" if len(found) > _MAX_CANDIDATES else ""
    return ", ".join(names) + more


def pick_element(
    found: list[tuple[str, str, int, int]],
    role: str,
    name: str,
    window: str,
    on_top: Callable[[tuple[str, str, int, int]], bool] | None = None,
) -> tuple[str, str, int, int]:
    """The one element meant, from those whose name contains *name*; else ValueError.

    An exact name (case ignored) wins; failing that, a single partial match. Never
    guesses between two. Identical duplicates (same type and name) are told apart by
    *on_top*: the one shown at its centre is taken, or several shown at the same spot (R3-5).
    """
    kind = role.casefold()
    typed = [f for f in found if f[0].casefold() == kind] if kind else found
    exact = [f for f in typed if f[1].casefold() == name.casefold()]
    matches = exact or typed
    identical = len({(f[0].casefold(), f[1].casefold()) for f in matches}) == 1
    if len(matches) > 1 and identical and on_top is not None:
        shown = [f for f in matches if on_top(f)]
        # One spot is one target: Explorer reports its "Copy as path" item twice, same box.
        if shown and len({f[2:] for f in shown}) == 1:
            return shown[0]
    if len(matches) == 1:
        return matches[0]
    what = f'{role or "element"} named "{name}"'
    if matches:
        raise ValueError(
            f'{len(matches)} elements match {what} in "{window}": {_listed(matches)}. '
            "Give the full name or its type (element='type:name'), or click by loc."
        )
    others = f" Found: {_listed(found)}." if found else ""
    colon = " A name containing ':' needs a leading ':' (element=':12:00')." if ":" in name else ""
    raise ValueError(f'No {what} in "{window}".{others}{colon}')


def find_element(handle: int, window: str, element: str) -> tuple[str, str, int, int]:
    """Find element='type:name' (type optional) in the window and check it is uncovered."""
    role, _, name = element.partition(":") if ":" in element else ("", "", element)
    role, name = role.strip(), name.strip()
    if not name:
        raise ValueError("element needs a name, e.g. element='button:Save' or element='Save'.")
    if not _readable_window(handle):
        raise ValueError(
            f'"{window}" cannot be read (not responding, or a VS Code window); click by loc.'
        )
    ia = uia.core._AutomationClient.instance().IUIAutomation
    flags = (
        uia.PropertyConditionFlags.PropertyConditionFlags_IgnoreCase
        | uia.PropertyConditionFlags.PropertyConditionFlags_MatchSubstring
    )
    found, boxes = [], {}
    try:
        condition = ia.CreatePropertyConditionEx(uia.PropertyId.NameProperty, name, flags)
        # ponytail: one native FindAll over the whole window; a very short name in a huge
        # tree (a grid of thousands) can take seconds. Narrow with type or window if so.
        elements = ia.ElementFromHandle(handle).FindAll(
            uia.TreeScope.TreeScope_Descendants, condition
        )
        for i in range(elements.Length):
            el = elements.GetElement(i)
            rect = el.CurrentBoundingRectangle
            if el.CurrentIsOffscreen or rect.right <= rect.left or rect.bottom <= rect.top:
                continue
            item = (
                el.CurrentLocalizedControlType,
                el.CurrentName,
                (rect.left + rect.right) // 2,
                (rect.top + rect.bottom) // 2,
            )
            found.append(item)
            boxes[item] = (rect.left, rect.top, rect.right, rect.bottom)
    except Exception as e:
        logger.debug("Element search failed in window %s", handle, exc_info=True)
        raise ValueError(f'Could not search "{window}" for elements: {e}') from None

    def on_top(f: tuple[str, str, int, int]) -> bool:
        return element_still_at(f[1], f[0], f[2], f[3], rect=boxes[f], window=window)

    picked = pick_element(found, role, name, window, on_top)
    kind, found_name, x, y = picked
    # Same spot check as label clicks (B.9): another window or a pop-up may sit on top.
    spot = spot_on_element(found_name, kind, x, y, rect=boxes[picked], window=window)
    if spot is None:
        what = f'{kind} "{_clean(found_name)}"'
        if cover := covering_window(x, y, window):
            raise ValueError(
                f'{what} is covered by "{_clean(cover)}"; bring "{window}" to the front.'
            )
        raise ValueError(
            f'{what}: something else of "{window}" is drawn over it everywhere tried; click by loc.'
        )
    return kind, found_name, *spot


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
