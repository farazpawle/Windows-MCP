"""Round-3 R3-I8: an unnamed window with nothing listed under it is left out of Snapshot's tree."""

from windows_mcp.tree.views import SemanticNode, TreeState, _prune_structural


def _window(name: str, *children: SemanticNode) -> SemanticNode:
    return SemanticNode("Window", "window", name=name, children=list(children))


def test_empty_unnamed_windows_are_dropped_but_others_kept():
    button = SemanticNode("Button", "interactive", name="OK")
    root = SemanticNode("Desktop", "desktop")
    root.children = [
        _window(""),  # the noise: prints as a bare `window ""` line
        _window("", button),  # unnamed but has content: kept
        _window("Notepad"),  # named, even if empty: kept
    ]
    _prune_structural(root)
    text = TreeState(semantic_tree_root=root).semantic_tree_to_string()
    assert text.count('window ""') == 1
    assert 'window "Notepad"' in text and '"OK"' in text
