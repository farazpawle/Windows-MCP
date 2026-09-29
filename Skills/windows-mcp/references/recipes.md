# Recipes: one PowerShell call instead of clicking through an app

Each snippet is a `command` for the PowerShell tool (PowerShell 7) and replaces a click-through
the test rounds did by hand. No focus, no typing, no Screenshot to check. Replace the paths;
use absolute paths (each call starts in the home folder). All were run and checked on
2026-09-29.

## Files

**Replace text in a file** (instead of Notepad's Find & Replace, then Save). Keeps the file's
own line breaks. `\b` stops "410" matching inside "4105".

```powershell
$f = 'C:\path\report.txt'
(Get-Content -Raw $f) -replace '\b410\b', '405' | Set-Content -NoNewline $f
```

The file is written back as UTF-8 without BOM. For literal text with regex characters
(`. ( ) [ ] $`), use `.Replace('old', 'new')` instead of `-replace`.

**Read some lines of a document** (instead of opening it and scrolling, or Ctrl+A, Ctrl+C).
Lines 2-3:

```powershell
Get-Content 'C:\path\report.txt' -TotalCount 3 | Select-Object -Skip 1
```

The last lines: `Get-Content 'C:\path\app.log' -Tail 20`. A whole file: FileSystem `read`.

**Find which files contain a word** (instead of opening each one, or FindText):

```powershell
Select-String -Path 'C:\path\*' -Pattern 'North' -SimpleMatch |
  ForEach-Object { "$($_.Filename):$($_.LineNumber): $($_.Line)" }
```

Subfolders too: `Get-ChildItem 'C:\path' -Recurse -File | Select-String -Pattern 'North' -SimpleMatch`.

**Copy chosen files to a folder** (instead of MultiSelect in Explorer, Ctrl+C, Ctrl+V):

```powershell
Copy-Item 'C:\path\report.txt', 'C:\path\sales.csv' -Destination 'C:\path\out'
```

**Count lines, words, characters** (instead of reading Notepad's status bar). Characters
leave out the line breaks.

```powershell
Get-Content 'C:\path\report.txt' | Measure-Object -Line -Word -Character
```

**Newest file in a folder** (to check a Save really wrote, instead of opening Explorer):

```powershell
Get-ChildItem 'C:\path' -File | Sort-Object LastWriteTime -Descending |
  Select-Object -First 1 Name, Length, LastWriteTime
```

**Wait for a file to appear and stop growing** (a save or download finishing; WaitFor has no
file condition). A tool error after 15 s if it never does.

```powershell
$f = 'C:\path\saved.txt'
$deadline = (Get-Date).AddSeconds(15); $last = -1; $ready = $false
while (-not $ready -and (Get-Date) -lt $deadline) {
  $size = if (Test-Path -LiteralPath $f) { (Get-Item -LiteralPath $f).Length } else { -1 }
  $ready = $size -ge 0 -and $size -eq $last; $last = $size
  if (-not $ready) { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) { throw "Not ready after 15 s: $f" }
```

Test with `Test-Path`, not `.Length` alone: a missing file's `.Length` reads as 0 in PowerShell.

## Data

**Add up a column of a CSV** (instead of reading numbers off the screen):

```powershell
Import-Csv 'C:\path\sales.csv' | Measure-Object Revenue -Sum -Average
```

## File Explorer windows

These drive an Explorer window that is already open, through `Shell.Application`: no focus
change, nothing typed.

**Point an open Explorer window at a folder** (instead of clicking the address bar, typing the
path and Enter). Pick the window by its current folder (or `$_.HWND -eq <handle>` from App `list`):

```powershell
$w = @((New-Object -ComObject Shell.Application).Windows() |
  Where-Object { $_.Document.Folder.Self.Path -eq 'C:\path\in' })[0]
$w.Navigate('C:\path\out')
```

**Which files are selected in Explorer** (instead of a Screenshot or Snapshot):

```powershell
(New-Object -ComObject Shell.Application).Windows() |
  Where-Object { $_.Document.SelectedItems } |
  ForEach-Object { $_.Document.SelectedItems() | ForEach-Object { $_.Path } }
```

It lists the selection of every open Explorer window.
