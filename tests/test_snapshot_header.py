"""Round-2 3.10: Screenshot/Snapshot header details."""

from unittest.mock import MagicMock, patch

import pytest

from windows_mcp.desktop.service import Desktop
from windows_mcp.desktop.views import DesktopState, Status, Window
from windows_mcp.tools._snapshot_helpers import build_snapshot_response, capture_desktop_state
from windows_mcp.tree import service as tree_service
from windows_mcp.tree.budget import TreeElementBudget
from windows_mcp.tree.service import Tree
from windows_mcp.tree.views import BoundingBox, TreeState
from windows_mcp.uia.core import Rect


def _box(left, top, right, bottom):
    return BoundingBox(
        left=left, top=top, right=right, bottom=bottom, width=right - left, height=bottom - top
    )


def _window(name, box, handle, status=Status.NORMAL):
    return Window(
        name=name,
        is_browser=False,
        depth=0,
        status=status,
        bounding_box=box,
        handle=handle,
        process_id=1,
    )


def _header(cursor, region):
    state = DesktopState(
        active_desktop={"name": "Desktop 1"},
        all_desktops=[{"name": "Desktop 1"}],
        active_window=None,
        windows=[],
        cursor_position=cursor,
        screenshot_region=region,
        tree_state=TreeState(),
    )
    capture = dict.fromkeys(
        [
            "interactive_elements",
            "scrollable_elements",
            "semantic_tree",
            "windows",
            "active_window",
            "active_desktop",
            "all_desktops",
        ],
        "",
    )
    capture.update(desktop_state=state, screenshot_bytes=None)
    return build_snapshot_response(capture, include_ui_details=False)[0]


# a. cursor outside the region
def test_cursor_outside_region_is_named_not_none():
    text = _header(None, _box(0, 0, 100, 100))
    assert "Cursor Position: outside region" in text
    assert "None" not in text


def test_cursor_inside_region_is_printed():
    assert "Cursor Position: (5, 6)" in _header((5, 6), _box(0, 0, 100, 100))


# b, c. grid values
def _capture(desktop=None, **kwargs):
    args = dict(
        use_vision=True,
        use_dom=False,
        use_annotation=False,
        use_ui_tree=False,
        width_reference_line=None,
        height_reference_line=None,
        display=None,
        region=None,
        tool_name="Screenshot tool",
    )
    args.update(kwargs)
    desktop = desktop or MagicMock()
    capture_desktop_state(desktop, **args)
    return desktop


@pytest.mark.parametrize("value", [0, -3, 101, 5000])
@pytest.mark.parametrize("name", ["width_reference_line", "height_reference_line"])
def test_bad_grid_values_are_refused_before_capture(name, value):
    desktop = MagicMock()
    with pytest.raises(ValueError, match=f"{name} must be a whole number from 1 to 100"):
        _capture(desktop, **{name: value})
    desktop.get_state.assert_not_called()


@pytest.mark.parametrize(("width", "expected"), [(1, (1, 1)), (100, (100, 1)), ("4", (4, 1))])
def test_good_grid_values_are_accepted(width, expected):
    desktop = _capture(width_reference_line=width)
    assert desktop.get_state.call_args.kwargs["grid_lines"] == expected


# d. window sizes: visible frame, not clipped to the region
@pytest.fixture
def desktop():
    return Desktop.__new__(Desktop)


def test_window_box_is_the_visible_frame(desktop):
    control = MagicMock(NativeWindowHandle=7, BoundingRectangle=Rect(-8, -8, 1928, 1040))
    with patch(
        "windows_mcp.desktop.service.uia.DwmGetWindowExtendFrameBounds",
        return_value=Rect(0, 0, 1920, 1032),
    ):
        box = desktop._window_box(control)
    assert (box.width, box.height) == (1920, 1032)


def test_window_box_falls_back_to_outer_rect(desktop):
    control = MagicMock(NativeWindowHandle=7, BoundingRectangle=Rect(10, 20, 110, 220))
    with patch("windows_mcp.desktop.service.uia.DwmGetWindowExtendFrameBounds", return_value=None):
        box = desktop._window_box(control)
    assert (box.left, box.top, box.width, box.height) == (10, 20, 100, 200)


