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
