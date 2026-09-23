"""Helpers for live windows-mcp tests: a guarded test window plus an in-process server.

Import from a script in the session scratchpad and run it from the repo root:

    timeout 180 env -u SSLKEYLOGFILE PYTHONPATH="<this folder>" uv run --no-sync python <script>

The server is built from the code on disk (`_build_mcp`), so it tests uncommitted changes
without restarting the MCP server Claude Code is connected to.
"""

import os
import subprocess
import time
from pathlib import Path

os.environ.setdefault("WINDOWS_MCP_DISABLE_FLASH", "1")  # the glow border would cover the window
os.environ["ANONYMIZED_TELEMETRY"] = "false"

import win32con  # noqa: E402
import win32gui  # noqa: E402
from fastmcp import Client  # noqa: E402

HARNESS_PS1 = Path(__file__).resolve().parent / "test_harness.ps1"
GA_ROOT = 2


def start_window(
    title: str,
    log: Path,
    *,
    rect: tuple[int, int, int, int] = (300, 300, 420, 280),
    textbox: bool = False,
    scrollbars: bool = False,
    seconds: int = 90,
) -> tuple[subprocess.Popen, int]:
    """Open the logging test window and wait until it is visible.

    Returns (process, hwnd). Pipes are DEVNULL: an inherited stdout pipe keeps the calling
    shell waiting until the window closes, even after this script has crashed.
    """
    for path in (log, Path(f"{log}.text")):
        path.unlink(missing_ok=True)
    x, y, w, h = rect
    cmd = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HARNESS_PS1),
        "-Title", title, "-Log", str(log), "-X", str(x), "-Y", str(y),
        "-Width", str(w), "-Height", str(h), "-Seconds", str(seconds),
    ]  # fmt: skip
    if textbox:
        cmd.append("-TextBox")
    if scrollbars:
        cmd.append("-ScrollBars")
    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and proc.poll() is None:
        hwnd = win32gui.FindWindow(None, title)
        if hwnd and win32gui.IsWindowVisible(hwnd):
            time.sleep(1.0)  # let it finish painting and take its TopMost place
            return proc, hwnd
        time.sleep(0.2)
    proc.kill()
    raise RuntimeError(f"test window {title!r} did not appear")


def close_window(proc: subprocess.Popen, hwnd: int) -> None:
    """Close the test window, killing its process (by our own handle, never by name) if needed."""
    if win32gui.IsWindow(hwnd):
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    try:
        proc.wait(5)
    except subprocess.TimeoutExpired:
        proc.kill()


def center(hwnd: int, dy: int = 0) -> tuple[int, int]:
    """Screen point in the middle of the window's client area (dy shifts it down)."""
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    x, y = win32gui.ClientToScreen(hwnd, ((left + right) // 2, (top + bottom) // 2 + dy))
    return x, y


def on_window(hwnd: int, x: int, y: int) -> bool:
    """True when the top-level window under (x, y) is `hwnd` - i.e. input there reaches it."""
    return win32gui.GetAncestor(win32gui.WindowFromPoint((x, y)), GA_ROOT) == hwnd


def mcp_client() -> Client:
    """FastMCP client wired to an in-process server built from the working tree."""
    from windows_mcp.__main__ import _build_mcp

    return Client(_build_mcp())


async def guarded_call(
    client: Client,
    hwnd: int,
    tool: str,
    args: dict,
    *,
    points: list[tuple[int, int]] = (),
    keyboard: bool = False,
):
    """Call a tool only if its input cannot land outside the test window.

    Every point in `points` must be on the window, and for keyboard input the window must
    be in front (click it first). Otherwise abort - once, input meant for a hidden test
    window was typed into the user's editor.
    """
    for x, y in points:
        if not on_window(hwnd, x, y):
            raise SystemExit(f"ABORT before {tool}: ({x}, {y}) is not on the test window")
    if keyboard and win32gui.GetForegroundWindow() != hwnd:
        raise SystemExit(f"ABORT before {tool}: the test window is not in front")
    result = await client.call_tool(tool, args, raise_on_error=False)
    text = "\n".join(block.text for block in result.content if block.type == "text")
    print(f"{tool} {args} -> is_error={result.is_error}: {text[:500]}")
    return result


def read_settled(path: Path, *, quiet: float = 0.6, timeout: float = 15.0) -> str | None:
    """Read a file the test window keeps rewriting, once it has stopped changing.

    The window writes on every keystroke and lags far behind fast input, so an early read
    under-counts (1,055 of 2,000 typed characters once). Retries while the file is locked.
    """
    deadline = time.monotonic() + timeout
    last, stable_since = None, time.monotonic()
    while time.monotonic() < deadline:
        try:
            current = path.read_text(encoding="utf-8") if path.exists() else None
        except PermissionError:
            time.sleep(0.05)
            continue
        if current != last:
            last, stable_since = current, time.monotonic()
        elif time.monotonic() - stable_since >= quiet:
            return current
        time.sleep(0.1)
    return last
