"""Coordinates in the pixel space of the last full screenshot (round-2 B.1).

A full screenshot shrunk by ``s`` (big screens, WINDOWS_MCP_SCREENSHOT_SCALE) makes
``s`` the caller's coordinate scale: a point the caller names is at screen = point / ``s``,
and every position we print is screen * ``s``. At ``s == 1``
nothing changes. WINDOWS_MCP_RAW_COORDINATES keeps plain screen pixels throughout.
"""

import os
from typing import Any


def raw_coordinates() -> bool:
    """True when the caller opted out and speaks plain screen pixels."""
    value = os.getenv("WINDOWS_MCP_RAW_COORDINATES", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def coordinate_scale(desktop: Any) -> float:
    scale = getattr(desktop, "coordinate_scale", 1.0)
    return scale if isinstance(scale, (int, float)) and scale > 0 else 1.0


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str) and value.strip().lstrip("+-").isdigit():
        return int(value)
    return None


def _scaled(values: list, factor: float, count: int) -> list:
    # Only the first `count` items are coordinates (MultiEdit's third is text); anything
    # that is not a number passes through for the tool's usual validation.
    out = list(values)
    for i in range(min(count, len(out))):
        number = _number(out[i])
        if number is not None:
            out[i] = round(number * factor)
    return out


def to_screen(desktop: Any, values: list | None, count: int = 2) -> list | None:
    """Caller coordinates (a point, [x, y, text], or a region with count=4) to screen pixels."""
    scale = coordinate_scale(desktop)
    if not isinstance(values, list) or scale == 1.0:
        return values
    return _scaled(values, 1.0 / scale, count)


def to_model(desktop: Any, point: tuple | list, count: int = 2) -> tuple:
    """Screen pixels to the caller's coordinates, for replies."""
    return tuple(_scaled(list(point), coordinate_scale(desktop), count))
