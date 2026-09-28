import asyncio
from unittest.mock import MagicMock, patch

import pytest

from windows_mcp.desktop.service import Desktop
from windows_mcp.desktop.views import DesktopState
from windows_mcp.tree.views import (
    BoundingBox,
    Center,
    ScrollElementNode,
    TreeElementNode,
    TreeState,
)
from windows_mcp.tools.multi import register

SERVICE = "windows_mcp.desktop.service"


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def make_desktop_with_tree_state():
    desktop = Desktop.__new__(Desktop)
    desktop.desktop_state = DesktopState(
        active_desktop={"name": "Desktop 1"},
        all_desktops=[],
        active_window=None,
        windows=[],
        tree_state=TreeState(
            interactive_nodes=[
                TreeElementNode(
                    bounding_box=BoundingBox(
                        left=0, top=0, right=20, bottom=20, width=20, height=20
                    ),
                    center=Center(x=10, y=10),
                    name="Button 1",
                    control_type="Button",
                    window_name="Notepad",
                ),
                TreeElementNode(
                    bounding_box=BoundingBox(
                        left=20, top=20, right=60, bottom=60, width=40, height=40
                    ),
                    center=Center(x=40, y=40),
                    name="Button 2",
                    control_type="Button",
                    window_name="Notepad",
                ),
            ],
            scrollable_nodes=[
                ScrollElementNode(
                    name="Scrollable 1",
                    control_type="Pane",
                    window_name="Notepad",
                    bounding_box=BoundingBox(
                        left=60, top=60, right=100, bottom=100, width=40, height=40
                    ),
                    center=Center(x=80, y=80),
                )
            ],
        ),
    )
    desktop.label_tree_state = desktop.desktop_state.tree_state  # as Snapshot sets it
    return desktop


def register_tools(desktop):
    mcp = FakeMCP()
    register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return mcp.tools


def test_get_coordinates_from_labels_returns_bulk_coordinates():
    desktop = make_desktop_with_tree_state()

    assert desktop.get_coordinates_from_labels([0, 1, 2]) == [(10, 10), (40, 40), (80, 80)]


def test_multiselect_passes_labels_to_desktop_unresolved():
    desktop = MagicMock()
    desktop.multi_select.return_value = [(10, 10), (40, 40)]

    tools = register_tools(desktop)
    result = asyncio.run(tools["MultiSelect"](labels=[0, 1], press_ctrl=False))

    assert result == "Clicked in sequence at:\n(10,10)\n(40,40)"
    desktop.get_coordinates_from_labels.assert_not_called()
    desktop.multi_select.assert_called_once_with(False, [], [0, 1])


def test_multiedit_passes_labels_to_desktop_unresolved():
    desktop = MagicMock()
    desktop.multi_edit.return_value = [(10, 10, "First"), (40, 40, "Second")]

    tools = register_tools(desktop)
    result = asyncio.run(tools["MultiEdit"](labels=[[0, "First"], [1, "Second"]]))

    assert (
        result == "Multi-edited elements at: (10,10) with text 'First', (40,40) with text 'Second'"
    )
    desktop.get_coordinates_from_labels.assert_not_called()
    desktop.multi_edit.assert_called_once_with([], [(0, "First"), (1, "Second")])


# R6-2: each label is checked just before its own click, so a click that reflows the list
# stops the batch instead of sending the next click to a stale spot.
def _moves_after_first_click(clicks):
    """spot_on_element: label 0 is where Snapshot saw it; label 1 only until the first click."""

    def spot(name, control_type, x, y, rect, window):
        return (x, y) if name == "Button 1" or not clicks else None

    return (
        patch(f"{SERVICE}.spot_on_element", side_effect=spot),
        patch(f"{SERVICE}.covering_window", return_value=None),
        patch.object(Desktop, "_require_on_screen"),
    )


def test_multiselect_stops_before_a_label_that_moved():
    desktop = make_desktop_with_tree_state()
    clicks = []
    p1, p2, p3 = _moves_after_first_click(clicks)
    with (
        p1,
        p2,
        p3,
        patch(f"{SERVICE}.uia.Click", side_effect=lambda x, y, **_: clicks.append((x, y))),
        patch(f"{SERVICE}.uia.PressKey"),
        patch(f"{SERVICE}.uia.ReleaseKey") as release,
    ):
        with pytest.raises(ValueError) as err:
            desktop.multi_select(True, [], [0, 1])
    assert clicks == [(10, 10)]
    message = str(err.value)
    assert "label 1" in message and "no longer at its spot" in message
    assert "Done: label 0" in message
    release.assert_called_once()  # Ctrl is never left held


def test_multiselect_unchanged_list_clicks_all():
    desktop = make_desktop_with_tree_state()
    with (
        patch(f"{SERVICE}.spot_on_element", side_effect=lambda n, c, x, y, **_: (x, y)),
        patch.object(Desktop, "_require_on_screen"),
        patch(f"{SERVICE}.uia.Click") as click,
        patch(f"{SERVICE}.uia.PressKey"),
        patch(f"{SERVICE}.uia.ReleaseKey"),
    ):
        points = desktop.multi_select(True, [[5, 5]], [0, 1])
    assert points == [(5, 5), (10, 10), (40, 40)]
    assert [c.args for c in click.call_args_list] == [(5, 5), (10, 10), (40, 40)]


def test_multiedit_stops_before_a_label_that_moved():
    desktop = make_desktop_with_tree_state()
    clicks = []
    p1, p2, p3 = _moves_after_first_click(clicks)
    with (
        p1,
        p2,
        p3,
        patch.object(Desktop, "type", side_effect=lambda loc, **_: clicks.append(loc)),
    ):
        with pytest.raises(ValueError) as err:
            desktop.multi_edit([], [(0, "a"), (1, "b")])
    assert clicks == [(10, 10)]
    message = str(err.value)
    assert message.startswith("MultiEdit stopped at label 1")
    assert "Done: label 0" in message and "Not done: label 1" in message
