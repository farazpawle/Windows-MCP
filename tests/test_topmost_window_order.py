"""Round-2 1.5: a visible on-top window that is not focused must get its elements."""

from unittest.mock import MagicMock, patch

from windows_mcp.desktop.service import Desktop
from windows_mcp.tree import service as tree_service
from windows_mcp.tree.budget import TreeElementBudget
from windows_mcp.tree.service import Tree
from windows_mcp.tree.utils import is_fully_covered
from windows_mcp.tree.views import BoundingBox
from windows_mcp.uia.core import Rect

ACTIVE, TOPMOST, BEHIND = 10, 20, 30


def _tree(get_nodes) -> Tree:
    tree = Tree.__new__(Tree)
    tree.desktop = MagicMock()
    tree.desktop.is_window_browser.return_value = False
    tree.element_budget = TreeElementBudget(500)
    tree.get_nodes = MagicMock(side_effect=get_nodes)
    return tree


def _walk(tree, handles, z_order, drop=lambda h, i, s, sem: (i, s)):
    with (
        patch.object(tree_service, "is_unreadable_window", return_value=False),
        patch.object(tree_service, "ControlFromHandle", return_value=MagicMock(ClassName="X")),
        patch.object(tree_service, "z_order_rank", return_value=z_order),
        patch.object(tree_service, "drop_occluded", side_effect=drop),
    ):
        return tree.get_window_wise_nodes(handles, active_window_flag=True)


def test_windows_are_read_front_to_back_not_focused_first():
    walked = []
    tree = _tree(lambda h, *a, **k: walked.append(h) or ([], [], [], None))
    _walk(tree, [ACTIVE, BEHIND, TOPMOST], {TOPMOST: 0, ACTIVE: 1, BEHIND: 2})
    assert walked == [TOPMOST, ACTIVE, BEHIND]


def test_focused_window_elements_under_an_on_top_window_are_dropped_too():
    # Live 2026-09-22: Edge focused behind a TopMost harness listed its bookmarks
    # under the harness; a label click there would hit the harness.
    tree = _tree(lambda h, *a, **k: ([h], [], [], None))
    filtered = []

    def drop(h, i, s, sem):
        filtered.append(h)
        return i, s

    _walk(tree, [ACTIVE, TOPMOST], {TOPMOST: 0, ACTIVE: 1}, drop)
    assert filtered == [TOPMOST, ACTIVE]


def test_elements_dropped_as_hidden_do_not_use_up_the_element_cap():
    def get_nodes(h, *a, **k):
        tree.element_budget.try_consume(2)
        return ([f"{h}-a", f"{h}-b"], [], [], None)

    tree = _tree(get_nodes)
    tree.element_budget = TreeElementBudget(2)
    hide_behind = lambda h, i, s, sem: ([], []) if h == BEHIND else (i, s)  # noqa: E731
    interactive, *_ = _walk(tree, [ACTIVE, BEHIND, TOPMOST], {BEHIND: 0, TOPMOST: 1}, hide_behind)
    # BEHIND's 2 elements were all hidden, so the cap still had room for TOPMOST.
    assert interactive == [f"{TOPMOST}-a", f"{TOPMOST}-b"]


def test_fully_covered_detection():
    rect = Rect(100, 100, 300, 200)
    assert is_fully_covered(5, rect, window_at=lambda x, y: 9)
    assert not is_fully_covered(5, rect, window_at=lambda x, y: 5 if x > 280 else 9)


def _box(left, top, right, bottom):
    return BoundingBox(
        left=left, top=top, right=right, bottom=bottom, width=right - left, height=bottom - top
    )


def test_region_skips_windows_fully_covered_inside_it():
    desktop = Desktop.__new__(Desktop)
    region = _box(100, 100, 700, 500)
    windows = [MagicMock(handle=h, bounding_box=_box(0, 0, 1920, 1080)) for h in (BEHIND, TOPMOST)]
    covered = {BEHIND}
    with (
        patch("windows_mcp.desktop.service.uia.DwmGetWindowExtendFrameBounds", return_value=None),
        patch(
            "windows_mcp.desktop.service.is_fully_covered",
            side_effect=lambda h, rect: h in covered,
        ),
    ):
        _, others = desktop._select_tree_handles(None, set(), windows, region)
    assert others == [TOPMOST]
