"""Scrape tool — fetch/scrape web page content."""

import logging

from mcp.types import ToolAnnotations
from windows_mcp.infrastructure import with_analytics
from fastmcp import Context
from windows_mcp.tools._args import as_bool

logger = logging.getLogger(__name__)


def register(mcp, *, get_desktop, get_analytics):
    @mcp.tool(
        name="Scrape",
        description="Fetch/scrape web page content from a URL. Keywords: scrape, fetch, browse, web, URL, extract, download, read webpage. By default (use_dom=False), performs a lightweight HTTP request to the URL and returns a clean LLM-processed summary of the page to avoid context bloat. Provide query to focus extraction on specific information. Set use_dom=True to extract from the active browser tab's DOM instead (required when site blocks HTTP requests; supported in Chrome, Edge, and Firefox). Set use_sampling=False to get raw content without LLM processing.",
        annotations=ToolAnnotations(
            title="Scrape",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    @with_analytics(get_analytics(), "Scrape-Tool")
    async def scrape_tool(
        url: str,
        query: str | None = None,
        use_dom: bool | str = False,
        use_sampling: bool | str = True,
        ctx: Context = None,
    ) -> str:
        desktop = get_desktop()
        use_dom = as_bool(use_dom, "use_dom")
        use_sampling = as_bool(use_sampling, "use_sampling")

        if not use_dom:
            content = desktop.scrape(url)
        else:
            desktop_state = desktop.get_state(use_vision=False, use_dom=True)
            tree_state = desktop_state.tree_state
            if not tree_state.dom_node:
                return f"No DOM information found. Please open {url} in browser first."
            # The scroll position lives in the node's metadata; reading it as an attribute
            # always gave 0, so every page claimed "Reached top ... Scroll down".
            metadata = tree_state.dom_node.metadata or {}
            content = "\n".join([node.text for node in tree_state.dom_informative_nodes])
            if not metadata.get("vertical_scrollable"):
                content = f"Whole page visible (no scrolling)\n{content}"
            else:
                percent = metadata.get("vertical_scroll_percent", 0)
                header_status = "Reached top" if percent <= 0 else "Scroll up to see more"
                footer_status = "Reached bottom" if percent >= 100 else "Scroll down to see more"
                content = f"{header_status}\n{content}\n{footer_status}"

        if use_sampling and ctx is not None:
            try:
                focus = f" Focus specifically on: {query}." if query else ""
                result = await ctx.sample(
                    messages=f"Raw scraped content from {url}:\n\n{content}",
                    system_prompt=(
                        "You are a web content extractor. Given raw webpage content, extract and present "
                        "only the meaningful information in clean, concise prose or structured format. "
                        "Strip out navigation menus, cookie banners, ads, footer links, and all other "
                        f"boilerplate. Preserve important data, facts, and structure.{focus}"
                    ),
                    max_tokens=2048,
                )
                return f"URL: {url}\nContent:\n{result.text}"
            except Exception:
                logger.debug("Scrape summary via sampling failed", exc_info=True)

        if use_sampling:
            # Clients without sampling (e.g. Claude Code) would otherwise get raw content
            # with no hint that the default summary was skipped.
            return (
                f"URL: {url}\nNote: summary unavailable in this client; raw content returned.\n"
                f"Content:\n{content}"
            )
        return f"URL: {url}\nContent:\n{content}"
