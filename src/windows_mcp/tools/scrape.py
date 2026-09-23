"""Scrape tool — fetch/scrape web page content."""

import logging
import re

from mcp.types import ToolAnnotations
from windows_mcp.infrastructure import with_analytics
from fastmcp import Context
from windows_mcp.tools._args import as_bool
from windows_mcp.tools._output import cap_text

logger = logging.getLogger(__name__)

# ponytail: a fixed English filler list; a query in another language keeps its filler
# words as keywords, which only makes the filter keep more.
_FILLER = {"the", "and", "for", "with", "what", "which", "who", "how", "are", "was", "does"}
_FILLER |= {"this", "that", "from", "about", "into", "can", "any", "all", "you", "our"}


def _filter_paragraphs(content: str, query: str) -> tuple[str, str]:
    """Keep the paragraphs that mention a word of *query* (round-2 B.12).

    Stands in for the summary that query would steer, when none was made. Returns the
    content and a note; with no match the whole content stays, so nothing is lost.
    """
    keywords = {w for w in re.findall(r"\w+", query.lower()) if len(w) > 2} - _FILLER
    parts = [p for p in re.split(r"\n\s*\n", content) if p.strip()]
    if len(parts) < 2:  # no blank lines (DOM mode): one line is one paragraph
        parts = [line for line in content.splitlines() if line.strip()]
    kept = [p for p in parts if any(k in p.lower() for k in keywords)]
    if not kept:
        return content, f"no paragraph mentions {query!r}, so all content is shown"
    note = f"showing {len(kept)} of {len(parts)} paragraphs that mention {query!r}"
    return "\n\n".join(kept), note


def register(mcp, *, get_desktop, get_analytics):
    @mcp.tool(
        name="Scrape",
        description="Fetch/scrape web page content from a URL. Keywords: scrape, fetch, browse, web, URL, extract, download, read webpage. By default (use_dom=False), performs a lightweight HTTP request to the URL and returns a clean LLM-processed summary of the page to avoid context bloat. Provide query to focus extraction on specific information; when no summary is made (use_sampling=False, or a client that cannot summarise), query keeps only the paragraphs that mention its words, and the note says how many. Set use_dom=True to extract from the active browser tab's DOM instead (required when site blocks HTTP requests; supported in Chrome, Edge, and Firefox). Set use_sampling=False to get raw content without LLM processing.",
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

        # Clients without sampling (e.g. Claude Code) would otherwise get raw content
        # with no hint that the default summary was skipped.
        notes = ["summary unavailable in this client; raw content returned"] if use_sampling else []
        if query:
            content, query_note = _filter_paragraphs(content, query)
            notes.append(query_note)
        note = f"Note: {'; '.join(notes)}.\n" if notes else ""
        return cap_text(f"URL: {url}\n{note}Content:\n{content}")
