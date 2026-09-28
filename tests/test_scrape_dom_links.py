"""Round-2 3.12: Scrape use_dom=True kept paragraph text but dropped link text."""

from unittest.mock import MagicMock

import pytest

from windows_mcp.desktop.views import Size
from windows_mcp.tree.service import Tree
from windows_mcp.tree.views import BoundingBox
from windows_mcp.uia.core import Rect


@pytest.fixture
def tree():
    desktop = MagicMock()
    desktop.get_screen_size.return_value = Size(width=1920, height=1080)
    desktop.get_screen_box.return_value = BoundingBox(
        left=0, top=0, right=1920, bottom=1080, width=1920, height=1080
    )
    return Tree(desktop)


def _element(control_type: str, name: str, *, control_element: bool = True) -> MagicMock:
    element = MagicMock()
    element.CachedIsOffscreen = False
    element.CachedControlTypeName = control_type
    element.CachedIsControlElement = control_element
    element.CachedBoundingRectangle = Rect(10, 10, 110, 40)
    element.CachedIsEnabled = True
    element.CachedIsKeyboardFocusable = control_type == "HyperlinkControl"
    element.CachedName = name
    element.GetCachedPattern.return_value = None
    return element


def _read_page(tree, monkeypatch, children_of: dict) -> list[str]:
    monkeypatch.setattr(
        "windows_mcp.tree.service.CachedControlHelper.get_cached_children",
        lambda node, request: children_of.get(id(node), []),
    )
    page = _element("GroupControl", "")
    children_of[id(page)] = children_of.pop("page")
    texts = []
    tree.tree_traversal(page, Rect(0, 0, 500, 500), "Edge", True, None, [], [], texts, is_dom=True)
    return [node.text for node in texts]


def test_link_text_is_part_of_the_page_text(tree, monkeypatch):
    # Structure read from Edge on example.com (2026-09-23): the words inside the link
    # are a TextControl that is not a control element, so only the link carries them.
    paragraph = _element("TextControl", "This domain is for use in documentation examples")
    link = _element("HyperlinkControl", "Learn more")
    link_words = _element("TextControl", "Learn more", control_element=False)
    children_of = {"page": [paragraph, link], id(link): [link_words]}
    assert _read_page(tree, monkeypatch, children_of) == [
        "This domain is for use in documentation examples",
        "Learn more",
    ]


def test_unnamed_link_adds_no_blank_line(tree, monkeypatch):
    children_of = {"page": [_element("HyperlinkControl", "  ")]}
    assert _read_page(tree, monkeypatch, children_of) == []


# R5-1: Scrape use_dom dropped table text. Structure read from Edge (2026-09-28): a row
# is a nameless DataItemControl, each cell a DataItemControl named with its text, and
# the words inside a cell a TextControl that is not a control element.
def _table(children_of: dict, rows: list[list[str]]) -> MagicMock:
    table = _element("TableControl", "")
    children_of[id(table)] = []
    for cells in rows:
        row = _element("DataItemControl", "")
        children_of[id(table)].append(row)
        children_of[id(row)] = []
        for text in cells:
            cell = _element("DataItemControl", text)
            children_of[id(row)].append(cell)
            children_of[id(cell)] = [_element("TextControl", text, control_element=False)]
    return table


def test_table_rows_are_part_of_the_page_text_one_line_each(tree, monkeypatch):
    children_of = {}
    table = _table(children_of, [["Region", "Total"], ["North", "460"], ["South", "405"]])
    children_of["page"] = [_element("TextControl", "Sales report"), table]
    assert _read_page(tree, monkeypatch, children_of) == [
        "Sales report",
        "Region | Total",
        "North | 460",
        "South | 405",
    ]


def test_a_row_of_blank_cells_adds_no_line(tree, monkeypatch):
    children_of = {}
    children_of["page"] = [_table(children_of, [["", " "]])]
    assert _read_page(tree, monkeypatch, children_of) == []
