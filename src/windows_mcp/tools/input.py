"""Input tools — Click, Type, Scroll, Move, Shortcut, Wait, WaitFor."""

import json
import math
import re
import time
from collections.abc import Callable, Iterator
from typing import Any, Literal

from mcp.types import ToolAnnotations
from windows_mcp.infrastructure import with_analytics
from fastmcp import Context
from windows_mcp.tools._args import as_bool


WaitForCondition = Literal[
    "text_exists",
    "active_window",
    "element_exists",
    "element_enabled",
    "focused_element",
]


def _resolve_label(desktop: Any, label: int) -> list[int]:
    """Resolve a UI element label to screen coordinates."""
    if desktop.label_tree_state is None:
        raise ValueError("Desktop state is empty. Please call Snapshot first.")
    try:
        return list(desktop.get_coordinates_from_label(label))
    except Exception as e:
        raise ValueError(f"Failed to find element with label {label}: {e}")


def _validate_finite_number(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")


def _as_loc(value: list | str | None) -> list | None:
    """Coerce a JSON-stringified list back to a list.

    Claude Desktop strips anyOf schemas and the model serializes lists as
    strings (e.g. '[100, 200]'). Parsing here keeps the tools working.
    """
    if value is None or isinstance(value, list):
        return value
    return json.loads(value)


def _as_point(value: object, name: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be a list of exactly 2 integers [x, y]")
    parsed = []
    for item in value:
        if isinstance(item, bool):
            raise ValueError(f"{name} must contain integers, not booleans")
        if isinstance(item, int):
            parsed.append(item)
            continue
        if isinstance(item, str):
            stripped = item.strip()
            if stripped and stripped.lstrip("+-").isdigit():
                parsed.append(int(stripped))
                continue
        raise ValueError(f"{name} must contain exactly 2 integers")
    return parsed


_MODIFIERS = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "win": "win",
    "windows": "win",
    # computer-use (xdotool / macOS) names
    "super": "win",
    "cmd": "win",
    "command": "win",
    "meta": "win",
    "option": "alt",
}


def _as_modifiers(value: list | str | None) -> list[str]:
    """Parse modifier keys given as "ctrl+shift", "ctrl, shift", ["ctrl", "shift"] or a JSON list.

    Plus signs, commas and spaces all separate; an empty value means no modifiers.
    """
    if value is None:
        return []
    if isinstance(value, str):
        if value.lstrip().startswith("["):
            value = json.loads(value)
        else:
            value = [token for token in re.split(r"[+,\s]+", value) if token]
    names = []
    for item in value:
        # "Control_L" / "Shift_R": either side holds the same modifier.
        token = (
            item.strip().lower().removesuffix("_l").removesuffix("_r")
            if isinstance(item, str)
            else None
        )
        key = _MODIFIERS.get(token)
        if key is None:
            raise ValueError(f"modifiers may only contain ctrl, shift, alt, win (got {item!r})")
        names.append(key)
    return list(dict.fromkeys(names))


def _focus_suffix(focus: object) -> str:
    """End a focused-Type reply: name the element and warn when it takes no text."""
    if not isinstance(focus, dict):
        return "."
    name = focus.get("name") or ""
    control_type = focus.get("control_type") or "element"
    described = f'{control_type} "{name}"' if name else control_type
    if focus.get("accepts_text"):
        return f" ({described})."
    return (
        f" ({described}). Warning: it takes no text (no ValuePattern or TextPattern), "
        "so the text may have gone nowhere."
    )


_TYPED_PREVIEW_CHARS = 50


def _typed_text(text: str) -> str:
    """The text as a Type reply names it: whole if short, else its length and start.

    Echoing a 1,000-character text back in full cost the caller as much as sending it.
    """
    if len(text) <= _TYPED_PREVIEW_CHARS:
        return text
    return f'{len(text):,} characters ("{text[:_TYPED_PREVIEW_CHARS]}...")'


def _held_suffix(modifiers: list[str]) -> str:
    return f" holding {'+'.join(modifiers)}" if modifiers else ""


def release_held_button(desktop) -> str:
    """Let go of a button left down by Move mouse_button='down'; the reply sentence, or ''."""
    if desktop.release_held_button() is True:
        return " Released the held left mouse button first."
    return ""


def _as_seconds(
    value: object, name: str, maximum: float | None = None, above: float | None = None
) -> float:
    """Parse a finite number of seconds (numbers or numeric strings).

    Zero is allowed unless *above* is given, which makes it an exclusive floor
    so every limit on the same argument is worded the same way.
    """
    try:
        if isinstance(value, bool):
            raise ValueError
        seconds = float(value)
    except TypeError, ValueError:
        raise ValueError(f"{name} must be a number of seconds (got {value!r})") from None
    too_small = seconds <= above if above is not None else seconds < 0
    if not math.isfinite(seconds) or too_small or (maximum is not None and seconds > maximum):
        floor = f"more than {above:g}" if above is not None else "0 or more"
        limit = f" and at most {maximum:g}" if maximum is not None else ""
        raise ValueError(f"{name} must be {floor}{limit} seconds (got {value!r})")
    return seconds


def _text_matches(value: object | None, expected: str | None) -> bool:
    if expected is None:
        return True
    if value is None:
        return False
    return expected.casefold() in str(value).casefold()


def _metadata_text_matches(metadata: dict[str, object], expected: str | None) -> bool:
    return any(_text_matches(value, expected) for value in metadata.values())


def _iter_nodes(desktop_state: Any) -> Iterator[Any]:
    tree_state = getattr(desktop_state, "tree_state", None)
    if tree_state is None:
        return
    yield from getattr(tree_state, "interactive_nodes", [])
    yield from getattr(tree_state, "scrollable_nodes", [])


def _iter_text_sources(desktop_state: Any) -> Iterator[object]:
    active_window = getattr(desktop_state, "active_window", None)
    if active_window is not None:
        yield active_window.name

    for window in getattr(desktop_state, "windows", []):
        yield window.name

    tree_state = getattr(desktop_state, "tree_state", None)
    if tree_state is None:
        return

    for node in _iter_nodes(desktop_state):
        yield node.name
        yield node.control_type
        yield node.window_name
        for value in getattr(node, "metadata", {}).values():
            yield value

    for node in getattr(tree_state, "dom_informative_nodes", []):
        yield getattr(node, "text", "")


def _node_matches(node: Any, text: str | None, window_name: str | None) -> bool:
    metadata: dict[str, object] = getattr(node, "metadata", {})
    return (
        _text_matches(getattr(node, "name", ""), text)
        or _text_matches(getattr(node, "control_type", ""), text)
        or _metadata_text_matches(metadata, text)
    ) and _text_matches(getattr(node, "window_name", ""), window_name)


def _text_window_handles(desktop_state: Any, window_name: str | None) -> list[int]:
    """Windows to search for static text: those matching window_name, else the active one."""
    active_window = getattr(desktop_state, "active_window", None)
    if window_name is None:
        return [active_window.handle] if active_window is not None else []
    windows = [active_window, *getattr(desktop_state, "windows", [])]
    handles = [w.handle for w in windows if w is not None and _text_matches(w.name, window_name)]
    return list(dict.fromkeys(handles))


def _off_screen_hint(desktop_state: Any, handles: list[int], desktop: Any) -> str:
    """Flag a match found only in windows parked outside every display.

    Tree elements are clipped to the displays, but the targeted text search and
    the active-window check read a window wherever it sits (e.g. at x=-3000),
    where nothing can be clicked.
    """
    if desktop is None or not handles:
        return ""
    windows = [
        getattr(desktop_state, "active_window", None),
        *getattr(desktop_state, "windows", []),
    ]
    # ponytail: judged by the window's center; a window mostly off-screen is flagged
    # even if an edge is still visible.
    centers = [
        w.bounding_box.get_center() for w in windows if w is not None and w.handle in handles
    ]
    if not centers or any(desktop.is_on_screen(c.x, c.y) for c in centers):
        return ""
    return " (window is off-screen)"


def _matches_wait_condition(
    desktop_state: Any,
    condition: WaitForCondition,
    text: str | None,
    window_name: str | None,
    desktop: Any = None,
) -> tuple[bool, str]:
    if condition == "text_exists":
        if window_name is None:
            sources = _iter_text_sources(desktop_state)
        else:
            sources = [
                n.name for n in _iter_nodes(desktop_state) if _node_matches(n, text, window_name)
            ]
            # DOM text carries no window name; it belongs to the active (browser) window.
            active_window = getattr(desktop_state, "active_window", None)
            tree_state = getattr(desktop_state, "tree_state", None)
            if active_window is not None and _text_matches(active_window.name, window_name):
                sources += [n.text for n in getattr(tree_state, "dom_informative_nodes", [])]
        for source in sources:
            if _text_matches(source, text):
                return True, f"text {text!r} appeared"
        handles = _text_window_handles(desktop_state, window_name)
        if desktop is not None and desktop.find_text(text, handles):
            hint = _off_screen_hint(desktop_state, handles, desktop)
            return True, f"text {text!r} appeared{hint}"
        return False, f"text {text!r} was absent"

    if condition == "active_window":
        expected = window_name or text
        active_window = getattr(desktop_state, "active_window", None)
        active_name = active_window.name if active_window else ""
        if _text_matches(active_name, expected):
            hint = _off_screen_hint(desktop_state, [active_window.handle], desktop)
            return True, f"active window matched {active_name!r}{hint}"
        return False, f"active window was {active_name!r}"

    if condition in {"element_exists", "element_enabled"}:
        for node in _iter_nodes(desktop_state):
            if _node_matches(node, text, window_name):
                return True, f"element matched {getattr(node, 'name', '')!r}"
        return False, "matching element was absent"

    if condition == "focused_element":
        for node in _iter_nodes(desktop_state):
            metadata = getattr(node, "metadata", {})
            if metadata.get("has_focused") and _node_matches(node, text, window_name):
                return True, f"focused element matched {getattr(node, 'name', '')!r}"
        return False, "matching focused element was absent"

    raise ValueError(f"Unsupported WaitFor condition: {condition}")


def _validate_wait_for_args(
    condition: str,
    text: str | None,
    window_name: str | None,
    timeout: float,
    interval: float,
) -> WaitForCondition:
    _validate_finite_number(timeout, "timeout")
    _validate_finite_number(interval, "interval")

    normalized = condition.strip().lower().replace("-", "_")
    aliases = {
        "text": "text_exists",
        "window": "active_window",
        "element": "element_exists",
        "enabled": "element_enabled",
        "focused": "focused_element",
    }
    normalized = aliases.get(normalized, normalized)
    valid_conditions = {
        "text_exists",
        "active_window",
        "element_exists",
        "element_enabled",
        "focused_element",
    }
    if normalized not in valid_conditions:
        raise ValueError(
            "condition must be one of: text_exists, active_window, element_exists, "
            "element_enabled, focused_element"
        )

    if timeout <= 0 or timeout > 120:
        raise ValueError("timeout must be greater than 0 and at most 120 seconds")
    if interval <= 0 or interval > 5:
        raise ValueError("interval must be greater than 0 and at most 5 seconds")

    if normalized == "text_exists" and not text:
        raise ValueError("text is required when condition is text_exists")
    if normalized == "active_window" and not (text or window_name):
        raise ValueError("text or window_name is required when condition is active_window")
    if normalized in {"element_exists", "element_enabled"} and not (text or window_name):
        raise ValueError(
            "text or window_name is required when condition is element_exists or element_enabled"
        )

    return normalized


_CLICK_NAMES = {0: "Hover", 1: "Single", 2: "Double", 3: "Triple"}


def register(
    mcp: Any,
    *,
    get_desktop: Callable[[], Any],
    get_analytics: Callable[[], Any],
) -> None:
    @mcp.tool(
        name="Click",
        description=(
            "Performs mouse clicks at specified coordinates [x, y] or passing a UI element's label/id. "
            "Supports button types: 'left' for selection/activation, 'right' for context menus, 'middle'. "
            "Supports clicks: 0=hover only (no click), 1=single click (select/focus), 2=double click (open/activate), "
            "3=triple click (select a line/paragraph). "
            "Provide loc or label; with neither, clicks at the current mouse position. "
            "modifiers holds keys during the click, e.g. 'shift' to extend a selection, "
            "'ctrl' to add to it or open a link in a new tab, 'ctrl+shift'. "
            "Allowed: ctrl, shift, alt, win (aliases: control, windows, super, cmd, command, "
            "meta, option), separated by +, a comma or a space. Not allowed with clicks=0, which only moves the pointer."
        ),
        annotations=ToolAnnotations(
            title="Click",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "Click-Tool")
    def click_tool(
        loc: list[int] | str | None = None,
        label: int | None = None,
        button: Literal["left", "right", "middle"] = "left",
        clicks: int = 1,
        modifiers: list[str] | str | None = None,
        ctx: Context = None,
    ) -> str:
        if type(clicks) is not int or clicks not in _CLICK_NAMES:
            raise ValueError(f"clicks must be 0, 1, 2 or 3 (got {clicks!r})")
        modifiers = _as_modifiers(modifiers)
        # A hover never presses the keys, so accepting them would report a hold that never happened.
        if clicks == 0 and modifiers:
            raise ValueError("modifiers cannot be used with clicks=0 (a hover holds no keys)")
        desktop = get_desktop()
        loc = _as_loc(loc)
        if label is not None:
            loc = _resolve_label(desktop, label)
        elif loc is None:
            loc = list(desktop.get_cursor_location())
        if len(loc) != 2:
            raise ValueError("Location must be a list of exactly 2 integers [x, y]")
        x, y = loc[0], loc[1]
        # clicks=0 only moves the pointer, which is how a held drag is steered.
        released = release_held_button(desktop) if clicks else ""
        desktop.click(loc=loc, button=button, clicks=clicks, modifiers=modifiers)
        if clicks == 0:
            return f"Moved to ({x},{y}) (hover)."
        return (
            f"{_CLICK_NAMES[clicks]} {button} clicked at ({x},{y}){_held_suffix(modifiers)}."
            f"{released}"
        )

    @mcp.tool(
        name="Type",
        description="Types text at specified coordinates [x, y] or passing a UI element's label/id. Set clear=True to clear existing text first, False to append. Set press_enter=True to submit after typing. Set caret_position to 'start' (beginning), 'end' (end), or 'idle' (default). Provide loc or label to click the field first; with neither, types into the element that already has keyboard focus (no click, so the caret and selection stay put).",
        annotations=ToolAnnotations(
            title="Type",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "Type-Tool")
    def type_tool(
        text: str,
        loc: list[int] | str | None = None,
        label: int | None = None,
        clear: bool | str = False,
        caret_position: Literal["start", "idle", "end"] = "idle",
        press_enter: bool | str = False,
        ctx: Context = None,
    ) -> str:
        desktop = get_desktop()
        loc = _as_loc(loc)
        if label is not None:
            loc = _resolve_label(desktop, label)
        if loc is not None and len(loc) != 2:
            raise ValueError("Location must be a list of exactly 2 integers [x, y]")
        # Only a located Type clicks; typing into the focused element leaves a drag alone.
        released = release_held_button(desktop) if loc is not None else ""
        # Read the focus before typing: typing can move it (Tab, Enter in a form).
        focus = desktop.describe_focused_element() if loc is None else None
        clear = as_bool(clear, "clear")
        press_enter = as_bool(press_enter, "press_enter")
        desktop.type(
            loc=loc,
            text=text,
            caret_position=caret_position,
            clear=clear,
            press_enter=press_enter,
        )
        typed = _typed_text(text)
        done = " Cleared the existing text first." if clear else ""
        done += " Pressed Enter." if press_enter else ""
        if loc is None:
            return f"Typed {typed} into the focused element{_focus_suffix(focus)}{done}"
        return f"Typed {typed} at ({loc[0]},{loc[1]}).{done}{released}"

    @mcp.tool(
        name="Scroll",
        description="Scrolls at coordinates [x, y], a UI element's label/id, or current mouse position if loc=None. Type: vertical (default) or horizontal. Direction: up/down for vertical, left/right for horizontal. wheel_times controls amount, 1 or more (1 wheel ≈ 3-5 lines). Use for navigating long content, lists, and web pages. modifiers holds keys while scrolling, e.g. 'ctrl' with up/down to zoom a page or document (allowed: ctrl, shift, alt, win; aliases: control, windows, super, cmd, command, meta, option; separated by +, a comma or a space).",
        annotations=ToolAnnotations(
            title="Scroll",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "Scroll-Tool")
    def scroll_tool(
        loc: list[int] | str | None = None,
        label: int | None = None,
        type: Literal["horizontal", "vertical"] = "vertical",
        direction: Literal["up", "down", "left", "right"] = "down",
        wheel_times: int = 1,
        modifiers: list[str] | str | None = None,
        ctx: Context = None,
    ) -> str:
        # isinstance, not type(): the `type` parameter above shadows the builtin here.
        if isinstance(wheel_times, bool) or not isinstance(wheel_times, int) or wheel_times < 1:
            raise ValueError(f"wheel_times must be 1 or more (got {wheel_times!r})")
        modifiers = _as_modifiers(modifiers)
        desktop = get_desktop()
        loc = _as_loc(loc)
        if label is not None:
            loc = _resolve_label(desktop, label)
        if loc and len(loc) != 2:
            raise ValueError("Location must be a list of exactly 2 integers [x, y]")
        released = release_held_button(desktop)
        response = desktop.scroll(loc, type, direction, wheel_times, modifiers=modifiers)
        if response:
            return f"{response}{released}"
        where = f" at ({loc[0]},{loc[1]})" if loc else " at the mouse position"
        return (
            f"Scrolled {type} {direction} by {wheel_times} wheel times"
            f"{where}{_held_suffix(modifiers)}.{released}"
        )

    @mcp.tool(
        name="Move",
        description=(
            "Moves mouse cursor to coordinates [x, y] or passing a UI element's label/id. "
            "Set drag=True to perform a drag-and-drop operation from the current mouse position "
            "to the target coordinates, or provide from_loc=[x, y] to make the drag explicit-start "
            "and atomic in one tool call. Optional duration controls bounded intermediate movement. "
            "Default (drag=False) is a simple cursor move (hover). "
            "Provide either loc or label. "
            "modifiers (drag only) holds keys during the drag, e.g. 'ctrl' to copy instead of move. "
            "For drags one straight move can't express (curved paths, hover before dropping): "
            "mouse_button='down' presses the left button at loc, then plain Moves steer it, "
            "then mouse_button='up' releases it (loc optional: current position). "
            "Always finish a 'down' with an 'up'; any click, scroll or drag releases it first."
        ),
        annotations=ToolAnnotations(
            title="Move",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "Move-Tool")
    def move_tool(
        loc: list[int] | str | None = None,
        label: int | None = None,
        drag: bool | str = False,
        from_loc: list[int] | str | None = None,
        duration: float | int | str | None = None,
        modifiers: list[str] | str | None = None,
        mouse_button: Literal["down", "up"] | None = None,
        ctx: Context = None,
    ) -> str:
        desktop = get_desktop()
        loc = _as_loc(loc)
        from_loc = _as_loc(from_loc)
        drag = as_bool(drag, "drag")
        modifiers = _as_modifiers(modifiers)
        if modifiers and not drag:
            raise ValueError(
                "modifiers require drag=True (use Click or Scroll modifiers otherwise)"
            )
        if mouse_button is not None:
            if mouse_button not in ("down", "up"):
                raise ValueError(f"mouse_button must be 'down' or 'up' (got {mouse_button!r})")
            if drag or from_loc is not None or duration is not None:
                raise ValueError("mouse_button cannot be combined with drag, from_loc or duration")
            if label is not None:
                loc = _resolve_label(desktop, label)
            elif loc is None:
                loc = list(desktop.get_cursor_location())
            loc = _as_point(loc, "loc")
            if not desktop.mouse_button(loc, mouse_button):
                return "No mouse button was held; nothing was sent."
            verb = "Pressed" if mouse_button == "down" else "Released"
            return f"{verb} the left mouse button at ({loc[0]},{loc[1]})."
        if loc is None and label is None:
            raise ValueError("Either loc or label must be provided.")
        if label is not None:
            loc = _resolve_label(desktop, label)
        if not isinstance(loc, list) or len(loc) != 2:
            raise ValueError("loc must be a list of exactly 2 integers [x, y]")
        if from_loc is not None and (not isinstance(from_loc, list) or len(from_loc) != 2):
            raise ValueError("from_loc must be a list of exactly 2 integers [x, y]")
        has_drag_only_options = any(
            value is not None
            for value in (
                from_loc,
                duration,
            )
        )
        if has_drag_only_options and not drag:
            raise ValueError("from_loc and duration require drag=True")
        if drag:
            loc = _as_point(loc, "loc")
            if from_loc is not None:
                from_loc = _as_point(from_loc, "from_loc")
        x, y = loc[0], loc[1]
        if drag:
            released = release_held_button(desktop)
            result = desktop.drag(
                loc,
                from_loc=from_loc,
                duration=duration,
                modifiers=modifiers,
            )
            start_x, start_y = result["start"]
            effective_duration = result["duration"]
            held = _held_suffix(modifiers)
            if effective_duration is None:
                return f"Dragged from ({start_x},{start_y}) to ({x},{y}){held}.{released}"
            return (
                f"Dragged from ({start_x},{start_y}) to ({x},{y}) "
                f"over {effective_duration:.3f} seconds{held}.{released}"
            )
        else:
            desktop.move(loc)
            return f"Moved the mouse pointer to ({x},{y})."

    @mcp.tool(
        name="Shortcut",
        description='Executes keyboard shortcuts using key combinations separated by +. Examples: "ctrl+c" (copy), "ctrl+v" (paste), "alt+tab" (switch apps), "win+r" (Run dialog), "win" (Start menu), "ctrl+shift+esc" (Task Manager), "ctrl++" or "ctrl+plus" (zoom in). xdotool key names work too (Return, Page_Down, KP_Enter, super, cmd). Punctuation can be named: plus, minus, equal, comma, period, slash, backslash, semicolon, quote, grave, bracketleft, bracketright, braceleft, braceright. Use for quick actions and system commands. repeat=N presses the combination N times (1-100), e.g. "down" with repeat=20. hold=S keeps all the keys down for S seconds (up to 10), e.g. an arrow key in a game; a held key does not auto-repeat typed characters, so use repeat for that. hold and repeat cannot be combined.',
        annotations=ToolAnnotations(
            title="Shortcut",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "Shortcut-Tool")
    def shortcut_tool(
        shortcut: str,
        repeat: int = 1,
        hold: float | str | None = None,
        ctx: Context = None,
    ):
        if type(repeat) is not int or not 1 <= repeat <= 100:
            raise ValueError(f"repeat must be a whole number from 1 to 100 (got {repeat!r})")
        if hold is not None:
            hold = _as_seconds(hold, "hold", maximum=10, above=0)
            if repeat != 1:
                raise ValueError("hold and repeat cannot be combined")
        get_desktop().shortcut(shortcut, repeat=repeat, hold=hold)
        if hold is not None:
            return f"Held {shortcut} for {hold:g} seconds."
        return f"Pressed {shortcut}" + (f" {repeat} times." if repeat > 1 else ".")

    @mcp.tool(
        name="Wait",
        description="Pauses execution for specified duration in seconds (decimals allowed, e.g. 0.5; at most 300). Use when waiting for: applications to launch/load, UI animations to complete, page content to render, dialogs to appear, or between rapid actions. Helps ensure UI is ready before next interaction.",
        annotations=ToolAnnotations(
            title="Wait",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "Wait-Tool")
    def wait_tool(duration: float | str, ctx: Context = None) -> str:
        # Capped so a typo (600 for 6.00) or a huge value can't block the server for long.
        seconds = _as_seconds(duration, "duration", maximum=300)
        time.sleep(seconds)
        return f"Waited for {seconds:g} seconds."

    @mcp.tool(
        name="WaitFor",
        description=(
            "Waits until a UI condition is satisfied, polling the Windows accessibility tree "
            "inside the tool to avoid repeated Snapshot calls. Conditions: text_exists, "
            "active_window, element_exists, element_enabled, focused_element. Provide text "
            "and/or window_name depending on the condition. Set use_dom=True for browser DOM text."
        ),
        annotations=ToolAnnotations(
            title="WaitFor",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "WaitFor-Tool")
    def wait_for_tool(
        condition: str,
        text: str | None = None,
        window_name: str | None = None,
        timeout: float = 10.0,
        interval: float = 0.25,
        use_dom: bool | str = False,
        ctx: Context = None,
    ) -> str:
        normalized = _validate_wait_for_args(
            condition=condition,
            text=text,
            window_name=window_name,
            timeout=timeout,
            interval=interval,
        )
        desktop = get_desktop()
        use_dom_bool = as_bool(use_dom, "use_dom")
        started_at = time.monotonic()
        deadline = started_at + timeout
        attempts = 0
        last_detail = "condition was not evaluated"

        while True:
            attempts += 1
            desktop_state = desktop.get_state(
                use_vision=False,
                use_dom=use_dom_bool,
                use_ui_tree=True,
                use_annotation=False,
            )
            matched, last_detail = _matches_wait_condition(
                desktop_state=desktop_state,
                condition=normalized,
                text=text,
                window_name=window_name,
                desktop=desktop,
            )
            if matched:
                elapsed = time.monotonic() - started_at
                return (
                    f"WaitFor condition '{normalized}' satisfied after "
                    f"{elapsed:.2f}s and {attempts} attempt(s): {last_detail}."
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"Timed out after {timeout:.2f}s waiting for '{normalized}': {last_detail}."
                )
            time.sleep(min(interval, remaining))
