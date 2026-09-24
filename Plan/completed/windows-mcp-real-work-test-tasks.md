---
Title: Windows-MCP round 3 - real-work scenario test tasks
Description: Task list for the round-3 plan (Plan/completed/windows-mcp-real-work-test-plan.md) - an office-job scenario that used all 21 windows-mcp tools through the connected server, a per-tool timing pass with an in-process client, and a claim-by-claim check of Skills/Skill.md. All done 2026-09-24. Findings (9 bugs, 9 improvements, 1 new ability) are in Plan/windows-mcp-open-issues-round3.md and the Round 3 section of docs/testing/windows-mcp-tool-test-report.md; guide wording was corrected in the session, tool code was not changed.
Total Tasks: 30
---

# 1. Prepare
- [x] 1.1 Check no window is "Not Responding". (none)
- [x] 1.2 Back up the clipboard (text / image / file list). (image 726x271 saved with Clipboard save_image, checked)
- [x] 1.3 Tell the user the screen part starts (hands off).

# 2. Look around
- [x] 2.1 DisplayInventory.
- [x] 2.2 Screenshot (full, then region + zoom).
- [x] 2.3 App list.

# 3. Set up the work (no screen input)
- [x] 3.1 FileSystem: write sales CSV and notes; list; info; read with offset/limit.
- [x] 3.2 Registry: set String/DWord/Binary; get; list. (MultiString and ExpandString too)
- [x] 3.3 PowerShell: total the CSV; one failing command shows as a tool error. (plus timeout, success_exit_codes, Read-Host)

# 4. Research
- [x] 4.1 Scrape example.com and a Wikipedia page (HTTP).
- [x] 4.2 Open one Edge tab; Scrape use_dom; Snapshot use_dom; close only that tab.

# 5. Write the report in Notepad
- [x] 5.1 App launch_executable Notepad on a new file; record PID. (stub PID 25436, real 17292)
- [x] 5.2 WaitFor active_window.
- [x] 5.3 Snapshot the Notepad region.
- [x] 5.4 Type the report.
- [x] 5.5 Shortcut: ctrl+s; ctrl+home; repeat and hold. (hold covered by round 2; repeat here and in the timing pass)
- [x] 5.6 Scroll the text. (Ctrl+wheel zoom to 120%; Explorer pane position reported)
- [x] 5.7 Move: drag-select a line.
- [x] 5.8 FindText a heading by OCR.
- [x] 5.9 WaitFor screen_idle and screen_changed. (screen_changed missed a clock change: R3-4)
- [x] 5.10 Click by element name (a menu).
- [x] 5.11 App minimize / restore / resize / switch / close Notepad.

# 6. Fill a form
- [x] 6.1 Open the WinForms "Report details" form.
- [x] 6.2 MultiEdit its fields; Click Submit; read the saved values.

# 7. Pick files
- [x] 7.1 Explorer on the work folder; MultiSelect three files with Ctrl.
- [x] 7.2 Shortcut ctrl+c; Clipboard get lists the files. (pasted into an outbox folder too)
- [x] 7.3 Clipboard set/get text. (text, files, image restore)

# 8. Announce and clean up
- [x] 8.1 Notification "Report ready".
- [x] 8.2 Process list and kill own PIDs.
- [x] 8.3 Delete the work folder and registry key; restore the clipboard.

# 9. Timing and guide
- [x] 9.1 Timing pass: median of 3 calls per tool (in-process client).
- [x] 9.2 Correct Skill.md where wrong or missing.
- [x] 9.3 Write the Round 3 report section.

# Implementation verification
- Every tool (21) called at least once in the scenario, each result checked a second way (file/registry/process read, screenshot, harness log, clipboard read). - Done.
- Each tool has a median timing; anything over its documented cost is a finding. - Done (R3-I1..I3).
- Every Skill.md claim touched is marked confirmed or corrected; no corrected claim contradicts a live result. - Done.
- Sandbox gone (`Test-Path` False for folder and key), own PIDs gone, clipboard equal to the backup. - Done (726x271 image restored).
