"""Snapshot and Screenshot tools — desktop state capture."""

import logging

from mcp.types import ToolAnnotations
from windows_mcp.infrastructure import with_analytics
from fastmcp import Context
from fastmcp.exceptions import ToolError
from windows_mcp.tools._args import as_bool

from windows_mcp.tools._snapshot_helpers import (
    _as_region,
    capture_desktop_state,
    build_snapshot_response,
)

logger = logging.getLogger(__name__)

# Populated by register(); exposed for backward-compatible test imports.
state_tool = None
screenshot_tool = None


def _retry_hint(error: Exception) -> str:
    """Suggest a retry only for capture failures; a bad option fails the same way again."""
    return "" if isinstance(error, ValueError) else " Please try again."


def register(mcp, *, get_desktop, get_analytics):
    global state_tool, screenshot_tool

    @mcp.tool(
        name="Snapshot",
        description="Take a screenshot and inspect the screen. Keywords: screenshot, screen capture, see screen, observe, look, inspect, UI elements, what's on screen. Captures the desktop state: focused/opened windows, interactive elements (buttons, text fields, links, menus with coordinates), and scrollable areas. Set use_vision=True to include screenshot with cursor highlight. Set use_annotation=False to get a clean screenshot without bounding box overlays on UI elements (default: True, draws colored rectangles around detected elements). Set use_ui_tree=False for a faster screenshot-only snapshot when you do not need interactive or scrollable element extraction. Set width_reference_line/height_reference_line (1-100 cells across/down) to overlay a grid for better spatial reasoning (make sure vision is enabled to use it). Set use_dom=True for browser content to get web page elements instead of browser UI. Set display=[0] or display=[0,1] using zero-based active Windows display indices; omit it to keep the default full-desktop behavior. Set region=[left, top, right, bottom] (same coordinates as Click; see the reply's Coordinates line) to capture and inspect only that rectangle instead of the whole screen/display — useful when you already know which area matters and want to save tokens; region takes precedence over display when both are given, and an invalid or out-of-bounds region raises an error rather than silently capturing something else. Use it when you need element labels, the window list or browser DOM; for a quick look, Screenshot is faster.",
        annotations=ToolAnnotations(
            title="Snapshot",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "State-Tool")
    def _state_tool(
        use_vision: bool | str = False,
        use_dom: bool | str = False,
        use_annotation: bool | str = True,
        use_ui_tree: bool | str = True,
        width_reference_line: int | None = None,
        height_reference_line: int | None = None,
        display: list[int] | None = None,
        region: list[int] | str | None = None,
        ctx: Context = None,
    ):
        use_vision = as_bool(use_vision, "use_vision")
        use_ui_tree = as_bool(use_ui_tree, "use_ui_tree")
        if not use_vision and not use_ui_tree:
            raise ValueError(
                "use_ui_tree and use_vision cannot both be false: that returns neither "
                "elements nor an image"
            )
        desktop = get_desktop()
        try:
            capture_result = capture_desktop_state(
                desktop,
                use_vision=use_vision,
                use_dom=as_bool(use_dom, "use_dom"),
                use_annotation=as_bool(use_annotation, "use_annotation"),
                use_ui_tree=use_ui_tree,
                width_reference_line=width_reference_line,
                height_reference_line=height_reference_line,
                display=display,
                region=_as_region(region),
                tool_name="Snapshot tool",
            )
        except Exception as e:
            logger.warning(
                "Snapshot failed with display=%s region=%s use_vision=%s use_dom=%s",
                display,
                region,
                use_vision if "use_vision" in locals() else None,
                use_dom if "use_dom" in locals() else None,
                exc_info=True,
            )
            # Raised, not returned: a returned message reached the client as a success.
            raise ToolError(f"Error capturing desktop state: {e}.{_retry_hint(e)}") from e

        # Label clicks resolve against exactly the tree printed here, never a later capture.
        desktop.label_tree_state = capture_result["desktop_state"].tree_state
        return build_snapshot_response(capture_result, include_ui_details=True)

    @mcp.tool(
        name="Screenshot",
        description="Captures a fast screenshot-first desktop snapshot with cursor position, desktop/window summaries, and an image. This path skips UI tree extraction for speed. Use Snapshot when you need interactive element ids, scrollable regions, or browser DOM extraction. Set display=[0] or display=[0,1] using zero-based active Windows display indices to capture only those monitors. Set region=[left, top, right, bottom] (same coordinates as Click; see the reply's Coordinates line) to capture only that rectangle instead of the whole screen/display — useful when you already know which area matters and want to save tokens; region takes precedence over display when both are given, and an invalid or out-of-bounds region raises an error rather than silently capturing something else. The image may be downscaled for efficiency; a full (non-region) screenshot makes its own pixels the coordinates every loc takes, so click where you see things. Set zoom=True with a region to enlarge it to about 1280 px wide at full resolution, so small text is legible. A region image is a close-up: its reply says how its pixels map (server setting WINDOWS_MCP_RAW_COORDINATES=1 keeps plain screen pixels).",
        annotations=ToolAnnotations(
            title="Screenshot",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "Screenshot-Tool")
    def _screenshot_tool(
        use_annotation: bool | str = False,
        width_reference_line: int | None = None,
        height_reference_line: int | None = None,
        display: list[int] | None = None,
        region: list[int] | str | None = None,
        zoom: bool | str = False,
        ctx: Context = None,
    ):
        if as_bool(use_annotation, "use_annotation"):
            raise ValueError(
                "use_annotation needs UI elements, which Screenshot skips; use Snapshot instead"
            )
        zoom = as_bool(zoom, "zoom")
        region = _as_region(region)
        if zoom and region is None:
            raise ValueError("zoom needs a region=[left, top, right, bottom] to enlarge")
        try:
            capture_result = capture_desktop_state(
                get_desktop(),
                use_vision=True,
                use_dom=False,
                use_annotation=False,
                use_ui_tree=False,
                width_reference_line=width_reference_line,
                height_reference_line=height_reference_line,
                display=display,
                region=region,
                tool_name="Screenshot tool",
                zoom=zoom,
            )
        except Exception as e:
            logger.warning(
                "Screenshot failed with display=%s region=%s",
                display,
                region,
                exc_info=True,
            )
            raise ToolError(f"Error capturing screenshot: {e}.{_retry_hint(e)}") from e

        return build_snapshot_response(
            capture_result,
            include_ui_details=False,
            ui_detail_note="UI Tree: Skipped for fast screenshot-only capture. Call Snapshot when you need interactive or scrollable elements.",
        )

    state_tool = _state_tool
    screenshot_tool = _screenshot_tool
