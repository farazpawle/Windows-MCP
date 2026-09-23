"""Round-2 B.11: Scrape and Snapshot replies are cut at the shared cap with a note."""

import asyncio
from unittest.mock import MagicMock

from windows_mcp.desktop.views import DesktopState
from windows_mcp.tools import scrape as scrape_tool_module
from windows_mcp.tools._output import MAX_REPLY_CHARS
from windows_mcp.tools._snapshot_helpers import build_snapshot_response
from windows_mcp.tree.views import TreeState


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _scrape(page: str) -> str:
    mcp = FakeMCP()
    desktop = MagicMock()
    desktop.scrape.return_value = page
    scrape_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return asyncio.run(mcp.tools["Scrape"](url="https://example.com", use_sampling=False))


def _snapshot_text(tree: str) -> str:
    state = DesktopState(
        active_desktop={"name": "Desktop 1"},
        all_desktops=[{"name": "Desktop 1"}],
        active_window=None,
        windows=[],
        tree_state=TreeState(),
    )
    result = {
        "desktop_state": state,
        "interactive_elements": "",
        "scrollable_elements": "",
        "semantic_tree": tree,
        "windows": "No windows found",
        "active_window": "No active window found",
        "active_desktop": "Desktop 1",
        "all_desktops": "Desktop 1",
        "screenshot_bytes": None,
    }
    return build_snapshot_response(result, include_ui_details=True)[0]


def test_long_scrape_is_cut_with_a_note():
    reply = _scrape("a" * 300_000)
    assert len(reply) < MAX_REPLY_CHARS + 100
    assert "[truncated -" in reply


def test_short_scrape_is_untouched():
    assert "[truncated" not in _scrape("hello")


def test_long_snapshot_text_is_cut_with_a_note():
    text = _snapshot_text("x" * 300_000)
    assert len(text) < MAX_REPLY_CHARS + 100
    assert "[truncated -" in text


def test_short_snapshot_text_is_untouched():
    assert "[truncated" not in _snapshot_text("button")
