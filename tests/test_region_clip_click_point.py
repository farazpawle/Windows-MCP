"""Round-2 1.7: a region capture must not move a click point onto a covering window."""

from unittest.mock import patch

from windows_mcp.desktop.service import Desktop
from windows_mcp.tree.views import BoundingBox, Center, SemanticNode, TreeElementNode, TreeState

REGION = BoundingBox(left=108, top=100, right=692, bottom=492, width=584, height=392)
EDGE, HARNESS = 1, 2


def _box(left, top, right, bottom):
    return BoundingBox(
        left=left, top=top, right=right, bottom=bottom, width=right - left, height=bottom - top
    )


def _node(name, box):
    return TreeElementNode(
        bounding_box=box, center=box.get_center(), name=name, control_type="Button", window_name="W"
    )


def _filter(nodes, window_at):
    root = SemanticNode(control_type="Desktop", element_type="desktop", name="Desktop")
    for n in nodes:
        root.add_child(
            SemanticNode(
                control_type="Button",
                element_type="interactive",
                name=n.name,
                window_name="W",
                center=n.center,
                bounding_box=n.bounding_box,
            )
        )
    state = TreeState(interactive_nodes=nodes, semantic_tree_root=root)
    with patch("windows_mcp.desktop.service.top_level_window_at", side_effect=window_at):
        return Desktop.__new__(Desktop)._filter_tree_state_to_region(state, REGION)


def _names(state):
    return (
        [n.name for n in state.interactive_nodes],
        [c.name for c in state.semantic_tree_root.children],
    )


# Edge's bookmark bar (y < 100) is visible above the harness, which covers the region.
def edge_above_harness_inside(x, y):
    return EDGE if y < 100 else HARNESS


def test_clipped_point_landing_on_another_window_is_dropped():
    bookmark = _node("Supersession Catalogs", _box(640, 84, 712, 108))  # centre (676,96) on Edge
    state = _filter([bookmark], edge_above_harness_inside)
    assert _names(state) == ([], [])


def test_clipped_point_still_on_its_own_window_is_kept():
    bookmark = _node("Supersession Catalogs", _box(640, 84, 712, 108))
    state = _filter([bookmark], lambda x, y: EDGE)
    assert _names(state) == (["Supersession Catalogs"], ["Supersession Catalogs"])
    assert state.interactive_nodes[0].center == Center(x=666, y=104)


def test_element_fully_inside_the_region_is_kept_without_lookup():
    button = _node("ClickMe", _box(150, 160, 250, 200))
    state = _filter([button], lambda x, y: (_ for _ in ()).throw(AssertionError("no lookup")))
    assert _names(state) == (["ClickMe"], ["ClickMe"])
