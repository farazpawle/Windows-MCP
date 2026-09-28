"""Round-5 R5-3: Snapshot listed Notepad's document twice, with a scroll of 100.1%."""

from types import SimpleNamespace

from windows_mcp.tree import utils
from windows_mcp.tree.views import BoundingBox, Center, SemanticNode, TreeState

BOX = BoundingBox(left=0, top=60, right=1000, bottom=600, width=1000, height=540)


def _document(value: str, percent: float) -> TreeState:
    """Notepad's document as the traversal records it: a scroll entry, then an input entry."""
    common = dict(control_type="Document", name="Text editor", window_name="Notepad")
    scroll_meta = {"vertical_scrollable": True, "vertical_scroll_percent": percent}
    input_meta = {"value": value, "has_focused": True}
    scroll = SimpleNamespace(**common, center=Center(412, 377), bounding_box=BOX)
    typed = SimpleNamespace(**common, center=Center(500, 330), bounding_box=BOX)
    window = SemanticNode(control_type="Window", element_type="window", name="Notepad")
    window.add_child(
        SemanticNode(
            **common,
            element_type="scrollable",
            center=scroll.center,
            bounding_box=BOX,
            metadata=dict(scroll_meta),
        )
    )
    window.add_child(
        SemanticNode(
            **common,
            element_type="interactive",
            center=typed.center,
            bounding_box=BOX,
            metadata=dict(input_meta),
        )
    )
    root = SemanticNode(control_type="Desktop", element_type="desktop", name="Desktop")
    root.add_child(window)
    typed.metadata, scroll.metadata = input_meta, scroll_meta
    return TreeState(interactive_nodes=[typed], scrollable_nodes=[scroll], semantic_tree_root=root)


def _document_lines(state: TreeState) -> list[str]:
    return [line for line in state.semantic_tree_to_string().splitlines() if "document" in line]


def test_a_document_both_typed_into_and_scrolled_is_listed_once():
    lines = _document_lines(_document("hello", 45.0))
    assert len(lines) == 1
    line = lines[0]
    # The input entry's label and point, which Click, Type and Scroll all accept.
    assert '[label:0] (500,330) document "Text editor"' in line
    assert '[value:"hello"]' in line and "[v:45.0%]" in line
    assert line.count("[focused]") == 1


def test_a_scroll_percent_above_100_is_shown_as_100():
    assert "[v:100.0%]" in _document_lines(_document("hello", 100.1))[0]


def test_value_line_breaks_are_shown_and_keep_the_entry_on_one_line():
    # Notepad's value holds bare CR line breaks; printed raw they ran lines together.
    lines = _document_lines(_document("Week 39\rRegion\r\nNorth", 0.0))
    assert len(lines) == 1
    assert '[value:"Week 39\\nRegion\\nNorth"]' in lines[0]


def test_scroll_reply_percent_above_100_is_100():
    pattern = SimpleNamespace(VerticallyScrollable=True, VerticalScrollPercent=100.1)
    control = SimpleNamespace(GetPattern=lambda _id: pattern)
    assert utils._scroll_percent(control, "vertical") == 100.0
