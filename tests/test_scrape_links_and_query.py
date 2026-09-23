"""Round-2 3.17: Scrape makes links absolute and says when query was ignored."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from windows_mcp.desktop import service
from windows_mcp.tools import scrape as scrape_tool_module


def _fetch(html: str, url: str = "https://example.com/docs/page") -> str:
    response = MagicMock(is_redirect=False, text=html)
    with patch.object(service._http_session, "get", return_value=response):
        return service.Desktop.__new__(service.Desktop).scrape(url)


def test_relative_links_become_absolute():
    content = _fetch('<a href="/domains">Domains</a> <a href="next">Next</a>')
    assert "(https://example.com/domains)" in content
    assert "(https://example.com/docs/next)" in content


def test_images_become_absolute():
    assert "(https://example.com/docs/logo.png)" in _fetch('<img src="logo.png" alt="Logo">')


def test_absolute_and_mailto_links_are_kept():
    content = _fetch('<a href="https://iana.org/x">IANA</a> <a href="mailto:a@b.c">Mail</a>')
    assert "(https://iana.org/x)" in content
    assert "(mailto:a@b.c)" in content


def test_links_resolve_against_the_redirect_target():
    moved = MagicMock(is_redirect=True, headers={"Location": "https://www.example.org/new/"})
    final = MagicMock(is_redirect=False, text='<a href="about">About</a>')
    with patch.object(service._http_session, "get", side_effect=[moved, final]):
        content = service.Desktop.__new__(service.Desktop).scrape("https://example.com/")
    assert "(https://www.example.org/new/about)" in content


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _scrape_tool(ctx, **kwargs) -> str:
    mcp = FakeMCP()
    desktop = MagicMock()
    desktop.scrape.return_value = "raw page"
    scrape_tool_module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return asyncio.run(mcp.tools["Scrape"](url="https://example.com", ctx=ctx, **kwargs))


@pytest.mark.parametrize("use_sampling", [True, False])
def test_unmatched_query_is_noted_when_not_summarised(use_sampling):
    # B.12 replaced "query ignored" with a keyword filter; nothing matches "raw page".
    reply = _scrape_tool(None, query="which domains", use_sampling=use_sampling)
    assert "no paragraph mentions" in reply
    assert "raw page" in reply


def test_no_query_note_when_summarised():
    ctx = MagicMock()
    ctx.sample = AsyncMock(return_value=MagicMock(text="short summary"))
    assert "paragraph" not in _scrape_tool(ctx, query="which domains")


def test_no_query_note_without_query():
    assert "paragraph" not in _scrape_tool(None)
