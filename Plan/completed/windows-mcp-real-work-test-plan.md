---
Title: Windows-MCP round 3 - real-work scenario test of all 21 tools
Description: Test every windows-mcp tool the way an agent uses it at work, through the tools Claude Code is connected to (this repo's code). One office-job scenario in a sandbox (a work folder in %TEMP%, a registry key under HKCU:\Software\WMCP-Work, Notepad, Explorer, a small WinForms form, one Edge tab), plus a separate timing pass that measures each tool's own latency with an in-process client. Also checks Skills/Skill.md claim by claim against what the tools really do; guide wording is corrected in this session (user's choice 2026-09-24), tool bugs are only recorded in three sections (Bugs, Improvements, New tools) per the user's testing preference. User hands-off during screen parts; clipboard backed up before every overwrite; only own windows/PIDs/tab closed. Completed 2026-09-24; findings in Plan/windows-mcp-open-issues-round3.md.
---

# Scenario: "prepare and send a weekly sales report"

1. **Look around** - DisplayInventory, Screenshot, Snapshot (region), App list.
2. **Set up the work** - FileSystem writes a sales CSV and a notes file in `%TEMP%\wmcp-work`; Registry stores report settings in `HKCU:\Software\WMCP-Work`; PowerShell totals the CSV.
3. **Research** - Scrape example.com and a Wikipedia page (HTTP); open one Edge tab, Scrape `use_dom` and Snapshot `use_dom`, close that tab.
4. **Write the report** - App launch_executable Notepad with a new file; WaitFor active_window; Type the report; Shortcut (select, save); Scroll; Move drag-select; FindText to locate a heading by OCR; WaitFor screen_idle / screen_changed; Click by element name (menu); App minimize/restore/resize/close.
5. **Fill a form** - a small WinForms "Report details" form: MultiEdit its fields, Click its Submit button, check the saved values.
6. **Pick files** - Explorer on the work folder: MultiSelect three files with Ctrl, Shortcut Ctrl+C, Clipboard get shows the file list; Clipboard set/get text.
7. **Announce** - Notification "Report ready".
8. **Clean up** - Process list/kill own PIDs; FileSystem delete the work folder; Registry delete the key; clipboard restored; Wait between steps where natural.

# Timing pass

In-process FastMCP client (`windows-mcp-live-test` harness), each tool called 3 times on a harness window or sandbox path; median wall time per tool. "Lag" = a tool slower than its documented cost (e.g. FindText full screen ~2.5 s) or any simple action over 1 s.

# Guide check

Each Skill.md statement is marked confirmed / wrong / missing while the scenario runs; wrong or missing ones are corrected in Skill.md and listed in the report.

# Output

`docs/testing/windows-mcp-tool-test-report.md` gets a Round 3 section: per-tool verdict and timing, Bugs / Improvements / New tools, and the guide corrections made.
