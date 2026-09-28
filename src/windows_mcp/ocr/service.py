"""Find text on screen with Windows' built-in OCR (round-2 C.6).

For games, remote desktops and canvas UIs, which expose no accessibility tree.
Windows.Media.Ocr is a WinRT API; with no WinRT package in the project, Windows
PowerShell 5.1 (pwsh 7 cannot load WinRT types) reads a temporary PNG. A full
1920x1080 screen takes about 1.6 s at the 3x enlargement, process start included
(measured 2026-09-24; a small region about 0.6 s).
"""

import json
import math
import os
import tempfile
from collections.abc import Callable

from PIL import Image

import windows_mcp.uia as uia
from windows_mcp.desktop import screenshot as screenshot_capture
from windows_mcp.powershell.service import PowerShellExecutor
from windows_mcp.powershell.utils import ps_quote
from windows_mcp.tree.utils import top_level_window_at

_ENLARGE = 3
_MAX_IMAGE_SIDE = 10_000  # OcrEngine.MaxImageDimension on Windows 11

# Prints JSON {"angle": TextAngle, "lines": [{"words": [{"t", "x", "y", "w", "h"}, ...]}, ...]},
# word boxes in pixels of the image as turned by TextAngle (see _turn_back).
_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
function Await($op, [type]$type) {
    $task = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait() | Out-Null
    $task.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { throw 'No text recognition language is installed (Settings > Language).' }
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
try {
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
} finally { $stream.Dispose() }
$lines = @(foreach ($line in $result.Lines) {
    @{ words = @($line.Words | ForEach-Object { $r = $_.BoundingRect
        @{ t = $_.Text; x = [int]$r.X; y = [int]$r.Y; w = [int]$r.Width; h = [int]$r.Height } }) }
})
ConvertTo-Json -Compress -Depth 6 -InputObject @{ angle = $result.TextAngle; lines = $lines }
"""


def read_lines(image: Image.Image) -> list[dict]:
    """The text lines Windows OCR sees in *image*; RuntimeError when it cannot run."""
    handle, path = tempfile.mkstemp(suffix=".png")
    os.close(handle)
    try:
        image.save(path)
        output, code = PowerShellExecutor.execute_command(
            f"$Path = {ps_quote(path)}\n{_SCRIPT}", timeout=30, shell="powershell"
        )
    finally:
        os.unlink(path)
    if code != 0:
        raise RuntimeError(f"Windows text recognition failed: {output.strip()[:300]}")
    data = json.loads(output) if output.strip() else {}
    lines = data.get("lines") or []
    lines = lines if isinstance(lines, list) else [lines]
    if data.get("angle"):
        _turn_back(lines, data["angle"], *image.size)
    return lines


def _turn_back(lines: list[dict], angle: float, width: int, height: int) -> None:
    """Move word boxes from OCR's tilted frame back to the image, in place.

    The engine guesses a text angle (1.5 degrees for level text drawn in columns,
    measured 2026-09-24) and returns boxes in the image turned by it, so one row's words
    drifted 18 px apart vertically and click points were off (round-3 R3-I6). Each box
    centre is turned by *angle* about the image centre; the box size is kept.
    """
    turn = math.radians(angle)
    cos, sin = math.cos(turn), math.sin(turn)
    ox, oy = width / 2, height / 2
    for line in lines:
        for word in line.get("words") or []:
            dx, dy = word["x"] + word["w"] / 2 - ox, word["y"] + word["h"] / 2 - oy
            word["x"] = round(dx * cos - dy * sin + ox - word["w"] / 2)
            word["y"] = round(dx * sin + dy * cos + oy - word["h"] / 2)


def _rows(lines: list[dict], owner: Callable[[dict], object] = lambda line: None) -> list[dict]:
    """Join OCR lines that sit on one row and have the same *owner*, words left to right.

    The engine splits a row at wide gaps, so each table column came back as its own
    line and "North 460 units" was never found (round-3 R3-I6). Lines count as one row
    when their vertical centres are less than half the smaller line height apart. The
    owner (the window under the line) keeps side-by-side windows apart (round-4 R4-9):
    a gap limit could not, since table columns are gaps wider than any between windows.
    """

    def centre(line: dict) -> float:
        return sum(w["y"] + w["h"] / 2 for w in line["words"]) / len(line["words"])

    rows: list[tuple[float, float, list[dict]]] = []
    last_row: dict[object, tuple[float, float, list[dict]]] = {}  # per owner
    for line in sorted((line for line in lines if line.get("words")), key=centre):
        cy, height, key = centre(line), max(w["h"] for w in line["words"]), owner(line)
        row = last_row.get(key)
        if row and abs(cy - row[0]) < min(height, row[1]) / 2:
            row[2].extend(line["words"])
        else:
            row = last_row[key] = (cy, height, list(line["words"]))
            rows.append(row)
    return [{"words": sorted(words, key=lambda w: w["x"])} for _, _, words in rows]


def find_phrase(
    lines: list[dict],
    phrase: str,
    left: int,
    top: int,
    scale: float = 1.0,
    window_at: Callable[[int, int], object] | None = None,
) -> list[tuple[str, int, int]]:
    """(row text, centre x, centre y) of each place *phrase* appears, case ignored.

    The phrase must appear in order within one row (see `_rows`), and may start or end
    inside a word. Word boxes are divided by *scale* (the enlargement) and offset by
    (left, top) into screen pixels. *window_at* (screen x, y -> window) keeps the text
    of different windows in separate rows.
    """

    def owner(line: dict) -> object:
        if window_at is None:
            return None
        word = line["words"][0]
        return window_at(
            left + int((word["x"] + word["w"] / 2) / scale),
            top + int((word["y"] + word["h"] / 2) / scale),
        )

    wanted = " ".join(phrase.split()).lower()
    matches = []
    for line in _rows(lines, owner):
        text, spans = "", []
        for word in line.get("words") or []:
            text += " " if text else ""
            spans.append((len(text), len(text) + len(word["t"]), word))
            text += word["t"]
        folded = text.lower()
        start = folded.find(wanted)
        while wanted and start != -1:
            end = start + len(wanted)
            hit = [w for s, e, w in spans if s < end and e > start]
            x0, y0 = min(w["x"] for w in hit), min(w["y"] for w in hit)
            x1 = max(w["x"] + w["w"] for w in hit)
            y1 = max(w["y"] + w["h"] for w in hit)
            cx, cy = (x0 + x1) / 2 / scale, (y0 + y1) / 2 / scale
            matches.append((text, left + int(cx), top + int(cy)))
            start = folded.find(wanted, end)
    return matches


def find_on_screen(
    phrase: str, rect: uia.Rect, window: int | None = None
) -> list[tuple[str, int, int]]:
    """Capture *rect* (screen pixels) and find *phrase* in it; positions in screen pixels.

    With *window* (a handle), only matches whose centre shows that window are kept, so
    text of a window lying over it is dropped (round-4 R4-N2).
    """
    # The screenshot module directly: Desktop.get_screenshot flashes a border on every call.
    image, _ = screenshot_capture.capture(rect)
    # Measured 2026-09-23: at 1x the OCR split "Zebra Quartz" into "Zebra Q uartz" and
    # missed a small "Save" button; 2x still missed both, 3x read everything. The engine
    # refuses images over 10,000 px. Cost: a full 1920x1080 screen 1.0 s -> 2.6 s.
    # Lanczos, not the default bicubic: bicubic lost "460" from "North 460 12.50" in 6 of
    # 60 crops of one window a few pixels apart, Lanczos in none, at the same speed (R5-4).
    scale = min(_ENLARGE, _MAX_IMAGE_SIDE / max(image.size))
    if scale != 1:
        size = (int(image.width * scale), int(image.height * scale))
        image = image.resize(size, Image.Resampling.LANCZOS)
    matches = find_phrase(
        read_lines(image), phrase, rect.left, rect.top, scale, top_level_window_at
    )
    if window is not None:
        matches = [m for m in matches if top_level_window_at(m[1], m[2]) == window]
    return matches
