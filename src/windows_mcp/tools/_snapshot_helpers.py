"""Snapshot / Screenshot shared helpers.

These functions were originally defined in ``__main__.py`` and are now shared
by the Snapshot and Screenshot tool modules.
"""

import io
import json
import logging
import os
import time

from fastmcp.utilities.types import Image
from textwrap import dedent
from windows_mcp.desktop.service import Desktop, Size
from windows_mcp.desktop.utils import remove_private_use_chars, repair_surrogates
from windows_mcp.tools._coords import coordinate_scale, raw_coordinates, to_screen


logger = logging.getLogger(__name__)

MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT = 1920, 1080
ZOOM_WIDTH = 1280  # a zoomed region is fitted into ZOOM_WIDTH x MAX_IMAGE_HEIGHT


def _zoom_scale(region: list | None) -> float:
    """Factor that fits a screen-pixel region into the zoom box (up or down)."""
    if not (isinstance(region, list) and len(region) == 4):
        return 1.0  # malformed: get_state reports it
    left, top, right, bottom = region
    if not all(isinstance(v, int) for v in region) or right <= left or bottom <= top:
        return 1.0
    return min(ZOOM_WIDTH / (right - left), MAX_IMAGE_HEIGHT / (bottom - top))


WINDOW_LIST_SKIPPED = "Skipped (screenshot-only; call Snapshot to list windows)"


def _screenshot_scale() -> float:
    value = os.getenv("WINDOWS_MCP_SCREENSHOT_SCALE", "1.0")
    try:
        scale = float(value)
    except ValueError:
        logger.warning("Invalid WINDOWS_MCP_SCREENSHOT_SCALE value %r, using 1.0", value)
        scale = 1.0
    if not (0.1 <= scale <= 1.0):
        logger.warning("WINDOWS_MCP_SCREENSHOT_SCALE %r out of range [0.1, 1.0], clamping", scale)
        scale = max(0.1, min(1.0, scale))
    return scale


