"""Round-2 B.1: coordinates are in the pixel space of the last full screenshot."""

import asyncio
from unittest.mock import MagicMock

import pytest

import windows_mcp.uia as uia
from windows_mcp.desktop.service import Desktop
from windows_mcp.desktop.views import DesktopState, Size
from windows_mcp.tools import input as input_tools
from windows_mcp.tools import multi as multi_tools
from windows_mcp.tools._coords import to_model, to_screen
from windows_mcp.tools._snapshot_helpers import build_snapshot_response, capture_desktop_state
from windows_mcp.tree.views import BoundingBox, Center, TreeElementNode, TreeState


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _node(x, y, name="OK"):
    return TreeElementNode(
        bounding_box=BoundingBox(
            left=x - 5, top=y - 5, right=x + 5, bottom=y + 5, width=10, height=10
        ),
        center=Center(x=x, y=y),
        name=name,
        control_type="ButtonControl",
        window_name="Harness",
    )


def _desktop(scale=0.5):
    desktop = MagicMock()
    desktop.coordinate_scale = scale
    desktop.label_tree_state = TreeState(interactive_nodes=[_node(400, 300)])
    desktop.get_coordinates_from_label.return_value = (400, 300)
    desktop.get_coordinates_from_labels.return_value = [(400, 300)]
    desktop.get_cursor_location.return_value = (600, 200)
    desktop.drag.return_value = {"start": (20, 40), "duration": None}
    desktop.scroll.return_value = None
    return desktop


def _tools(desktop):
    mcp = FakeMCP()
    input_tools.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    multi_tools.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return mcp.tools


def _run(tool, **kwargs):
    return asyncio.run(tool(**kwargs))


# --- conversion helpers -------------------------------------------------------


def test_half_scale_doubles_to_screen():
    assert to_screen(_desktop(0.5), [100, 100]) == [200, 200]


def test_identity_at_full_scale():
    assert to_screen(_desktop(1.0), [100, 100]) == [100, 100]


def test_text_items_pass_through():
    assert to_screen(_desktop(0.5), [10, 20, "hello"]) == [20, 40, "hello"]


def test_screen_back_to_model():
    assert to_model(_desktop(0.5), (400, 300)) == (200, 150)


def test_desktop_without_a_scale_is_identity():
    assert to_screen(Desktop.__new__(Desktop), [7, 9]) == [7, 9]


# --- input tools ---------------------------------------------------------------


def test_click_loc_is_scaled_and_echoed_as_given():
    desktop = _desktop()
    reply = _run(_tools(desktop)["Click"], loc=[100, 100])
    assert desktop.click.call_args.kwargs["loc"] == [200, 200]
    assert "(100,100)" in reply


def test_click_label_is_not_scaled_but_echoed_in_image_space():
    desktop = _desktop()
    reply = _run(_tools(desktop)["Click"], label=0)
    assert desktop.click.call_args.kwargs["loc"] == [400, 300]
    assert "(200,150)" in reply


def test_hover_at_cursor_echoes_image_space():
    desktop = _desktop()
    reply = _run(_tools(desktop)["Click"], clicks=0)
    assert desktop.click.call_args.kwargs["loc"] == [600, 200]
    assert "(300,100)" in reply


def test_type_loc_is_scaled():
    desktop = _desktop()
    reply = _run(_tools(desktop)["Type"], text="x", loc=[10, 20])
    assert desktop.type.call_args.kwargs["loc"] == [20, 40]
    assert "(10,20)" in reply


def test_scroll_loc_is_scaled():
    desktop = _desktop()
    reply = _run(_tools(desktop)["Scroll"], loc=[10, 20])
    assert desktop.scroll.call_args.args[0] == [20, 40]
    assert "(10,20)" in reply


def test_move_loc_is_scaled():
    desktop = _desktop()
    reply = _run(_tools(desktop)["Move"], loc=[10, 20])
    desktop.move.assert_called_once_with([20, 40])
    assert "(10,20)" in reply


def test_drag_loc_and_from_loc_are_scaled():
    desktop = _desktop()
    reply = _run(_tools(desktop)["Move"], loc=[50, 60], from_loc=[10, 20], drag=True)
    assert desktop.drag.call_args.args[0] == [100, 120]
    assert desktop.drag.call_args.kwargs["from_loc"] == [20, 40]
    assert "from (10,20) to (50,60)" in reply


def test_mouse_button_loc_is_scaled():
    desktop = _desktop()
    _run(_tools(desktop)["Move"], loc=[10, 20], mouse_button="down")
    desktop.mouse_button.assert_called_once_with([20, 40], "down")


