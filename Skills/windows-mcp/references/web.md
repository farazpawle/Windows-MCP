# Web: Scrape

## HTTP mode (default)

- Works on this PC. Certificates are checked against the Windows store, so Avast's HTTPS
  inspection is accepted and bad certificates are still refused.
- Local and private addresses are blocked by design.
- If it fails, PowerShell `Invoke-WebRequest` is the fallback (system-tools.md).

## Browser mode (`use_dom=true`)

- Reads the **active tab of the focused browser** (Edge works). Snapshot `use_dom=true` lists
  the page's links and fields with labels Click accepts.
- To open a page, start `msedge.exe <url>` (full path: known-gaps.md). It opens a new tab:
  this PC's browser lock blocks new *windows*, not tabs. Then App switch to it.
- Close only your own tab afterwards (Ctrl+W while it is active).
- The first or last line says top / middle / bottom, or "Whole page visible".

## What comes back

- Only the **visible viewport** text: scroll and scrape again for more.
- `use_sampling=false` gives raw text. Clients that cannot summarise (Claude Code) always get
  raw text, with "Note: summary unavailable in this client".
- Without a summary, `query` keeps only the paragraphs that mention its words ("showing 2 of 4
  paragraphs that mention ..."); with no match the whole page comes back with a note.
  Keywords are plain words, so a link URL containing the word counts too.
- Long replies stop at 50,000 characters with "[truncated - N more characters]" (the same cap
  applies to Snapshot text and PowerShell, FileSystem and Process replies). Scrape a narrower
  page, or scroll with `use_dom=true`, for the rest.
