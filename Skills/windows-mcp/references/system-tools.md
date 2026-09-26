# System tools: PowerShell, FileSystem, Registry, Process, Clipboard, Notification

These have no focus problems and are the most reliable way to act on the PC.

## PowerShell (`command`, `timeout` in seconds, default 30)

- Output is UTF-8, with a `Status Code`.
- Each call is a new session starting in the home folder: variables and `cd` do not carry
  over, so use absolute paths.
- Nobody can answer a prompt: `Read-Host` or a confirmation fails with "interactive input is
  not available". Pass the value, or add `-Confirm:$false` / `-Force` / `-Recurse`.
- Errors and warnings come back as plain text. When the command still succeeds (non-terminating
  errors, status 0) the errors follow the output under an `Errors and messages:` heading:
  check for it. A `Write-Warning` line can instead come back inline, among the output.
- A non-zero exit code is a tool error carrying the output and `Status Code`. For commands
  whose non-zero codes mean success pass `success_exit_codes`: `[0, 1]` for findstr
  (1 = no match), `[0,1,2,3,4,5,6,7]` for robocopy.
- On timeout it is a tool error "Command execution timed out after N s" with
  `Status Code: -1`, and the command really is stopped, with anything it started; what it
  printed before is kept. The reply comes ~0.25 s after the timeout. Raise `timeout` for long
  jobs; it must be at least 1.
- Web requests work (Invoke-WebRequest uses the Windows certificate store): the fallback when
  Scrape fails.
- Notification AppIDs: `Get-StartApps`.

## FileSystem (`mode`, absolute `path`)

- `read`: `offset` is a **1-based line number**, plus `limit`. A whole-file read over 10 MB is
  refused; read part of a bigger file with `offset` + `limit`.
- `write`: creates parent folders; `append=true` appends. An existing file is refused unless
  `overwrite=true`. Newlines are written as CRLF.
- `copy` / `move`: an existing destination is refused unless `overwrite=true`. Both create
  missing target folders; `move` also renames.
- `delete`: a non-empty folder is refused unless `recursive=true`.
- `list`: `pattern` filter. `search`: glob; without `recursive=true` it only looks in the top
  folder ("No matches" even when subfolders have hits).
- `info`: size, dates, counts. A folder's "Contents (top level only)" counts only its top level, while its
  "Size" is the total of every file inside, subfolders included, counted up to 10,000 files; a "Size note" line says when it stopped
  early (C:\Windows: 1.4 s).

## Registry (PowerShell-style paths, `HKCU:\...`)

- A path must name a hive (`HKCU:\`, `HKLM:\`, `HKLM\...`, `HKEY_USERS\...`); anything else,
  even an empty path, is refused. `*`, `?` and `[ ]` in a path are plain characters.
- Modes: `get`, `list`, `set` (`type` String | ExpandString | Binary | DWord | MultiString |
  QWord), `delete`.
- `set` creates the key if needed. DWord is stored as a real Int32.
- Binary: pass hex bytes `"01,02,ff"`, `"01 02 ff"`, `"0102ff"` or a decimal list
  `"[1, 2, 255]"`; anything else is refused before writing.
- MultiString: pass a JSON list, `["North","South"]`, for several items; plain text is one
  item.
- `get` and `list` show a value the same way, in the shape `set` accepts: Binary as hex
  (`01,02,ff`), MultiString as a JSON list (`["a","b c"]`). `list` prints one `name : value`
  line each.
- `get` and `list` show ExpandString values already expanded (`%TEMP%` → full path) and do
  not name the type; the stored raw value is intact. Read it raw with PowerShell:
  `(Get-Item 'HKCU:\Environment').GetValue('TEMP', $null, 'DoNotExpandEnvironmentNames')`;
  `.GetValueKind('TEMP')` names the type (`ExpandString`).
- `delete` WITH `name` removes one value; WITHOUT `name` it deletes the key and its values. A
  key with sub-keys is refused unless `recursive=true`.
- A missing key is a plain-text error.

## Process

- `list`: `name` is a plain substring filter ("pwsh" → only pwsh.exe); `sort_by` memory | cpu
  | name; `limit` 1 or more. The CPU% column (a share of the whole machine) appears only with
  `sort_by="cpu"`, which takes ~0.5 s (a half-second sample; memory and name sorts under
  0.05 s). The CPU list leaves out "System Idle Process" (PID 0: idle time, not load); a
  memory or name list still shows it. `details=true` adds
  Started and Command line (secrets shown as [hidden]; `-` when Windows denies it; cut to 200
  characters with "…"): use it to see which program is behind a process, e.g. a hidden
  powershell.exe running a tray script. For a full command line, use PowerShell
  `(Get-CimInstance Win32_Process -Filter "ProcessId=<pid>").CommandLine`.
- `kill`: prefer `pid`; give `pid` **or** `name`, not both. By `name` it is an exact match
  (`.exe` optional) and ends every process with that name. `force` is available. Replies
  "Terminated: exe (PID)".

## Clipboard

- `get` / `set`; Unicode round-trips.
- `get` also names an image (with its size), copied files (by path) and HTML.
- `save_image=<full .png path>` saves a clipboard image to a **new** file (an existing one is
  refused, never overwritten).
- `set` takes exactly one of `text`, `image=<image file>` (pastes as a picture) or
  `files=[full paths]` (like Explorer's Ctrl+C; a paste in a folder copies them).
- So text, an image or a file list can be backed up and restored before you overwrite the
  clipboard; HTML and Office data cannot, so ask first.

## Notification (`title`, `message`, `app_id`)

- `app_id` must be an installed app's AppID from `Get-StartApps`. Both work here:
  `{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe` and
  `Microsoft.Windows.Explorer`.
- An unknown app_id, or notifications turned off for the app, for all apps or by policy, is
  an error, not "sent".
- Do Not Disturb (Focus) cannot be read: with it on, a "sent" toast goes straight to the
  notification centre without a pop-up.
