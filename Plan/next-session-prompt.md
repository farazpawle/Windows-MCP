---
Title: Prompt to start the second round of rigorous windows-mcp testing
Description: Copy-paste prompt for the next session. It starts a fresh bug hunt across all 20 windows-mcp tools after the whole open-issues backlog was fixed (Plan/completed/). It covers the new section 6 abilities, re-checks for regressions of earlier fixes, edge cases and combined workflows, and the safety rules learned so far. Output is a new backlog file and an updated test report. Nothing gets fixed without the user's approval.
---

Copy everything below this line into the next session:

Run a second round of rigorous testing on windows-mcp and find the bugs. Every item in the first backlog (Plan/completed/windows-mcp-open-issues.md) was fixed on 2026-09-22. This round checks that those fixes hold and looks for new problems.

**Before testing**
- Confirm the live windows-mcp tools run the current code. For example, the Click tool must offer `modifiers` and Move must offer `mouse_button`. If they don't, stop and ask me to reconnect (`/mcp`).
- Write a plan and task file in Plan/ covering what gets tested, then ask me to approve it.
- Use the windows-mcp-tool-tester skill for each tool's test pass.

**What to test**
1. The seven new abilities from section 6: Click/Scroll/drag `modifiers`, Shortcut `hold` and `repeat`, Move `mouse_button` down/up, Click and Type with no location, and decimal Wait. Try bad values, limits (repeat 100, hold 10), mixed options, and errors partway through. After each test, check that no key or mouse button is left held down.
2. Regressions of every earlier fix (sections 1-5 of the old backlog): FileSystem overwrite and true/false values, Process kill by name, Registry recursive delete, hidden elements in Snapshot, PowerShell errors and timeout, binary registry values, Notification checks, Screenshot grid, Scrape notes, click counts, label ids, App switch/launch/resize, Snapshot region, multi-monitor, screenshot backends.
3. Edge cases no one has tried yet: empty or huge inputs, Unicode and emoji, paths with spaces, very long text, windows that are minimised, maximised or off-screen, high-DPI or scaled coordinates, and rapid back-to-back calls.
4. Real workflows that chain several tools, such as open an app, fill a form, save, read the file back and clean up. Also check that each reply tells the truth: every "done" must match what actually happened.
5. Check that Skills/Skill.md still matches real behaviour, line by line.

**How to work**
- Do the testing yourself. Mark something [User] only when it truly can't be done by an agent, and say why.
- Verify each result a second way (a Screenshot, a file read, a registry read with PowerShell, or the process list). Never trust a tool's own reply alone.
- Safety: never read VS Code-family windows (they freeze). Test on small windows you launch yourself. Keep destructive tests to the %TEMP% test folder and HKCU:\Software\WMCP-Test. End processes by the PID you launched only, and close only your own tabs (Notepad and Edge share windows with my tabs).
- Tell me before any step that takes more than a few seconds or takes over the mouse and keyboard.
- Don't fix anything yet. For each bug, record the tool, the exact steps, what happened, what should happen, how serious it is, and a suggested fix.

**Output**
- A new backlog file, Plan/windows-mcp-open-issues-round2.md, grouped by priority like the first one.
- An updated docs/testing/windows-mcp-tool-test-report.md with this round's results.
- At the end, a short summary of what was found, and ask me which bugs to fix.
