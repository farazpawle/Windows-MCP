"""1.5: elements of background windows covered by another window are dropped."""

from windows_mcp.tree.utils import drop_occluded
from windows_mcp.tree.views import (
    BoundingBox,
    Center,
    ScrollElementNode,
    SemanticNode,
    TreeElementNode,
)

BACK, FRONT = 100, 200


def _node(x, y, name):
    box = BoundingBox(left=x - 5, top=y - 5, right=x + 5, bottom=y + 5, width=10, height=10)
    return TreeElementNode(bounding_box=box, center=Center(x=x, y=y), name=name, window_name="Back")


def _window_at(x, y):
    # FRONT covers everything left of x=500.
    return FRONT if x < 500 else BACK


def test_covered_elements_dropped_from_lists_and_tree():
    hidden, visible = _node(100, 100, "hidden"), _node(600, 100, "visible")
    scroll = ScrollElementNode(
        name="list",
        control_type="List",
        window_name="Back",
        bounding_box=hidden.bounding_box,
        center=Center(x=50, y=50),
    )
    group = SemanticNode(control_type="Group", element_type="structural", name="g")
    for n, kind in ((hidden, "interactive"), (visible, "interactive"), (scroll, "scrollable")):
        group.add_child(SemanticNode(control_type="Button", element_type=kind, name=n.name, center=n.center))
    window = SemanticNode(control_type="Window", element_type="window", name="Back")
    window.add_child(group)

    interactive, scrollable = drop_occluded(BACK, [hidden, visible], [scroll], window, window_at=_window_at)

    assert [n.name for n in interactive] == ["visible"]
    assert scrollable == []
    assert [c.name for c in group.children] == ["visible"]


def test_window_on_top_keeps_everything():
    nodes = [_node(100, 100, "a"), _node(600, 100, "b")]
    interactive, _ = drop_occluded(BACK, nodes, [], None, window_at=lambda x, y: BACK)
    assert len(interactive) == 2
