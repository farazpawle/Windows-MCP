"""Round-2 B.12: without a summary, query keeps only the paragraphs that mention it."""

import asyncio
from unittest.mock import MagicMock

from windows_mcp.tools import scrape as scrape_tool_module

PAGE = (
    "Welcome to the shop.\n\n"
    "Shipping takes 3 days within the country.\n\n"
    "Returns are free for 30 days.\n\n"
    "International shipping costs extra."
)


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _scrape(page=PAGE, **kwargs) -> str:
    mcp = FakeMCP()
    desktop = MagicMock()
    desktop.scrape.return_value = page
    scrape_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return asyncio.run(mcp.tools["Scrape"](url="https://example.com", use_sampling=False, **kwargs))


def test_only_matching_paragraphs_are_returned():
    reply = _scrape(query="How much is shipping?")
    assert "Shipping takes 3 days" in reply and "International shipping" in reply
    assert "Returns are free" not in reply and "Welcome" not in reply
    assert "showing 2 of 4 paragraphs that mention" in reply


def test_matching_ignores_case_and_filler_words():
    reply = _scrape(query="what about RETURNS")
    assert "Returns are free" in reply
    assert "showing 1 of 4 paragraphs" in reply


def test_no_match_returns_the_whole_page_with_a_note():
    reply = _scrape(query="warranty")
    assert "Welcome" in reply and "Returns are free" in reply
    assert "no paragraph mentions" in reply


def test_lines_count_as_paragraphs_when_there_are_no_blank_lines():
    reply = _scrape(page="Home\nShipping info\nContact", query="shipping")
    assert "Shipping info" in reply and "Contact" not in reply


def test_without_query_nothing_is_filtered():
    reply = _scrape()
    assert "Welcome" in reply and "paragraph" not in reply
