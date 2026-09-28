---
Title: Windows-MCP round 6 - speed and accuracy (plan)
Description: Plan from the 2026-09-28 code audit for making agents drive the desktop faster and land every action where intended. Part A accuracy - App switch confirms the window came to the front, MultiSelect/MultiEdit re-check each item before its click, optional expect= on Click/Type by loc. Part B speed - one cached element search for Click element= (R5-I2), Scroll re-reads the element it found (R5-I1), Registry through winreg instead of PowerShell (also R5-2), a kept-running OCR helper only if the user approves. Part C fewer calls per task - a PowerShell recipes page in the guide, and a new "steps in one go" tool designed first and built only after the user approves. Part D cleanup - one fuzzy-matching library. Part E the user's leftover round-4 checks. Part F one guide pass and one ZIP rebuild at the end. Round-5's open items are slotted into the order. Tasks in Plan/windows-mcp-round6-speed-accuracy-tasks.md.
---

# Goal

An agent's task time is mostly the model thinking between calls (seconds each); the tools
themselves take 0.1-0.3 s except a few slow spots. So round 6 does three things:

1. **Accuracy first** - close the gaps where an input can land in the wrong window or spot.
2. **Speed the slow tools** - the four measured outliers (Click `element=` in a browser 1.5 s,
   Scroll 0.7 s, Registry 0.25-0.33 s a call, FindText 1.2-1.3 s).
3. **Fewer calls per task** - recipes for jobs that need no screen, and one tool that runs a
   short list of input steps in a single call.

No change may trade accuracy for speed: every speed item keeps the reply and the checks it
has today, and is verified to pick the same target as before.

# Findings behind each item (audit 2026-09-28, checked in code)

| Item | Finding | Where |
|---|---|---|
| R6-1 | `bring_window_to_top` logs and swallows a refused `SetForegroundWindow` (pywin32 raises on failure); `switch_app` still replies "Switched to". A following Type with no `loc` goes to the old window. | `desktop/service.py` `switch_app`, `bring_window_to_top` |
| R6-2 | MultiSelect/MultiEdit resolve every label's point once, before the first click; a click that reflows the list sends later clicks to stale points. | `tools/multi.py` (`get_coordinates_from_labels` before `multi_select`/`multi_edit`) |
| R6-3 | Click/Type by `loc` only check the point is on screen. The `element=`/`label=` paths check the target is still there and uncovered; `loc` clicks learn what was hit only from the reply, after the click. | `desktop/service.py` `click`, `type` |
| R6-4 | `find_element` runs one native FindAll, then four uncached cross-process reads per match (box, offscreen, type, name). Tree capture already batches the same reads with a CacheRequest. (Measured 2026-09-28: these reads cost ~0.02 s; the 1.5 s was the throwaway Edge profile slowing every window. See the task file.) | `tree/utils.py` `find_element` |
| R6-5 | Scroll reads its position before, then up to ~6 times while settling; every read re-walks up to 15 ancestors asking each for ScrollPattern. | `tools/input.py` `_settled`, `tree/utils.py` `scroll_position` |
| R6-6 | Every Registry call starts a new PowerShell process (~0.25 s startup). Python's `winreg` does the same in milliseconds with no new dependency, and has no text round-trip (the cause of R5-2's stray `\r`). | `registry/service.py` |
| R6-7 | FindText starts Windows PowerShell 5.1 and reloads the WinRT OCR types every call. A kept-running helper could save most of that, at the cost of crash/restart handling. | `ocr/service.py` |
| R6-8 | Jobs with no screen part (settings, files, process checks) are often done by clicking through menus in 8-10 calls; one PowerShell call does them. | guide |
| R6-9 | Short fixed input sequences (click, type, key, wait) cost one model round-trip per step. | new tool |
| R6-10 | `fuzzywuzzy` (old name) is imported; `thefuzz` (its maintained successor, same API) is also a dependency and unused. CLAUDE.md says fuzzy matching is used for element names; it is used for window and app names only. | `desktop/service.py`, `pyproject.toml`, CLAUDE.md |

# Design notes