def _snapshot_profile_enabled() -> bool:
    value = os.getenv("WINDOWS_MCP_PROFILE_SNAPSHOT", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_region(value: list | str | None) -> list | None:
    """Accept region as a list, a JSON array string, or "left,top,right,bottom" text."""
    if value is None or isinstance(value, list):
        return value
    text = value.strip()
    if not text:
        return None
    try:
        if text.startswith("["):
            return json.loads(text)
        return [int(part) for part in text.split(",")]
    except ValueError:  # JSONDecodeError is a ValueError too
        raise ValueError(
            f'region must be [left, top, right, bottom] or "left,top,right,bottom" (got {value!r})'
        ) from None


MAX_GRID_CELLS = 100  # 1920 px / 100 = 19 px cells; thousands turned the image solid grey


def _as_grid_count(value: int | str | None, name: str) -> int | None:
    if value is None:
        return None
    try:
        count = int(value)
    except TypeError, ValueError:
        count = 0
    if not 1 <= count <= MAX_GRID_CELLS:
        raise ValueError(
            f"{name} must be a whole number from 1 to {MAX_GRID_CELLS} (got {value!r})"
        )
    return count


def capture_desktop_state(
    desktop: Desktop,
    *,
    use_vision: bool,
    use_dom: bool,
    use_annotation: bool,
    use_ui_tree: bool,
    width_reference_line: int | None,
    height_reference_line: int | None,
    display: list[int] | None,
    region: list[int] | None,
    tool_name: str,
    zoom: bool = False,
):
    profile_enabled = _snapshot_profile_enabled()
    profile_started_at = time.perf_counter()
    stage_started_at = profile_started_at
    desktop_state_ms = 0.0
    metadata_render_ms = 0.0
    screenshot_encode_ms = 0.0

    if use_dom and not use_ui_tree:
        raise ValueError("use_dom=True requires use_ui_tree=True")

    display_indices = Desktop.parse_display_selection(display)

    # Either reference line alone is enough; the missing direction gets no lines.
    width_reference_line = _as_grid_count(width_reference_line, "width_reference_line")
    height_reference_line = _as_grid_count(height_reference_line, "height_reference_line")
    grid_lines = None
    if width_reference_line or height_reference_line:
        grid_lines = (width_reference_line or 1, height_reference_line or 1)

    screen_region = to_screen(desktop, region, count=4)
    image_scale = _screenshot_scale()
    max_image_size = Size(width=MAX_IMAGE_WIDTH, height=MAX_IMAGE_HEIGHT)
    if zoom:
        # Round-2 B.4: full resolution, enlarged so small text is legible; the size cap
        # would clamp the enlargement back to 1.
        image_scale, max_image_size = _zoom_scale(screen_region), None

    desktop_state = desktop.get_state(
        use_vision=use_vision,
        use_dom=use_dom,
        use_annotation=use_annotation,
        use_ui_tree=use_ui_tree,
        as_bytes=False,
        scale=image_scale,
        grid_lines=grid_lines,
        display_indices=display_indices,
        region=screen_region,
        max_image_size=max_image_size,
    )
    if profile_enabled:
        desktop_state_ms = (time.perf_counter() - stage_started_at) * 1000
        stage_started_at = time.perf_counter()

    # A full screenshot sets the caller's coordinate space (round-2 B.1); a region is a
    # close-up of it and leaves the space alone, like computer use's zoom.
    if use_vision and region is None and not raw_coordinates():
        desktop.coordinate_scale = desktop_state.screenshot_scale or 1.0
    scale = coordinate_scale(desktop)
    image_origin = None
    if desktop_state.screenshot_original_size:
        box = desktop_state.screenshot_region or desktop.get_screen_box()
        image_origin = (box.left, box.top)

    interactive_elements = desktop_state.tree_state.interactive_elements_to_string(scale)
    scrollable_elements = desktop_state.tree_state.scrollable_elements_to_string(scale)
    semantic_tree = desktop_state.tree_state.semantic_tree_to_string(scale)
    if use_ui_tree:
        windows = desktop_state.windows_to_string()
        active_window = desktop_state.active_window_to_string()
    else:
        # Windows are not enumerated on the fast path; "No windows found" would be false.
        windows = active_window = WINDOW_LIST_SKIPPED
    active_desktop = desktop_state.active_desktop_to_string()
    all_desktops = desktop_state.desktops_to_string()
    if profile_enabled:
        metadata_render_ms = (time.perf_counter() - stage_started_at) * 1000
        stage_started_at = time.perf_counter()

    screenshot_bytes = None
    if use_vision and desktop_state.screenshot is not None:
        buffered = io.BytesIO()
        desktop_state.screenshot.save(buffered, format="PNG")
        screenshot_bytes = buffered.getvalue()
        buffered.close()
    if profile_enabled:
        screenshot_encode_ms = (time.perf_counter() - stage_started_at) * 1000
        logger.info(
            "%s profile: desktop_state_ms=%.1f metadata_render_ms=%.1f png_encode_ms=%.1f total_ms=%.1f use_vision=%s use_dom=%s use_ui_tree=%s use_annotation=%s display=%s",
            tool_name,
            desktop_state_ms,
            metadata_render_ms,
            screenshot_encode_ms,
            (time.perf_counter() - profile_started_at) * 1000,
            use_vision,
            use_dom,
            use_ui_tree,
            use_annotation,
            display,
        )

    return {
        "desktop_state": desktop_state,
        "interactive_elements": interactive_elements,
        "scrollable_elements": scrollable_elements,
        "semantic_tree": semantic_tree,
        "windows": windows,
        "active_window": active_window,
        "active_desktop": active_desktop,
        "all_desktops": all_desktops,
        "screenshot_bytes": screenshot_bytes,
        "coordinate_scale": scale,
        "image_origin": image_origin,
    }


_SPACE_USERS = (
    "element, cursor and display positions here and the loc, locs, from_loc and region you pass"
)


def _image_mapping_text(desktop_state, origin: tuple[int, int], scale: float) -> str:
    """Size of the image and how its pixels map to the caller's coordinates."""
    orig = desktop_state.screenshot_original_size
    applied = desktop_state.screenshot_scale or 1.0
    text = f"Screenshot Size: {orig.to_string()}\n"
    if applied != 1.0:
        text = (
            f"Screenshot Original Size: {orig.to_string()}\n"
            f"Image Size: {round(orig.width * applied)}x{round(orig.height * applied)}\n"
        )
    ratio = round(scale / applied, 6)
    left, top = round(origin[0] * scale), round(origin[1] * scale)
    if ratio == 1.0 and (left, top) == (0, 0):
        if scale == 1.0:
            return text
        return text + (
            f"Coordinates: image pixels as seen (screen pixels x {scale:g}); "
            f"{_SPACE_USERS} use them\n"
        )
    return text + (
        f"Coordinates: image pixel (x, y) = ({left} + x*{ratio:g}, {top} + y*{ratio:g}) "
        f"in the coordinates {_SPACE_USERS} use\n"
    )


def build_snapshot_response(
    capture_result: dict[str, object],
    *,
    include_ui_details: bool,
    ui_detail_note: str | None = None,
):
    desktop_state = capture_result["desktop_state"]
    interactive_elements = capture_result["interactive_elements"]
    scrollable_elements = capture_result["scrollable_elements"]
    semantic_tree = capture_result["semantic_tree"]
    windows = capture_result["windows"]
    active_window = capture_result["active_window"]
    active_desktop = capture_result["active_desktop"]
    all_desktops = capture_result["all_desktops"]
    screenshot_bytes = capture_result["screenshot_bytes"]

    # Some applications (e.g. VS Code) embed Unicode Private Use Area characters in the
    # Automation Element Name property of certain UI elements (e.g. navigation bar items in VS Code).
    # These characters can cause display issues, so we strip them out before rendering.
    interactive_elements = remove_private_use_chars(interactive_elements)
    scrollable_elements = remove_private_use_chars(scrollable_elements)
    semantic_tree = remove_private_use_chars(semantic_tree)

    # Emoji reach us from UIA as raw UTF-16 surrogate pairs. Left alone they make
    # the strict UTF-8 JSON encoder reject the entire response, so every string
    # heading into it is repaired -- window titles included, since an emoji in a
    # window title is enough to take the whole snapshot down.
    interactive_elements = repair_surrogates(interactive_elements)
    scrollable_elements = repair_surrogates(scrollable_elements)
    semantic_tree = repair_surrogates(semantic_tree)
    windows = repair_surrogates(windows)
    active_window = repair_surrogates(active_window)
    active_desktop = repair_surrogates(active_desktop)
    all_desktops = repair_surrogates(all_desktops)

    scale = capture_result.get("coordinate_scale", 1.0)

    def box_to_string(box):
        return "({},{},{},{})".format(*(round(v * scale) for v in box.convert_xywh_to_xyxy()))

    def display_to_string(display):
        primary = " primary" if display.primary else ""
        return (
            f"{display.index}:{display.device_name} {box_to_string(display.bounding_box)}{primary}"
        )

    # get_state drops a cursor that lies outside the region (it would be drawn off the image).
    cursor = desktop_state.cursor_position
    if cursor is None:
        cursor = "outside region" if desktop_state.screenshot_region else "unknown"
    else:
        cursor = (round(cursor[0] * scale), round(cursor[1] * scale))
    metadata_text = f"Cursor Position: {cursor}\n"
    zoomed = (desktop_state.screenshot_scale or 1.0) > 1.0  # the old hint only covers shrinking
    if desktop_state.screenshot_original_size and (zoomed or not raw_coordinates()):
        metadata_text += _image_mapping_text(
            desktop_state, capture_result.get("image_origin") or (0, 0), scale
        )
    elif desktop_state.screenshot_original_size:
        orig = desktop_state.screenshot_original_size
        applied = desktop_state.screenshot_scale or 1.0
        if applied < 1.0:
            coord_scale = round(1.0 / applied, 6)
            metadata_text += (
                f"Screenshot Original Size: {orig.to_string()}\n"
                f"Screenshot Coordinate Scale: {coord_scale} "
                f"— image pixels are downscaled; multiply every image pixel coordinate by "
                f"{coord_scale} before passing to Click, Move, Scroll, or any loc= argument "
                f"(e.g. image pixel (200, 150) → screen coordinate ({round(200 * coord_scale)}, {round(150 * coord_scale)}))\n"
            )
        else:
            metadata_text += f"Screenshot Size: {orig.to_string()}\n"
    elif scale != 1.0:
        metadata_text += (
            f"Coordinates: screen pixels x {scale:g}, the space of the last full screenshot; "
            f"{_SPACE_USERS} use it\n"
        )
    if desktop_state.available_displays:
        metadata_text += "Visible Displays: "
        metadata_text += "; ".join(
            display_to_string(display) for display in desktop_state.available_displays
        )
        metadata_text += "\n"
    if desktop_state.screenshot_displays:
        metadata_text += f"Selected Displays: {','.join(str(index) for index in desktop_state.screenshot_displays)}\n"
    if desktop_state.screenshot_region:
        metadata_text += f"Screenshot Region: {box_to_string(desktop_state.screenshot_region)}\n"
        if scale == 1.0:
            metadata_text += "Coordinate Space: Virtual desktop coordinates\n"
    if desktop_state.screenshot_backend:
        metadata_text += f"Screenshot Backend: {desktop_state.screenshot_backend}\n"
    if ui_detail_note:
        metadata_text += f"{ui_detail_note}\n"

    response_text = dedent(f"""
    {metadata_text}
    Active Desktop:
    {active_desktop}

    All Desktops:
    {all_desktops}

    Focused Window:
    {active_window}

    Opened Windows:
    {windows}
    """)
    if include_ui_details:
        response_text += dedent(f"""

    UI Tree:
    {semantic_tree or "No elements found."}""")

    response = [response_text]
    if screenshot_bytes:
        response.append(Image(data=screenshot_bytes, format="png"))
    return response
