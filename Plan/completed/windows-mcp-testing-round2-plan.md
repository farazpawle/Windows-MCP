---
Title: Windows-MCP testing round 2 - plan
Description: Second round of rigorous live testing of all 20 windows-mcp tools (2026-09-22), after every item in Plan/completed/windows-mcp-open-issues.md was fixed. Checks the seven section 6 abilities hard (bad values, limits, mixed options, mid-call errors, no stuck keys/buttons), re-tests every earlier fix, probes untried edge cases, runs chained real workflows checking every reply is truthful, and re-checks Skills/Skill.md line by line. No fixes this round; output is a new backlog (Plan/windows-mcp-open-issues-round2.md) and an updated docs/testing/windows-mcp-tool-test-report.md.
---

# Windows-MCP testing round 2 - plan

## Goal
Prove the round-1 fixes hold and find new bugs. Record, don't fix.

## Pre-check (done 2026-09-22 14:26)
The live tools run current code: Click offers `modifiers`, Move offers `mouse_button`, Shortcut offers `hold`/`repeat`, Wait accepts decimals.

## Test bed
- The round-1 WinForms harness in `%TEMP%\wmcp-test` (`harness.ps1`): logs every mouse and key event and writes control state to `state.json` every 300 ms. It is the second, independent check for all input tests, including "no key or button left held" (checked with `GetAsyncKeyState` from PowerShell after each test).
- Notepad and Calculator launched by the agent, closed by their own PID. Edge only in a new tab the agent opens, closed by the agent.
- Destructive work only in `%TEMP%\wmcp-r2` and `HKCU:\Software\WMCP-Test`.
- Never read a VS Code-family window. Snapshot/WaitFor are scoped to the test window where possible.

## Order of work (each block uses the windows-mcp-tool-tester skill for its tool)
1. **Section 6 abilities** - Click/Scroll/drag `modifiers`, Shortcut `hold`/`repeat`, Move `mouse_button`, Click/Type without location, decimal Wait. Bad values, limits, mixed options, errors partway through, held-key check after each.
2. **Regressions of sections 1-5** - one check per old item, verified a second way.
3. **Edge cases** - empty/huge input, Unicode/emoji, paths with spaces, very long text, minimised/maximised/off-screen windows, rapid back-to-back calls. High-DPI: this PC runs 100% scaling; changing it needs a sign-out, so only what can be done without that is tested (see [User] task).
4. **Chained workflows** - e.g. launch Notepad, type, save via dialog, read back, delete, close; registry write/read/delete chain; clipboard round-trip into an app. Each "done" checked against reality.
5. **Skills/Skill.md** - every claim checked against observed behaviour.
6. **Write-up** - backlog file grouped by priority, report updated.

## Interruptions to the user
Blocks 1, 3 and 4 take over mouse and keyboard for a few minutes each. The agent announces each block before starting it.

## Bug record format
Tool, exact steps, what happened, what should happen, severity (High/Medium/Low), suggested fix.
