---
Title: Windows-MCP round 5 - re-test of the round-4 fixes (tasks)
Description: Task list for Plan/windows-mcp-round5-retest-plan.md - restart the connected server on the committed code, run the round-4 "weekly sales report" job through all 21 tools with a re-check of every round-4 fix (R4-1 to R4-16, R4-I1 to R4-I7, R4-N1, R4-N2) checked a second way and timed from the MCP log, then write the Round 5 report section and a round-5 backlog if anything fails. Test only, no code changes. Status 2026-09-26: all done except [User] 8.6; every round-4 fix held; findings in Plan/windows-mcp-open-issues-round5.md.
Total Tasks: 53
---

# 1. Prepare

- [x] 1.1 [User] Restart the windows-mcp server Claude Code is connected to (needs the user: `/mcp` reconnect or a new Claude Code session; the agent cannot restart its own connection).
- [x] 1.2 Confirm the connected server is the repo build: Type's description lists `field_start`.
- [x] 1.3 Check the server start wrote no uv warning (MCP log stderr) (R4-14).
- [x] 1.4 Check no window is "Not Responding".
- [x] 1.5 Back up the clipboard.
- [x] 1.6 Ask the user for a hands-off window and say how long the input steps take.
- **Verify:** 1.2 and 1.3 recorded with the log lines; clipboard backup file exists.

# 2. Look around

- [x] 2.1 Screenshot full (first capture of the session): Backend line (R4-11).
- [x] 2.2 Measure the Screenshot reply length (R4-I5).
- [x] 2.3 DisplayInventory.
- [x] 2.4 App `list`: order against a GetTopWindow walk, front marker (R4-I6).
- [x] 2.5 App `list`: maximized windows' rectangles against the work area (R4-12).
- **Verify:** each value compared with a PowerShell / win32 reading.

# 3. Set up the work (no screen input)

- [x] 3.1 FileSystem write the sales CSV and notes; read back with PowerShell.
- [x] 3.2 FileSystem folder `info`: "Contents (top level only)" wording (R4-15).
- [x] 3.3 Registry set and get every value type under `HKCU:\Software\WMCP-Test`.
- [x] 3.4 PowerShell CSV total and one failing command.
- [x] 3.5 PowerShell `timeout=2` on an 8 s sleep: time and status (R4-10).
- [x] 3.6 PowerShell with a fake `-Token "..."`: closing quote kept in the action log / details (R4-15).
- **Verify:** raw values read with .NET / PowerShell; the timeout reply under 2.6 s.

# 4. Processes

- [x] 4.1 Process list by memory: time (R4-I1).
- [x] 4.2 Process list by CPU: time, no System Idle Process (R4-I1).
- [x] 4.3 Process list `details=true limit=5`: reply length (R4-I2).
- [x] 4.4 Kill a throwaway process by PID; confirm gone.
- **Verify:** times from the MCP log; reply length counted.

# 5. Typing (harness text box)

- [x] 5.1 Open the live-test harness text box.
- [x] 5.2 Type the 622-character multi-line report: time and exact text (R4-1).
- [x] 5.3 Type with `caret_position="start"` and `"end"` on a middle line (R4-6).
- [x] 5.4 Type with `field_start` and `field_end` (R4-N1).
- [x] 5.5 Check Type's read-back count against the box (R4-7).
- [x] 5.6 Click `clicks=2` on a word, then Type "X": time and selection (R4-I4).
- [x] 5.7 Move drag across the text, then Type "X": time and selection (R4-I4).
- [x] 5.8 Close the harness window.
- **Verify:** every result judged from the harness `.text` file, not the reply.

# 6. Notepad test tab

- [x] 6.1 App `launch name=Notepad` with a Notepad already open: reply names the new window and handle (R4-2).
- [x] 6.2 Open a new test tab; check its runtime id before each key.
- [x] 6.3 Type the 622-character report into it: exact, or the reply warns (R4-16).
- [x] 6.4 Snapshot the Notepad region; Click `label=` on a mid-line word; Type "X" (R4-3).
- [x] 6.5 WaitFor `text_exists` of a phrase in the document: time (R4-4).
- [x] 6.6 WaitFor `text_exists` of a missing phrase: error names the active window (R4-4).
- [x] 6.7 Scroll three times: each "now" equals the next "was" (R4-7).
- [x] 6.8 Open Find and Replace (Ctrl+H); Snapshot: no word under the panel (R4-13).
- [x] 6.9 Click `element="button:Replace all"`: reply names the button (R4-8).
- [x] 6.10 FindText full screen "North 460 units": no text joined from another window (R4-9).
- [x] 6.11 FindText `window=` Notepad: one match (R4-N2).
- [x] 6.12 Ctrl+W on the modified tab, then Move: reply names the "save changes" dialog once (R4-5).
- [x] 6.13 Press "Don't save"; check the user's tabs are intact.
- **Verify:** Notepad text read through TextPattern; clicks checked by the typed "X".

# 7. Windows, web, pop-ups

- [x] 7.1 Maximize a test window; App `resize`: refusal names `mode="restore"` (R4-I7).
- [x] 7.2 MultiSelect two files in a test Explorer window.
- [x] 7.3 Edge with a throwaway profile: Scrape `use_dom`; WaitFor names Edge in plain quotes (R4-15).
- [x] 7.4 Notification toast; find it by FindText.
- [x] 7.5 Clipboard set / get round trip; restore the backup.
- **Verify:** Explorer selection count; Edge profile folder deleted; clipboard equals the backup.

# 8. Report

- [x] 8.1 Pull every call's time from the MCP log into a timing table.
- [x] 8.2 Write the Round 5 section of `docs/testing/windows-mcp-tool-test-report.md`.
- [x] 8.3 Compare the guide and tool descriptions with the results; list corrections.
- [x] 8.4 Write `Plan/windows-mcp-open-issues-round5.md` for any failure or correction.
- [x] 8.5 Clean up: registry key, scratch folders, own windows and processes.
- [ ] 8.6 [User] Settle round-4 R4-11c (optional lock/unlock check) and D.33 (upload the guide ZIP): both need the user at the PC or in their Claude account.
- **Verify:** clean-up checked with PowerShell; report frontmatter updated.

# Implementation verification

- Every re-check row of the plan's table has a pass/fail with its evidence and time.
- Nothing judged from a tool reply alone; each change checked a second way.
- Clipboard restored and equal to the backup; the user's Notepad tabs intact; no test window,
  process, registry key or folder left.
- A failure is recorded as a round-5 backlog item, not fixed in this round.
