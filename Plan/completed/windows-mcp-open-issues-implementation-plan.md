---
Title: Plan — implement the windows-mcp open-issues backlog (sections 1, 2, 3, 6)
Description: Session plan for fixing every non-[User] item in Plan/windows-mcp-open-issues.md sections 1 (High), 2 (Medium), 3 (Low) and 6 (missing abilities vs computer use), in that order, test-first. Records what the code actually does today (1.3 kill is already exact; 3.4 focused window is already walked first), the chosen fix per item, how each is checked live with a different tool, the Skills/Skill.md update per item, and one commit checkpoint per section on the new branch fix/open-issues-backlog. Section 4/5 items and every [User] item are out of scope.
---

# Implement the windows-mcp open-issues backlog

## Scope

In: every unticked, non-`[User]` item of sections 1, 2, 3 and 6, plus 7.1 (Skill.md kept in step with each fix) and 7.2 (final end-to-end re-read of Skill.md).

Out: 2.4b, 4.1, 4.2 (all `[User]`), section 5 coverage gaps (testing, not fixes; 5.1–5.5 need hardware, network set-up or the blocked browser).

## Ground rules

- Branch `fix/open-issues-backlog` off `fix/uia-hang-and-input-bugs`. One commit per section (1, 2, 3, 6) = the checkpoint. `Skills/Skill.md` gets committed with the section 1 checkpoint (it is untracked today) and updated in every later one.
- Per item: failing test → fix → full suite + `ruff check` → live check → Skill.md edit → tick the backlog.
- Before editing a symbol: GitNexus impact (upstream); warn on HIGH/CRITICAL. Before each commit: GitNexus detect_changes.
- **Live checks.** The running windows-mcp server loaded the old code and only picks up changes after a reconnect (a user action). So each fix is exercised by calling the changed function directly from the repo's Python on this desktop, and the effect is read back with a *different* tool: PowerShell (file/registry/process state), Screenshot (what is on screen), or FileSystem/Registry reads.
- Slow steps (full test suite, Snapshot on a busy desktop) are announced first and run under a hard timeout.

## What the code does today, and the fix

### Section 1 — High

| Item | Found in code | Fix |
|---|---|---|
| 1.1 write ignores overwrite=false | `write_file` never receives `overwrite`. | Pass it through; refuse when the file exists, `overwrite` is false and `append` is false. **Behaviour change:** callers that relied on silent replace must now pass `overwrite=true`. |
| 1.2 "yes" counts as false | The same loose `== 'true'` check is copied in 6 tools. | One strict parser (true/false/yes/no/1/0/on/off, anything else → clear error) in a small shared module, used by FileSystem, Process, MultiSelect, Scrape, Snapshot/Screenshot and Type. Root-cause fix, not FileSystem only. |
| 1.3 fuzzy name filter | `list` uses a 60% fuzzy score (why "pwsh" hit ShellExperienceHost). `kill` is already exact but needs the `.exe` ("pwsh" kills nothing). | `list`: case-insensitive substring match. `kill`: exact name, `.exe` optional. |
| 1.4 key delete wipes sub-keys | `Remove-Item -Recurse -Force` always. | New `recursive` option on Registry; without it a key that has sub-keys is refused with a message naming how many. |
| 1.5 hidden elements listed | Background windows are walked with no occlusion check. | After walking a background window, drop elements whose centre point belongs to a different top-level window (WindowFromPoint → root ancestor). Applied to the flat lists (labels, annotation) and the text tree alike. Desktop icons (Progman/WorkerW) treated as one window. |

### Section 2 — Medium

| Item | Found in code | Fix |
|---|---|---|
| 2.1 errors dropped at exit 0 | `output = stdout or stderr`, and stderr is CLIXML. | Always append stderr, decoded from CLIXML to plain error lines. |
| 2.2 timeout=0 | Passed straight to the subprocess timeout. | Reject values below 1 with a clear message (no "no timeout" mode — a stuck command would hang the server). |
| 2.3 binary values | Value passed as one string. | Accept "01,02,ff", "01 02 ff", "0102ff" and a JSON list; build a real byte array. |
| 2.4 toast "success" | Reports success whatever happens. | Check the app id exists (reuse the existing Start-apps lookup) and read the Windows "notifications on" and per-app switches; report a clear warning instead of success when one is off. Focus Assist / Do Not Disturb state has no supported API — the reply will say it cannot be checked. |
| 2.5 "No windows found" | Screenshot never lists windows but prints the empty-list text. | Screenshot prints "Skipped (screenshot-only; use Snapshot for windows)". |
| 2.6 Screenshot grid ignored | Grid is only drawn on the annotated path; Screenshot is not annotated by default. | Draw the grid whenever grid lines are asked for. |
| 2.7 summary skipped silently | Sampling error swallowed. | Add "Note: summary unavailable in this client; raw content returned." |

### Section 3 — Low

| Item | Fix |
|---|---|
| 3.1 clicks outside 0–2 | Accept 0–3 (3 = triple click, a computer-use action), reject anything else with an error. |
| 3.2 MultiSelect wording | "Ctrl-selected …" vs "Clicked in sequence …". |
| 3.3 no label ids in text | Print `[label:N]` on each interactive/scrollable line, same numbering Click/Type `label=` uses. |
| 3.4 500-cap filled by VS Code | The focused window is **already walked first**, so when VS Code is focused it is expected to fill the cap. First reproduce with VS Code in the background; if the focused window still gets its share, close as not-a-bug and correct Skill.md (point to `region` / `WINDOWS_MCP_MAX_TREE_ELEMENTS`). Only if it does not, reserve part of the budget for the focused window. |
| 3.5 App switch needs long title | After the fuzzy match fails, try a case-insensitive substring of the title (zero-width spaces removed), then the process name. Also helps `resize`, which shares the lookup. |

### Section 6 — missing abilities

| Item | Fix |
|---|---|
| 6.1 Click with modifiers | `modifiers` option (e.g. `"shift"`, `"ctrl+alt"`): held down for the click, always released afterwards even on error. |
| 6.4 Scroll/drag with modifiers | Same `modifiers` option on Scroll and on Move drags (shared helper). |
| 6.2 Hold a key | Shortcut `hold` seconds (max 10): keys pressed, held, released. |
| 6.5 Repeat a key | Shortcut `repeat` count (1–100). |
| 6.3 Mouse down / up | Move `button_action="press"` or `"release"` (left button) for custom drags. Skill.md will warn to always release. |
| 6.6 Click/type in place | Click without `loc`/`label` clicks at the pointer; Type without them types into the focused field (no click). |
| 6.7 Decimal waits | Wait accepts decimals; negative or non-finite values rejected. |

## Validation per section

`ruff check .`, `ruff format` on touched files, full `pytest` suite, the new tests, one live check per item with a different tool, self-review of the diff, GitNexus detect_changes, then the checkpoint commit.

## Risks

- 1.1 and 1.2 change behaviour on purpose (stricter). Documented in Skill.md.
- 1.5 could hide a genuinely visible element if an app draws through another window's rectangle (transparent overlays). Mitigation: only background windows are filtered, never the focused one.
- 6.3 can leave the left button held if an agent forgets `release`; documented.