- **R6-1:** after the switch, poll `GetForegroundWindow()` for up to 0.1 s and compare it with
  the target or a window the target owns (a dialog it opened comes to the front instead of
  it); on a mismatch retry the switch once, then reply with a tool error naming the window
  that is in front. `switch_app` is the only caller of `bring_window_to_top` (App `launch` does
  not switch).
- **R6-2:** before each click, run the existing still-there check for that label; if it fails,
  stop without clicking and say which item moved and how many clicks were done. No silent
  re-targeting: the agent takes a new Snapshot.
- **R6-3:** optional `expect="<name>"` on Click and Type. Before acting, read the element at
  the point and its ancestors (a click on a button's text hits a Text child); act only if one
  of their names contains `expect` (case ignored), else refuse and name what is there.
  Without `expect` nothing changes. The point is already read for the reply, so the cost is
  a few ancestor reads. On a VS Code-family or not-responding window `expect` refuses
  without reading anything (one tree read freezes VS Code).
- **R6-4:** one CacheRequest for BoundingRectangle, IsOffscreen, LocalizedControlType and
  Name, passed to `FindAllBuildCache`; read the cached values. Verify live that Chromium's
  cached values equal the uncached ones.
- **R6-5:** keep the scrollable element the "before" read found, and have every later read
  ask only that element for its percent; fall back to the walk if it has gone.
- **R6-6:** the tool's inputs and successful replies stay the same; only the engine changes.
  Today's PowerShell behaviour `winreg` does not give for free, each kept on purpose:
  ExpandString shown expanded (`winreg.ExpandEnvironmentStrings`), DWord shown as a signed
  Int32, the `(Default)` value, the wildcard-delete guard, the sub-key refusal, recursive
  delete (pywin32 `win32api.RegDeleteTree`), and refusal of paths naming no hive. Error
  replies change wording (no longer PowerShell's text) but still name the path and reason.
  Registry calls are rarer than clicks, so this sits after the accuracy items.
- **R6-7:** decided by the user after R6-4 to R6-6, with a measured split of where FindText's
  time goes.
- **R6-8:** a `references/recipes.md` page of 10-15 tested PowerShell snippets, each naming
  the click-through it replaces. Text the agent passes to the PowerShell tool, not scripts the
  skill runs itself (in Claude Desktop a skill's own scripts run in Anthropic's sandbox, not
  on this PC; not verified here, and not needed for recipes).
- **R6-9:** design written first as its own Plan file and approved by the user before any
  code. Open questions for the design: step types (click, type, shortcut, scroll, move,
  wait_for), which per-step checks stay (all of today's), what stops the run (first error,
  first failed check, an unexpected new window), the reply (each step's outcome and where it
  stopped), a step limit, and how the action log records it.

- **R6-10:** `thefuzz` keeps `fuzzywuzzy`'s functions but scores through `rapidfuzz`, so a
  name table test pins today's matches first. `python-levenshtein` only sped up
  `fuzzywuzzy` and goes with it.
- **R6-12:** every guide change lands with its item, but the Claude Desktop ZIP is rebuilt
  once at the end, after round-5's guide corrections are applied with round-6 timings.

# Order

R6-1, R6-4, R6-5, R6-2, R6-3, R5-1, R5-3, R5-4, R5-I3, R6-6, R6-10, R6-8, R6-9, R6-7, R6-12,
then the user's R6-11. Reasons: the wrong-window risk first; then the two slowest calls
agents make often (browser element click, Scroll), whose caching work shares one approach;
then the other accuracy gaps and round-5's bugs; Registry and cleanup after, as they touch
rarer calls; recipes before the new tool so the tool's design sees what recipes already
cover; the OCR decision after the other timings are measured; one guide ZIP at the end.
Round-5 items stay in `Plan/windows-mcp-open-issues-round5.md` (R5-I4 is a user decision,
any time); R5-I1, R5-I2, R5-2 and D5-1 to D5-4 are closed by R6-5, R6-4, R6-6 and R6-12.
Each item is its own commit (`fix:`/`feat:`/`docs:` citing the item).

# Out of scope

The PowerShell tool's per-call process start (a kept-running shell would leak variables and
folder between calls), a scripts folder in the guide, multi-monitor, the PyPI release.
