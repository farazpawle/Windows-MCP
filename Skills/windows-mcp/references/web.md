# Web: Scrape

## HTTP mode (default)

- Works on this PC. Certificates are checked against the Windows store, so Avast's HTTPS
  inspection is accepted and bad certificates are still refused.
- Local and private addresses are blocked by design.
- If it fails, PowerShell `Invoke-WebRequest` is the fallback (system-tools.md).

## Browser mode (`use_dom=true`)

- Reads the **active tab of the focused browser** (Edge works). Snapshot `use_dom=true` lists
  the page's links and fields with labels Click accepts.
- To open a page, App `launch_executable` with `msedge.exe` (the bare name works) and the URL
  as `args`. In the running Edge it opens a new tab: this PC's browser lock blocks new
  *windows*, not tabs. Then App switch to it. A throwaway profile
  (`--user-data-dir=<empty folder>`) opens its own window instead.
- A throwaway profile signs itself into the Windows Microsoft account and shows a "now
  syncing" notice over the page; `use_dom` then returns the notice's text. Click its
  "Got it" first.
- While a throwaway profile is starting and syncing, every window answers slowly: Click
  `element=` and App calls by window name can take ~1.5-2 s instead of ~0.5 s. With an
  everyday Edge profile, Click `element=` in Edge takes about 0.5 s.
- Close only your own tab afterwards (Ctrl+W while it is active).
- The first or last line says top / middle / bottom, or "Whole page visible".

## What comes back

- Only the **visible viewport** text: scroll and scrape again for more.
- With `use_dom=true` a table comes back one row per line, cells joined by ` | `
  (`North | 460`). A link inside a cell also gets a line of its own after its row. Right
  after the page opens, before Edge exposes its tree, the cells can come one per line instead.
  Buttons are not in the text; Snapshot lists them.
- `use_sampling=false` gives raw text. Clients that cannot summarise (Claude Code) always get
  raw text, with "Note: summary unavailable in this client".
- Without a summary, `query` keeps only the paragraphs that mention its words ("showing 2 of 4
  paragraphs that mention ..."); with no match the whole page comes back with a note.
  Keywords are plain words, so a link URL containing the word counts too.
- Long replies stop at 50,000 characters with "[truncated - N more characters]" (the same cap
  applies to Snapshot text and PowerShell, FileSystem and Process replies). Scrape a narrower
  page, or scroll with `use_dom=true`, for the rest.