def test_multi_select_locs_scaled_labels_not():
    desktop = _desktop()
    reply = _run(_tools(desktop)["MultiSelect"], locs=[[10, 20]], labels=[0], press_ctrl=False)
    assert desktop.multi_select.call_args.args[1] == [[20, 40], [400, 300]]
    assert "(10,20)" in reply and "(200,150)" in reply


def test_multi_edit_locs_scaled():
    desktop = _desktop()
    reply = _run(_tools(desktop)["MultiEdit"], locs=[[10, 20, "a"]])
    desktop.multi_edit.assert_called_once_with([[20, 40, "a"]])
    assert "(10,20)" in reply


# --- capture: remembering the scale, region, printed positions ---------------------


def _state(scale, region=None, cursor=(400, 300)):
    return DesktopState(
        active_desktop={"name": "Desktop 1"},
        all_desktops=[{"name": "Desktop 1"}],
        active_window=None,
        windows=[],
        cursor_position=cursor,
        screenshot_original_size=Size(width=3840, height=2160),
        screenshot_scale=scale,
        screenshot_region=region,
        tree_state=TreeState(interactive_nodes=[_node(400, 300, "Save")]),
    )


def _capture(desktop, *, region=None, use_vision=True):
    return capture_desktop_state(
        desktop,
        use_vision=use_vision,
        use_dom=False,
        use_annotation=False,
        use_ui_tree=True,
        width_reference_line=None,
        height_reference_line=None,
        display=None,
        region=region,
        tool_name="test",
    )


def _capturing_desktop(scale):
    desktop = MagicMock()
    desktop.coordinate_scale = 1.0
    desktop.get_state.return_value = _state(scale)
    desktop.get_screen_box.return_value = BoundingBox(0, 0, 3840, 2160, 3840, 2160)
    return desktop


def test_full_screenshot_remembers_its_scale(monkeypatch):
    monkeypatch.delenv("WINDOWS_MCP_RAW_COORDINATES", raising=False)
    desktop = _capturing_desktop(0.5)
    _capture(desktop)
    assert desktop.coordinate_scale == 0.5


def test_region_screenshot_keeps_the_remembered_scale():
    desktop = _capturing_desktop(1.0)
    desktop.coordinate_scale = 0.5
    _capture(desktop, region=[100, 100, 200, 200])
    assert desktop.coordinate_scale == 0.5
    assert desktop.get_state.call_args.kwargs["region"] == [200, 200, 400, 400]


def test_capture_without_image_keeps_the_scale():
    desktop = _capturing_desktop(None)
    desktop.coordinate_scale = 0.5
    _capture(desktop, use_vision=False)
    assert desktop.coordinate_scale == 0.5


def test_opt_out_keeps_screen_coordinates(monkeypatch):
    monkeypatch.setenv("WINDOWS_MCP_RAW_COORDINATES", "1")
    desktop = _capturing_desktop(0.5)
    result = _capture(desktop)
    assert desktop.coordinate_scale == 1.0
    assert "(400,300)" in result["semantic_tree"] or "(400,300)" in result["interactive_elements"]
    text = build_snapshot_response(result, include_ui_details=True)[0]
    assert "multiply every image pixel coordinate by 2.0" in text


def test_printed_positions_use_image_space(monkeypatch):
    monkeypatch.delenv("WINDOWS_MCP_RAW_COORDINATES", raising=False)
    desktop = _capturing_desktop(0.5)
    result = _capture(desktop)
    assert "(200,150)" in result["interactive_elements"]
    text = build_snapshot_response(result, include_ui_details=False)[0]
    assert "Cursor Position: (200, 150)" in text
    assert "multiply" not in text


def test_region_image_mapping_is_printed(monkeypatch):
    monkeypatch.delenv("WINDOWS_MCP_RAW_COORDINATES", raising=False)
    desktop = _capturing_desktop(1.0)
    desktop.coordinate_scale = 0.5
    desktop.get_state.return_value = _state(1.0, region=BoundingBox(200, 200, 400, 400, 200, 200))
    result = _capture(desktop, region=[100, 100, 200, 200])
    text = build_snapshot_response(result, include_ui_details=False)[0]
    assert "Screenshot Region: (100,100,200,200)" in text
    assert "image pixel (x, y) = (100 + x*0.5, 100 + y*0.5)" in text


# --- off-screen refusal speaks the caller's coordinates ---------------------------


def test_off_screen_error_uses_image_space():
    desktop = Desktop.__new__(Desktop)
    desktop.coordinate_scale = 0.5
    display = MagicMock()
    display.rect = uia.Rect(0, 0, 3840, 2160)
    desktop.get_displays = MagicMock(return_value=[display])
    with pytest.raises(
        ValueError, match=r"\(2000,50\) is outside every display.*\(0,0\)-\(1920,1080\)"
    ):
        desktop._require_on_screen([(4000, 100)])
