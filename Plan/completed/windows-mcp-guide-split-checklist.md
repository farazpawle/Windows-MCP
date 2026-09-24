---
Title: Tool guide split - fact checklist (round-3 D.1l)
Description: Side-by-side check for task D.1 of Plan/windows-mcp-open-issues-round3.md. Every fact of the old one-file guide (Skills/windows-mcp/SKILL.md at commit 9fea0bb, 127 lines) is mapped to the line or section of the new files that holds it (SKILL.md plus references/). Dropped items are only test dates and evidence (kept in docs/testing/windows-mcp-tool-test-report.md). Also lists facts that were corrected or added during the split.
---
# Guide split: fact checklist

Old = `git show 9fea0bb:Skills/windows-mcp/SKILL.md`. New files: `SKILL.md` (main) and
`references/` observe (obs), input (inp), apps-windows (app), system-tools (sys), web,
pypi-differences (pypi), known-gaps (gaps). "Dropped" = test date or evidence only.

| Old line | Fact | New home |
|---|---|---|
| 1-4 | frontmatter name, description | main 1-4 (unchanged) |
| 5 | title with test dates | main title (dates dropped) |
| 8 | both clients run local repo; command | main "Which server" |
| 8 | PyPI notes for other machines/configs | main "Which server" |
| 8 | PyPI notes describe pre-fix builds, not re-checked | pypi intro |
| 9 | 1 display 1920x1080 at PC, 2560x1440 over RDP, shrunk x0.75 | main "This machine" |
| 9 | local coords follow image, PyPI's do not | inp "Shrunk screenshots"; pypi Apps and windows (last bullet) |
| 9 | 100% scale, PowerShell 7.6, Avast, OneDrive Desktop | main "This machine" |
| 11 | per-tool costs | main "Typical cost per call" |
| 15 | frozen app used to block Snapshot/WaitFor/App switch; now skipped, ~0.2 s | main rule 8 |
| 15 | PyPI may still hang | pypi General |
| 15 | IsHungAppWindow check command; ask user to close app | obs "Frozen-app check" |
| 15 | Screenshot never hangs this way | main rule 8 |
| 16-20 | approval prompts steal focus (Desktop only, not Code); chat typing; Shortcut to Claude; mitigations; no press_enter | main rule 1 |
| 21 | verify by effect | main rule 2 |
| 21 | local flags failures as errors; PyPI returns normal replies | main rule 2; pypi General |
| 22 | kill by PID; Notepad one process; name kill ends all | main rule 3 |
| 22 | local list = substring filter, kill by name exact, .exe optional | sys Process |
| 22 | PyPI fuzzy filter (ShellExperienceHost) | pypi Process |
| 23 | absolute paths; relative = OneDrive Desktop | main rule 4 |
| 24 | sandbox in %TEMP% / HKCU test key, clean up | main rule 5 |
| 25 | real booleans; yes/no/1/0/on/off; other words error | main rule 6 |
| 25 | PyPI other strings false (recursive="yes") | pypi General |
| 26 | VS Code family never read; which apps; Screenshot+coords; don't set READ_VSCODE | main rule 7 |
| 26 | Antigravity program name `Antigravity IDE.exe` | main rule 7 (history of the miss dropped) |
| 26 | PyPI reads them and freezes VS Code | pypi General |
| 33 | FindText: OCR, for games/RDP/canvas, text rules, region, spots within 1 px | obs FindText |
| 33 | not found = normal reply; timings; visible pixels only | obs FindText |
| 33 | phrase across table columns missed, search one word | gaps (R3-I6) |
| 33 | prefer Snapshot / element= | obs FindText |
| 33 | FindText local only | pypi Observe |
| 34 | DisplayInventory: bounds, DPI, scale; run first; scale 1.0 | obs DisplayInventory |
| 35 | Screenshot: no tree/window list, "Skipped" message | obs Screenshot; main "Which server" (tell-apart) |
| 35 | PyPI "No active window found" = not checked | pypi Observe |
| 35 | bad display index error; captures approval prompts; reference lines, either alone | obs Screenshot |
| 35 | PyPI ignored reference lines | pypi Observe |
| 35 | one screen: dxcam, shows pop-ups | obs Screenshot |
| 35 | several screens / PyPI: pillow can miss pop-up, use region | gaps (R3-2); pypi Observe |
| 36 | `[label:N]` ids, order not tree order | obs Snapshot |
| 36 | only Snapshot sets labels | obs Snapshot |
| 36 | PyPI renumbers labels after WaitFor/capture | pypi Observe |
| 36 | re-check before label action, "take a new Snapshot" | obs Snapshot; inp "Spot check" |
| 36 | PyPI label ids only on annotated image, prefer loc | pypi Observe |
| 36 | region keeps only elements inside | obs Snapshot |
| 36 | covered background elements left out; PyPI lists them | obs Snapshot; pypi Observe |
| 36 | focused window first, 500 cap, truncation message, busy window, region or raise env var | obs Snapshot |
| 36 | region limits reading (0.3 s vs 22 s); PyPI reads everything first | obs Snapshot; pypi Observe |
| 36 | display=[0]/[1]/[0,1], virtual-desktop coords, clicks land, border on that screen | obs Snapshot (test date dropped) |
| 36 | layout re-read every call; PyPI remembers from start; 8 px wide windows | obs Snapshot; pypi Observe |
| 36 | reference-line grid with use_vision, either alone | obs Snapshot |
| 37 | WaitFor conditions and parameters | obs WaitFor |
| 37 | returns time + attempts; timeout error names active window; cheaper than Snapshots | obs WaitFor |
| 37 | text_exists scope incl. plain labels | obs WaitFor |
| 37 | PyPI text_exists buttons/fields/titles only, ignores window_name | pypi Observe |
| 37 | screen_text (OCR per look) | obs WaitFor (speed corrected, see below) |
| 37 | screen_changed behaviour, box incl. drop shadow, misses change during prior click | obs WaitFor |
| 37 | screen_idle, settle default 1, < timeout, use after click | obs WaitFor |
| 37 | tiny = <100 px or <1% of small region, min 20; clock example | obs WaitFor |
| 37 | watch every screen unless region; give region | obs WaitFor |
| 37 | PyPI: no screen_* conditions, fixed 100 | pypi Observe |
| 38 | Wait: 3 s took 3.4 s; decimals; max 300; refuses negative/non-numeric; prefer WaitFor | obs Wait |
| 38 | PyPI whole seconds, no limit | pypi Observe |
| 42 | launch_executable: full path or PATH name; args list; cwd; returns pid, save it | app launch_executable |
| 42 | PID can be a stub; check alive; find real with Process list | app launch_executable (example PIDs dropped) |
| 42 | pwsh example args | app launch_executable |
| 43 | launch: Start Menu, fuzzy; unknown name reply; real title; empty refused | app launch |
| 43 | PyPI echoes your text | pypi Apps and windows |
| 43 | no PID; Store apps reuse window | app launch |
| 44 | switch/resize fuzzy title, then part of title, then program name | app "How a window name matches" |
| 44 | several matches: best + "Also matched"; empty refused | app "How a window name matches" |
| 44 | PyPI needs long fragment (zero-width space) | pypi Apps and windows |
| 45 | approval click undoes switch | app switch |
| 46 | resize params; outer rect exact, frame smaller; either alone | app resize |
| 46 | PyPI no-name resize uses last-capture window; local uses front window | pypi Apps and windows; app resize |
| 46 | maximized/minimized refused; bad size/loc refused | app resize |
| 47 | minimize/maximize/restore/close/list/move details | app "minimize / ... / move" |
| 47 | handle= for all window modes | app "How a window name matches" |
| 47 | PyPI has none of these | pypi Apps and windows |
| 48 | non-maximizable windows listed | app "How a window name matches" |
| 48 | PyPI leaves them out; workarounds | pypi Apps and windows |
| 48 | whole title wins; Also matched only same titles | app "How a window name matches" |
| 49 | bare name only PATH; msedge full path | gaps (R3-I5) |
| 49 | new Notepad on missing file asks "create a new file?" | app launch_executable |
| 56 | Click targets; clicks 0-3; other values refused | inp Click |
| 56 | PyPI "None … clicked", negative single-clicks | pypi Input |
| 56 | modifiers (values, aliases, released, not with clicks=0) | inp Click (Notepad evidence dropped) |
| 56 | no loc/label clicks at pointer | inp Click |
| 56 | off-display points refused, all input tools | inp Click |
| 56 | PyPI clamps to edge; no modifiers; Ctrl-click via MultiSelect, no Shift-click | pypi Input |
| 56 | element= search, exact/partial, refusals, type names, leading ':', not with loc/label | inp Click |
| 56 | free point when centre covered; refusal causes | inp "Spot check" |
| 56 | Chromium first search empty, retry ~2 s | inp Click |
| 56 | identical duplicates told apart | inp Click |
| 56 | right-click menu ~1 s later, WaitFor first | inp Click |
| 57 | Type: clicks loc first; no loc types into focus | inp Type |
| 57 | PyPI requires loc/label | pypi Input |
| 57 | clear=true, old-style boxes | inp Type |
| 57 | PyPI clear deletes one char and appends | pypi Input |
| 57 | caret_position, press_enter danger | inp Type |
| 57 | accents, CJK, emoji OK; keystrokes, no clipboard, 2,000 chars | inp Type |
| 57 | PyPI emoji wrong; clipboard paste 20+ chars loses image/files | pypi Input |
| 57 | empty text + clear clears; PyPI raises index error | inp Type; pypi Input |
| 58 | MultiEdit params, clears each field, checks all first, stops and lists | inp MultiEdit |
| 58 | PyPI corner + silent failures | pypi Input |
| 59 | MultiSelect press_ctrl true/false, replies | inp MultiSelect |
| 59 | PyPI "multi-selected" either way | pypi Input |
| 60 | Scroll params, 1 wheel = 3 lines, axis/type, bad direction error, sideways any app, ctrl zoom | inp Scroll |
| 60 | PyPI wheel_times <=0, Shift+wheel vertical | pypi Input |
| 61 | Move hover, drag, duration, pixel-exact, modifiers with drag | inp Move |
| 61 | mouse_button down/moves/up, loc optional, always send up | inp Move (Notepad evidence dropped) |
| 61 | second down / up with nothing refused; next action releases and says so | inp Move |
| 61 | PyPI keeps button held; no modifiers/mouse_button; refuses no-loc Move | pypi Input |
| 61 | no-loc Move replies cursor position | inp Move |
| 62 | Shortcut names, xdotool names, Return/BackSpace | inp Shortcut |
| 62 | PyPI knows none; use pagedown, win, ctrl+= | pypi Input |
| 62 | repeat, hold, no auto-repeat, not combined | inp Shortcut |
| 62 | release_all | inp Shortcut |
| 62 | hits focus, Claude after approval, unreliable unless Always-allow | inp Shortcut |
| 62 | misspelled key refused; PyPI leaves Ctrl held | inp Shortcut; pypi Input |
| 64 | coordinates: Snapshot centres, re-snapshot after move/resize/scroll | inp Coordinates |
| 66 | what replies report; VS Code/frozen named not read; evidence not guarantee | inp "What the replies report" |
| 66 | PyPI replies only echo | pypi General |
| 68 | shrunk screenshot rules | inp "Shrunk screenshots" |
| 68 | zoom=true | obs Screenshot (pointer in inp) |
| 68 | window_loc/size and DisplayInventory stay real pixels; RAW_COORDINATES | inp "Shrunk screenshots" |
| 68 | PyPI no zoom; screen pixels, multiply by scale | pypi Observe; pypi Apps and windows |
| 70 | system tools most reliable, no focus issues | main "Which tool"; sys intro |
| 74-79 | PowerShell: UTF-8, status, new session, prompts fail, errors heading, exit codes, success_exit_codes, timeout, web requests, Get-StartApps | sys PowerShell |
| 75-77 | PyPI Read-Host empty, errors dropped + wrapper, timeout reply, timeout=0 | pypi PowerShell |
| 83-88 | FileSystem modes | sys FileSystem |
| 83, 85, 88 | PyPI overwrite, 10 MB, folder 4 KB | pypi FileSystem |
| 92 | registry path rules | sys Registry |
| 92 | PyPI wildcards, file-system paths | pypi Registry |
| 94-101 | registry modes, set, Binary, MultiString, get/list shape, ExpandString, delete, missing key | sys Registry |
| 96, 98-101 | PyPI Binary single byte, MultiString one item, decimal list, tree delete, CLIXML | pypi Registry |
| 105-106 | Process list/kill | sys Process |
| 105 | CPU% whole machine; ~1.6 s | sys Process; main cost |
| 105-106 | PyPI limit=0, CPU summed, pid+name | pypi Process |
| 108 | Clipboard get/set, image/files/HTML, save_image, set variants, backup | sys Clipboard |
| 108 | PyPI non-text can't be saved | pypi Clipboard |
| 110 | Notification app_id rules, two working AppIDs, errors, DND | sys Notification |
| 110 | PyPI success for fake app_id | pypi Notification |
| 114 | Scrape HTTP works, Windows store, Avast accepted, private addresses blocked | web HTTP mode |
| 115 | PyPI Scrape fails / crashes; use WebFetch or PowerShell | pypi Scrape |
| 116 | use_dom reads active tab; Snapshot use_dom labels; msedge new tab; switch; Ctrl+W; top/middle/bottom line | web Browser mode; obs Snapshot |
| 116 | PyPI "Reached top … Scroll down" | pypi Scrape |
| 117 | viewport only; use_sampling; Claude Code raw + note; query filtering | web "What comes back" |
| 117 | PyPI ignores query | pypi Scrape |
| 118 | 50,000-character cap on Scrape/Snapshot/PowerShell/FileSystem/Process | web "What comes back" |
| 118 | PyPI no cap | pypi General |
| 120-127 | UI workflow 1-6 | main "UI workflow" |
| 122 | PyPI needs use_vision for label ids | pypi Observe |

## Corrected during the split

- WaitFor `screen_text` speed: old "~2.5 s full screen" was the tool description's figure;
  measured 1.24 s for the same OCR (round-3 timing pass), so obs WaitFor says ~1.2 s.
- Notification PowerShell AppID: old text read `WindowsPowerShell1.0` (a lost backslash);
  sys Notification gives `WindowsPowerShell\v1.0\powershell.exe`, as the tool's own error
  message does.

## Added during the split

- main "Which server": how to tell the local repo from PyPI (label lines, Screenshot message).
- main "Which tool for which job" table and reference list.
- inp Type: never `clear=true` in an Explorer file list (learned in the R3-3 live test).
- gaps: Process command lines (R3-I10), App list positions (R3-I11), pop-ups not announced
  (R3-N1), empty `window ""` lines (R3-I8), from the round-3 backlog.

## Result

Every old fact is mapped; nothing is unmapped. Dropped: test dates, "verified/proven live"
notes, example PIDs and the Notepad evidence of Click/Move behaviour.
