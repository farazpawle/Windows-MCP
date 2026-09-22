"""Regression tests for Plan/windows-mcp-open-issues.md section 3 (Low)."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from windows_mcp.desktop.service import Desktop
from windows_mcp.tools import input as input_tool_module
from windows_mcp.tree.views import (
    BoundingBox,
    Center,
    ScrollElementNode,
    SemanticNode,
    TreeElementNode,
    TreeState,
)
from windows_mcp.tools import multi as multi_tool_module


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _tool(module, name, desktop):
    mcp = FakeMCP()
    module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    tool = mcp.tools[name]
    return lambda **kwargs: asyncio.run(tool(**kwargs))


# 3.1 Click validates clicks (0-3) and names each count
class TestClickCount:
    @pytest.mark.parametrize(
        ("clicks", "word"), [(0, "Hover"), (1, "Single"), (2, "Double"), (3, "Triple")]
    )
    def test_valid_counts_are_named(self, clicks, word):
        desktop = MagicMock()
        reply = _tool(input_tool_module, "Click", desktop)(loc=[5, 6], clicks=clicks)
        assert reply.startswith(word)
        desktop.click.assert_called_once_with(loc=[5, 6], button="left", clicks=clicks)

    @pytest.mark.parametrize("clicks", [-1, 4, 10, True])
    def test_out_of_range_is_rejected_without_clicking(self, clicks):
        desktop = MagicMock()
        with pytest.raises(ValueError, match="clicks"):
            _tool(input_tool_module, "Click", desktop)(loc=[5, 6], clicks=clicks)
        desktop.click.assert_not_called()


# 3.2 MultiSelect reply is worded by mode
class TestMultiSelectReply:
    def test_ctrl_mode(self):
        reply = _tool(multi_tool_module, "MultiSelect", MagicMock())(
            locs=[[1, 2], [3, 4]], press_ctrl=True
        )
        assert reply.startswith("Ctrl-selected")

    def test_plain_mode(self):
        reply = _tool(multi_tool_module, "MultiSelect", MagicMock())(
            locs=[[1, 2], [3, 4]], press_ctrl=False
        )
        assert reply.startswith("Clicked in sequence")
        assert "selected" not in reply


def _flat(cls, name, x, y, window="W"):
    box = BoundingBox(left=x - 5, top=y - 5, right=x + 5, bottom=y + 5, width=10, height=10)
    if cls is ScrollElementNode:
        return ScrollElementNode(name, "Pane", window, box, Center(x, y))
    return TreeElementNode(box, Center(x, y), name, "Button", window)


def _sem(kind, name, x, y, window="W"):
    control = "Pane" if kind == "scrollable" else "Button"
    return SemanticNode(control, kind, name, window, center=Center(x, y))


# 3.3 Snapshot text tree prints the label id that Click/Type label= uses
class TestTreeLabels:
    def _state(self):
        ok, cancel = _flat(TreeElementNode, "OK", 10, 10), _flat(TreeElementNode, "Cancel", 30, 10)
        doc = _flat(ScrollElementNode, "Doc", 50, 50)
        root = SemanticNode("Desktop", "desktop", "Desktop")
        window = SemanticNode("Window", "window", "W", "W")
        root.add_child(window)
        # Text order differs from label order, and one element was filtered out of the
        # flat lists (e.g. covered by another window), so it has no label.
        for node in (
            _sem("scrollable", "Doc", 50, 50),
            _sem("interactive", "Cancel", 30, 10),
            _sem("interactive", "Gone", 70, 70),
            _sem("interactive", "OK", 10, 10),
        ):
            window.add_child(node)
        return TreeState(
            interactive_nodes=[ok, cancel], scrollable_nodes=[doc], semantic_tree_root=root
        )

    def test_labels_match_click_numbering(self):
        text = self._state().semantic_tree_to_string()
        line = {
            n: next(ln for ln in text.splitlines() if f'"{n}"' in ln)
            for n in ("OK", "Cancel", "Doc", "Gone")
        }
        assert "[label:0]" in line["OK"]
        assert "[label:1]" in line["Cancel"]
        assert "[label:2]" in line["Doc"]  # scrollables are numbered after interactives
        assert "label" not in line["Gone"]

    def test_duplicate_elements_get_distinct_labels(self):
        a, b = _flat(TreeElementNode, "X", 10, 10), _flat(TreeElementNode, "X", 10, 10)
        root = SemanticNode("Desktop", "desktop", "Desktop")
        root.add_child(_sem("interactive", "X", 10, 10))
        root.add_child(_sem("interactive", "X", 10, 10))
        text = TreeState(
            interactive_nodes=[a, b], semantic_tree_root=root
        ).semantic_tree_to_string()
        assert "[label:0]" in text and "[label:1]" in text


def _window(name, pid):
    return SimpleNamespace(name=name, process_id=pid, handle=pid)


# 3.5 App switch finds windows by short title fragment or process name
class TestFindWindowFallbacks:
    TITLES = [
        _window("tri.txt - Notepad", 1),
        _window("Shop and 4 more pages - Personal - Microsoft\u200b Edge", 2),
        _window("FactsERP [ROSTOCK]", 3),
    ]
    PROCESSES = {1: "Notepad.exe", 2: "msedge.exe", 3: "FactsERP.exe"}

    def _find(self, query):
        with patch.object(Desktop, "__init__", lambda self: None):
            desktop = Desktop()
        desktop.desktop_state = SimpleNamespace(active_window=None, windows=list(self.TITLES))
        with patch(
            "windows_mcp.desktop.service.Process",
            side_effect=lambda pid: SimpleNamespace(name=lambda: self.PROCESSES[pid]),
        ):
            return desktop._find_window_by_name(query)

    @pytest.mark.parametrize(
        ("query", "pid"),
        [("Edge", 2), ("microsoft edge", 2), ("msedge", 2), ("MSEDGE.exe", 2), ("Notepad", 1)],
    )
    def test_finds_window(self, query, pid):
        window, error = self._find(query)
        assert error == ""
        assert window.process_id == pid

    def test_unknown_name_still_not_found(self):
        window, error = self._find("Outlook")
        assert window is None
        assert "not found" in error
