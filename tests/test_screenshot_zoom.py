"""Round-2 B.4: Screenshot zoom=true enlarges a small region so its text is legible."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from windows_mcp.desktop.service import Desktop
from windows_mcp.desktop.views import DesktopState, Size
from windows_mcp.tools import snapshot as snapshot_tools
from windows_mcp.tools._snapshot_helpers import (
    ZOOM_WIDTH,
    build_snapshot_response,
    capture_desktop_state,
)
from windows_mcp.tree.views import BoundingBox, TreeState


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _screenshot_tool(desktop):
    mcp = FakeMCP()
    snapshot_tools.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return mcp.tools["Screenshot"]


def _capture(desktop, region, zoom=True):
    return capture_desktop_state(
        desktop,
        use_vision=True,
        use_dom=False,
        use_annotation=False,
        use_ui_tree=False,
        width_reference_line=None,
        height_reference_line=None,
        display=None,
        region=region,
        tool_name="test",
        zoom=zoom,
    )


def _mock_desktop(scale=1.0):
    desktop = MagicMock()
    desktop.coordinate_scale = scale
    desktop.get_state.return_value = DesktopState(
        active_desktop={"name": "Desktop 1"},
        all_desktops=[{"name": "Desktop 1"}],
        active_window=None,
        windows=[],
        screenshot_original_size=Size(width=20, height=10),
        screenshot_scale=64.0,
        screenshot_region=BoundingBox(100, 200, 120, 210, 20, 10),
        tree_state=TreeState(),
    )
    return desktop


def test_zoom_without_region_is_refused():
    desktop = MagicMock()
    with pytest.raises(ValueError, match="zoom needs a region"):
        asyncio.run(_screenshot_tool(desktop)(zoom=True))
    desktop.get_state.assert_not_called()


def test_zoom_asks_for_an_enlarged_uncapped_capture():
    desktop = _mock_desktop()
    _capture(desktop, [100, 200, 120, 210])
    kwargs = desktop.get_state.call_args.kwargs
    assert kwargs["scale"] == ZOOM_WIDTH / 20
    assert kwargs["max_image_size"] is None


def test_tall_region_is_fitted_by_height():
    desktop = _mock_desktop()
    _capture(desktop, [0, 0, 10, 100])
    assert desktop.get_state.call_args.kwargs["scale"] == 1080 / 100


def test_zoom_keeps_the_coordinate_space():
    desktop = _mock_desktop(scale=0.75)
    result = _capture(desktop, [75, 150, 90, 157])  # caller space; screen 100,200,120,209
    assert desktop.coordinate_scale == 0.75
    text = build_snapshot_response(result, include_ui_details=False)[0]
    assert "Image Size: 1280x640" in text
    assert "image pixel (x, y) = (75 + x*0.011719, 150 + y*0.011719)" in text


def test_get_state_upscales_a_20x10_region_to_1280_wide():
    desktop = Desktop.__new__(Desktop)
    desktop.get_displays = MagicMock(return_value=[])
    desktop.get_screen_box = MagicMock(return_value=BoundingBox(0, 0, 1920, 1080, 1920, 1080))
    desktop.get_cursor_location = MagicMock(return_value=(0, 0))
    desktop.get_screenshot = MagicMock(return_value=Image.new("RGB", (20, 10), "white"))
    with (
        patch("windows_mcp.desktop.service.get_current_desktop", return_value={"name": "D"}),
        patch("windows_mcp.desktop.service.get_all_desktops", return_value=[{"name": "D"}]),
    ):
        state = desktop.get_state(
            use_vision=True,
            use_ui_tree=False,
            use_annotation=False,
            region=[100, 200, 120, 210],
            scale=ZOOM_WIDTH / 20,
            max_image_size=None,
        )
    assert state.screenshot.size == (1280, 640)
