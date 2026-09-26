---
Title: Windows-MCP round 5 - re-test of the round-4 fixes (plan)
Description: Plan for a round-5 real-work scenario test after the round-4 backlog (Plan/windows-mcp-open-issues-round4.md): the same "weekly sales report" job as round 4, driven through the connected windows-mcp server, re-running every step that failed or was slow in round 4 (R4-1 to R4-16, R4-I1 to R4-I7, R4-N1, R4-N2) against the fixed code, each checked a second way and timed from Claude Code's MCP log. Test only: no code changes; new findings go to a round-5 backlog. Tasks in Plan/windows-mcp-round5-retest-tasks.md; results in docs/testing/windows-mcp-tool-test-report.md, section "Round 5".
---

# Goal

Prove, through the MCP connection an agent really uses, that the round-4 fixes hold in a real
job, and find what is still wrong or slow. Unit tests and the in-process live tests already
passed; this round checks the connected server, the guide and the timings end to end.

# Scope

In: all 21 tools, with extra weight on the round-4 items below. Out: code changes (a failure
becomes a round-5 backlog item), the PyPI release, multi-monitor (one screen here).

| Round-4 item | Re-check | Pass when |
|---|---|---|
| R4-1, R4-16 | Type 622 multi-line characters into the harness text box, then into a Notepad test tab | harness exact under 1 s; Notepad exact, or the reply warns the text is missing |
| R4-2 | App `launch name=Notepad` with a Notepad already open | reply names the new window and its handle |
| R4-3 | Snapshot a Notepad test tab, Click `label=` on a mid-line word, Type "X" | X lands inside that word |
| R4-4 | WaitFor `text_exists` of a phrase inside the document; and of a missing phrase | found under 0.5 s; timeout error names the active window |
| R4-5 | Ctrl+W on a modified test tab, then any input call | reply names the "save changes" dialog once |
| R4-6, R4-N1 | Type with `caret_position` start / end / field_start / field_end in a multi-line box | line vs whole-field placement as described |
| R4-7 | Three Scrolls in a long document | each "now" equals the next call's "was" |
| R4-8 | Click `element="button:Replace all"` in Notepad's Find panel | reply names `button "Replace all"` |
| R4-9, R4-N2 | FindText full screen and `window=` Notepad, with the chat showing the same phrase | full screen joins no windows; `window=` finds one match |
| R4-10 | PowerShell `timeout=2` on an 8 s sleep | reply under 2.6 s, status -1 |
| R4-11 | First full Screenshot of the session | Backend line reads dxcam, or says why not |
| R4-12, R4-I6 | App `list` | maximized windows at the work area; front to back; front marked |
| R4-13 | Snapshot with the Find panel open | no word under the panel |
| R4-14 | Server start | no uv warning on stderr |
| R4-15 | PowerShell with a fake `-Token`, WaitFor on Edge, FileSystem folder info | closing quote kept; plain titles; "Contents (top level only)" |
| R4-I1, R4-I2 | Process list by memory, by CPU, `details=true limit=5` | memory under 0.1 s, CPU ~0.5 s, no Idle; details under 2,000 characters |
| R4-I4 | Click `clicks=2`, Move drag | double under 0.3 s, drag under 0.6 s |
| R4-I5 | Screenshot reply | under 400 characters, no empty tables |
| R4-I7 | Resize a maximized window | refusal points to App `mode="restore"` |

# Approach

1. Restart the connected server so it runs the committed code (it runs the code it started
   with), then confirm it is the repo build (Type description lists `field_start`).
2. Run the round-4 job in the same order (files, registry, PowerShell, processes, Notepad
   report, Explorer pick, OCR, Edge, toast, pop-ups), inserting the re-checks above where the
   job reaches them. Input steps only while the user is hands-off.
3. Check every change a second way (PowerShell reads, window rectangles, clipboard, harness
   text file), never by the tool's reply alone.
4. Time every call from the MCP log; compare with round 4 and the guide's timings.
5. Compare the guide (`Skills/windows-mcp/`) and each tool description with what happened.

# Safety

Windows 11 Notepad restores the user's tabs: use only a new test tab, close it with Ctrl+W and
"Don't save", never close or kill the window. Back up the clipboard before the first copy and
restore it after. Never read the UI tree of a VS Code-family window. Throwaway Edge profile in
the scratch folder, deleted after. Registry work only under `HKCU:\Software\WMCP-Test`.

# Expected outcome

The Round 5 report section (verdict per tool, timing table, bugs, improvements, guide check),
a round-5 backlog file if anything failed, and the round-4 files moved to `Plan/completed/`
once their `[User]` items are settled.