def test_region_keeps_window_size_unclipped(desktop):
    maximised = _window("Edge", _box(0, 0, 1920, 1032), 5, Status.MAXIMIZED)
    with patch(
        "windows_mcp.desktop.service.uia.DwmGetWindowExtendFrameBounds",
        return_value=Rect(0, 0, 1920, 1032),
    ):
        kept = desktop._filter_windows_to_region([maximised], _box(100, 100, 600, 140))
    assert [(w.bounding_box.width, w.bounding_box.height) for w in kept] == [(1920, 1032)]


# e. the focused window is named even when it lies outside the region
def test_focused_window_outside_region_is_still_named():
    desktop = Desktop.__new__(Desktop)
    desktop.tree = MagicMock()
    desktop.tree.get_state.return_value = TreeState()
    focused = _window("VS Code", _box(0, 0, 1920, 1032), 1, Status.MAXIMIZED)
    desktop.get_displays = MagicMock(return_value=[])
    desktop.get_controls_handles = MagicMock(return_value={1})
    desktop.get_windows = MagicMock(return_value=([focused], {1}))
    desktop.get_active_window = MagicMock(return_value=focused)
    desktop.get_cursor_location = MagicMock(return_value=(5, 5))
    # A 1920x1080 screen whatever this PC's is (a 1366x768 session refused the region).
    desktop.get_screen_box = MagicMock(return_value=_box(0, 0, 1920, 1080))
    with (
        patch("windows_mcp.desktop.service.get_current_desktop", return_value={"name": "D"}),
        patch("windows_mcp.desktop.service.get_all_desktops", return_value=[{"name": "D"}]),
        patch(
            "windows_mcp.desktop.service.uia.DwmGetWindowExtendFrameBounds",
            return_value=Rect(0, 0, 1920, 1032),
        ),
    ):
        # The taskbar strip: below the focused window's visible frame.
        state = desktop.get_state(use_vision=False, region=[0, 1045, 600, 1078])
    assert state.active_window is focused
    assert "VS Code" in state.active_window_to_string()


# f. the cap note only when something was really left out
def test_reaching_the_limit_exactly_is_not_truncation():
    budget = TreeElementBudget(limit=2)
    assert budget.try_consume() and budget.try_consume()
    assert budget.exhausted and not budget.truncated


def test_consuming_past_the_limit_is_truncation():
    budget = TreeElementBudget(limit=1)
    budget.try_consume()
    assert budget.try_consume() is False
    assert budget.truncated


def _tree(get_nodes, limit):
    tree = Tree.__new__(Tree)
    tree.desktop = MagicMock()
    tree.desktop.is_window_browser.return_value = False
    tree.element_budget = TreeElementBudget(limit)
    tree.get_nodes = MagicMock(side_effect=get_nodes)
    return tree


def _walk(tree, handles, drop=lambda h, i, s, sem: (i, s)):
    with (
        patch.object(tree_service, "is_unreadable_window", return_value=False),
        patch.object(tree_service, "ControlFromHandle", return_value=MagicMock(ClassName="X")),
        patch.object(
            tree_service, "z_order_rank", return_value={h: n for n, h in enumerate(handles)}
        ),
        patch.object(tree_service, "drop_occluded", side_effect=drop),
    ):
        return tree.get_window_wise_nodes(handles, active_window_flag=False)


def _two_elements(tree):
    def get_nodes(h, *a, **k):
        tree.element_budget.try_consume(2)
        return ([f"{h}-a", f"{h}-b"], [], [], None)

    return get_nodes


def test_every_element_listed_at_exactly_the_cap_has_no_note():
    tree = _tree(None, 2)
    tree.get_nodes.side_effect = _two_elements(tree)
    _walk(tree, [1])
    assert tree.element_budget.truncated is False


def test_window_left_unread_at_the_cap_gets_the_note():
    tree = _tree(None, 2)
    tree.get_nodes.side_effect = _two_elements(tree)
    _walk(tree, [1, 2])
    assert tree.get_nodes.call_count == 1
    assert tree.element_budget.truncated is True


def test_hidden_window_that_filled_the_cap_leaves_no_note():
    # Window 1 fills the cap exactly but all of it is hidden; window 2 is then read whole.
    tree = _tree(None, 2)
    tree.get_nodes.side_effect = _two_elements(tree)
    interactive, *_ = _walk(tree, [1, 2], lambda h, i, s, sem: ([], []) if h == 1 else (i, s))
    assert interactive == ["2-a", "2-b"]
    assert tree.element_budget.truncated is False
