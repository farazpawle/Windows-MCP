"""Labels belong to the last Snapshot (round-2 bug 1.3).

WaitFor, App, Scrape and Screenshot all re-capture the desktop; before the fix
each capture replaced the tree that ``label=N`` indexes into, so a label could
silently point at a different element (a Close button, in the live test).
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from windows_mcp.desktop.service import Desktop
from windows_mcp.desktop.views import DesktopState
from windows_mcp.tools.snapshot import register as register_snapshot
from windows_mcp.tree.views import BoundingBox, Center, TreeElementNode, TreeState


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def tree(name: str, x: int) -> TreeState:
    box = BoundingBox(left=x - 5, top=0, right=x + 5, bottom=10, width=10, height=10)
    node = TreeElementNode(
        bounding_box=box,
        center=Center(x=x, y=5),
        name=name,
        control_type="Button",
        window_name="Harness",
    )
    return TreeState(interactive_nodes=[node])


def state(tree_state: TreeState) -> DesktopState:
    return DesktopState(
        active_desktop={"name": "Desktop 1"},
        all_desktops=[],
        active_window=None,
        windows=[],
        tree_state=tree_state,
    )


def test_labels_resolve_from_snapshot_tree_not_latest_capture():
    desktop = Desktop.__new__(Desktop)
    desktop.label_tree_state = tree("ShowLater", 633)
    desktop.desktop_state = state(tree("Close", 1049))  # a later WaitFor capture

    assert desktop.get_coordinates_from_label(0) == (633, 5)
    assert desktop.get_coordinates_from_labels([0]) == [(633, 5)]


def test_labels_before_any_snapshot_are_refused():
    desktop = Desktop.__new__(Desktop)
    desktop.label_tree_state = None
    desktop.desktop_state = state(tree("Close", 1049))

    for resolve in (
        lambda: desktop.get_coordinates_from_label(0),
        lambda: desktop.get_coordinates_from_labels([0]),
    ):
        with pytest.raises(ValueError, match="Snapshot"):
            resolve()


def _tools(desktop):
    mcp = FakeMCP()
    register_snapshot(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return mcp.tools


def test_snapshot_owns_labels_screenshot_does_not():
    snapshot_tree = tree("ShowLater", 633)
    desktop = MagicMock()
    desktop.label_tree_state = None
    desktop.get_state.return_value = state(snapshot_tree)
    tools = _tools(desktop)

    asyncio.run(tools["Snapshot"](use_vision=False))
    assert desktop.label_tree_state is snapshot_tree

    desktop.get_state.return_value = state(tree("Close", 1049))
    asyncio.run(tools["Screenshot"]())
    assert desktop.label_tree_state is snapshot_tree
