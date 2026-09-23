"""Find text on screen with Windows' built-in OCR (round-2 C.6).

For games, remote desktops and canvas UIs, which expose no accessibility tree.
Windows.Media.Ocr is a WinRT API; with no WinRT package in the project, Windows
PowerShell 5.1 (pwsh 7 cannot load WinRT types) reads a temporary PNG. A full
1920x1080 screen takes about 2.6 s at the 3x enlargement, process start included.
"""

import json
import os
import tempfile

from PIL import Image

import windows_mcp.uia as uia
from windows_mcp.desktop import screenshot as screenshot_capture
from windows_mcp.powershell.service import PowerShellExecutor
from windows_mcp.powershell.utils import ps_quote

_ENLARGE = 3
_MAX_IMAGE_SIDE = 10_000  # OcrEngine.MaxImageDimension on Windows 11

# Prints the recognised lines as JSON: [{"words": [{"t", "x", "y", "w", "h"}, ...]}, ...],
# word boxes in pixels of the image.
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
ConvertTo-Json -Compress -Depth 5 -InputObject $lines
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
    data = json.loads(output) if output.strip() else []
    return data if isinstance(data, list) else [data]


def find_phrase(
    lines: list[dict], phrase: str, left: int, top: int, scale: float = 1.0
) -> list[tuple[str, int, int]]:
    """(line text, centre x, centre y) of each place *phrase* appears, case ignored.

    The phrase must appear in order within one line, and may start or end inside a
    word. Word boxes are divided by *scale* (the enlargement) and offset by
    (left, top) into screen pixels.
    """
    wanted = " ".join(phrase.split()).lower()
    matches = []
    for line in lines:
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


def find_on_screen(phrase: str, rect: uia.Rect) -> list[tuple[str, int, int]]:
    """Capture *rect* (screen pixels) and find *phrase* in it; positions in screen pixels."""
    # The screenshot module directly: Desktop.get_screenshot flashes a border on every call.
    image, _ = screenshot_capture.capture(rect)
    # Measured 2026-09-23: at 1x the OCR split "Zebra Quartz" into "Zebra Q uartz" and
    # missed a small "Save" button; 2x still missed both, 3x read everything. The engine
    # refuses images over 10,000 px. Cost: a full 1920x1080 screen 1.0 s -> 2.6 s.
    scale = min(_ENLARGE, _MAX_IMAGE_SIDE / max(image.size))
    if scale != 1:
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    return find_phrase(read_lines(image), phrase, rect.left, rect.top, scale)
