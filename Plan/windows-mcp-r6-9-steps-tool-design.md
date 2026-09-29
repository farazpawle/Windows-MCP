---
Title: Windows-MCP R6-9 - "Steps" tool design (several input steps in one call)
Description: Design for round-6 R6-9, for the user's approval before any code. A new tool, Steps, runs up to 20 input steps (click, type, shortcut, scroll, move, wait_for) in one call by calling the existing tools through the server itself, so every step keeps today's checks (R6-2 label re-check, R6-3 expect=, still-there checks, new-window notes, action log). All steps are checked before the first runs; the run stops at the first error or at a new window or dialog the step did not allow, and the reply lists each step's outcome and where it stopped. Includes the reply format, limits, what is left out and why, the build and test plan, and three decisions for the user.
---

# R6-9 - "Steps" tool design

## Problem

A short fixed sequence (Ctrl+Shift+S, wait for "Save As", type a name, Enter, wait for the
title to change) costs one model round-trip per step: five calls, each with its reply to read.
Round 4-5 timings put the tools themselves at 0.05-0.3 s a step, so almost all of the time is
the agent's turn between steps, not the desktop.

## What the recipes page already covers

`references/recipes.md` (R6-8) moved the no-UI jobs (edit, copy, count, wait for a file,
drive Explorer) to one PowerShell call. Steps is only for jobs that must go through an app's
UI.

## The tool

`Steps(steps: list[object])`, e.g.

```json
[
  {"do": "shortcut", "shortcut": "ctrl+shift+s", "allow_new_window": true},
  {"do": "wait_for", "condition": "active_window", "text": "Save As", "timeout": 5},
  {"do": "type", "text": "C:\\Temp\\week39.txt", "press_enter": true},
  {"do": "wait_for", "condition": "active_window", "text": "week39.txt", "timeout": 5}
]
```

- `do` names the step type; every other key is that tool's own argument, same names and
  meaning as calling the tool directly. No new argument language to learn.
- Step types: `click`, `type`, `shortcut`, `scroll`, `move`, `wait_for`, `wait` (the tools
  Click, Type, Shortcut, Scroll, Move, WaitFor, Wait).
- One extra key on any step: `allow_new_window` (default false), see "What stops the run".

### How a step runs

Each step is run by calling the registered tool through the server's own tool manager
(`mcp.call_tool(name, args)`), not by re-implementing it. So every step gets, unchanged:
argument checks, coordinate scaling (shrunk screenshots), label still-there checks (R6-2),
`expect=` (R6-3), the held-button release, Type's "now reads" check, the new-window and
in-window-dialog notes (`@note_new_windows`), `is_error` on failure (`@raise_error_replies`
paths), and one action-log line per step (`with_analytics`), so the log shows each step as
if called on its own, plus one line for the Steps call.

### Checked before anything runs

- 1 to 20 steps (a longer job is better split so the agent sees the screen in between).
- Every `do` is a known type; every key is an argument of that tool (checked against the
  tool's own input schema); required arguments are present.
- The waits add up to at most 60 s (`wait` durations plus `wait_for` timeouts), so a run
  cannot hold the client past its own call timeout.
- `Steps` inside `Steps` is refused (not a step type).
A typo in step 4 is refused with its step number before step 1 clicks anything.

### What stops the run

1. A step's tool error (a refused `expect`, a label that moved, a WaitFor timeout, a bad
   value found at run time). Steps after it are not run.
2. A step whose reply names a new window or an in-window dialog ("Note: a new window
   appeared" / "Note: a dialog is open"), unless that step has `allow_new_window: true`.
   The surprises of rounds 3-4 (Notepad's "save changes?", an Avast alert) would otherwise
   receive the remaining keystrokes. A step that opens a dialog on purpose sets the flag, and
   the next step is normally a `wait_for active_window` for it.
3. Nothing else: no time-based stop beyond the checked 60 s of waits.

A stop is a tool error (`is_error=True`) whose text is the whole report below, so the agent
knows which steps already acted.

### The reply

```
Ran 4 of 4 steps.
1. shortcut: Pressed ctrl+shift+s. Note: a new window appeared: "Save As" (handle=..., pid=...).
2. wait_for: Window "Save As" is active (0.4 s).
3. type: Typed 20 characters into the focused element ... Pressed Enter.
4. wait_for: Window "week39.txt - Notepad" is active (0.3 s).
```

On a stop: `Stopped at step 3 of 4: <that step's error>. Steps 4-4 were not run.` after the
lines of the steps that ran. Each step's own reply is kept whole (it carries the checks the
agent relies on); the total goes through `cap_text` (50,000 characters).

## Left out, and why

- **Screenshot / Snapshot / FindText steps:** the agent cannot look at a picture mid-run, and
  a label list taken mid-run could not be used by later steps written before it. Use
  `wait_for` (element, text, window, screen conditions) to wait on the screen inside a run,
  and take a Screenshot after the run.
- **MultiSelect, MultiEdit:** already one call for many items.
- **App, PowerShell, FileSystem, Registry, Process, Clipboard, Notification:** not input
  steps; App `switch` is normally the call before a run. (Clipboard could be useful for the
  Notepad paste workaround, R5-I4; add it only if asked.)
- **Branches, loops, variables, "if this then that":** a script language inside a tool call is
  harder to check and to read in the log than two calls.
- **Retries:** a failed step stops the run; the agent decides what to do next.

## Risks

- **One approval covers up to 20 actions** in Claude Desktop (without "Always allow"). That
  is fewer focus-stealing prompts (golden rule 1), but the user approves the whole list at
  once; the approval dialog shows the full `steps` argument.
- **Coordinates go stale:** `loc` values come from a Screenshot taken before the run, and an
  earlier step can move things. The guide will say: prefer `element=` / `wait_for` over `loc`
  in a run, and put `expect=` on every `loc` click or Type after the first step.
- **Deployments that drop input tools:** Steps only runs step types whose tool is registered;
  a step whose tool was removed with `--exclude-tools` is refused before the run. `Steps`
  itself can be removed the same way.

## Build plan (after approval; tests first)

1. Unit: an unknown `do`, an unknown key, a missing required argument, 0 or 21 steps, and
   waits over 60 s are each refused naming the step, and nothing runs.
2. Unit: steps run in order through the tool manager with their own arguments; the reply has
   one numbered line per step.
3. Unit: a failing step stops the run as a tool error listing the steps done and not run.
4. Unit: a step reply with a new-window or dialog note stops the run; with
   `allow_new_window: true` it continues.
5. Unit: a step whose tool is excluded is refused before the run.
6. Unit: the action log gets one line per step plus the Steps line.
7. Code: `tools/steps.py` with `register()`, added to `tools/__init__.py`; `@with_analytics`
   (no `@note_new_windows` on Steps itself: each step already notes).
8. Guide: `references/input.md` Steps entry, one row in SKILL.md's table, a recipe-style
   example; tool count 21 -> 22 in CLAUDE.md.
9. Live (harness): the four-step save-as above in one call; a deliberately wrong step
   (a `wait_for` on a title that never comes) stops the run and the reply names it; a run
   whose first step opens a dialog without the flag stops before typing.

## Decisions for the user

1. **Name:** "Steps" (recommended: plain, says what it does), or another name.
2. **Step limit 20 and 60 s of waits** (recommended: enough for a dialog flow, short enough
   that the agent looks at the screen often).
3. **New window stops the run unless allowed** (recommended), or only note it and carry on.

**Decided 2026-09-29:** approved as recommended on all three: "Steps", 20 steps and 60 s of
waits, an unallowed new window or dialog stops the run.
