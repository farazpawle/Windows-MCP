# System tools: PowerShell, FileSystem, Registry, Process, Clipboard, Notification

These have no focus problems and are the most reliable way to act on the PC.

## PowerShell (`command`, `timeout` in seconds, default 30)

- Output is UTF-8, with a `Status Code`.
- Each call is a new session starting in the home folder: variables and `cd` do not carry
  over, so use absolute paths.
- Nobody can answer a prompt: `Read-Host` or a confirmation fails with "interactive input is
  not available". Pass the value, or add `-Confirm:$false` / `-Force` / `-Recurse`.
- Errors and warnings come back as plain text. When the command still succeeds (non-terminating
  errors, status 0) they follow the output under an `Errors and messages:` heading, with any
  warning, verbose and debug lines: check for it.
- A non-zero exit code is a tool error carrying the output and `Status Code`. For commands
  whose non-zero codes mean success pass `success_exit_codes`: `[0, 1]` for findstr
  (1 = no match), `[0,1,2,3,4,5,6,7]` for robocopy.
- On timeout it is a tool error "Command execution timed out after N s" with
  `Status Code: -1`, and the command really is stopped. Raise `timeout` for long jobs; it must
  be at least 1.
- Web requests work (Invoke-WebRequest uses the Windows certificate store): the fallback when
  Scrape fails.
- Notification AppIDs: `Get-StartApps`.

## FileSystem (`mode`, absolute `path`)

- `read`: `offset` is a **1-based line number**, plus `limit`. A whole-file read over 10 MB is
  refused; read part of a bigger file with `offset` + `limit`.
- `write`: creates parent folders; `append=true` appends. An existing file is refused unless
  `overwrite=true`. Newlines are written as CRLF.
- `copy` / `move`: an existing destination is refused unless `overwrite=true`. `move` also
  renames and creates target folders.
- `delete`: a non-empty folder is refused unless `recursive=true`.
- `list`: `pattern` filter. `search`: glob; without `recursive=true` it only looks in the top
  folder ("No matches" even when subfolders have hits).
- `info`: size, dates, counts. A folder's "Size" is the total of every file inside,
  subfolders included, counted up to 10,000 files; a "Size note" line says when it stopped
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
- `list` shows ExpandString values already expanded (`%TEMP%` → full path); the stored raw
  value is intact.
- `delete` WITH `name` removes one value; WITHOUT `name` it deletes the key and its values. A
  key with sub-keys is refused unless `recursive=true`.
- A missing key is a plain-text error.

## Process

- `list`: `name` is a plain substring filter ("pwsh" → only pwsh.exe); `sort_by` memory | cpu
  | name; `limit` 1 or more. The CPU% column (a share of the whole machine) appears only with
  `sort_by="cpu"`, which takes ~1.7 s; memory and name sorts take ~0.6 s.
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
