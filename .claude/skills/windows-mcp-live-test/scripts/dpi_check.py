"""Round-2 5.1: coordinate checks at the current display scaling (run at 100%, 125%, 150%).

Per harness button: Snapshot centre inside the button's real rectangle, Click by label logged
by the harness, Move lands the pointer on the centre, Screenshot region image has the region's
size. Sends real clicks: the user keeps hands off (~30 s). Prints RESULT: PASS / FAIL.
"""

import asyncio
import base64
import ctypes
import io
import re
import sys
import tempfile
from pathlib import Path

import windows_mcp.uia  # noqa: F401  sets per-monitor DPI awareness, as the real server does
import win32api
import win32gui
from livetest import close_window, guarded_call, mcp_client, read_settled, start_window
from PIL import Image

LOG = Path(tempfile.gettempdir()) / "wmcp_dpi_check.log"
BUTTONS = ("Alpha", "Bravo", "Charlie")
LINE = re.compile(r'\[label:(\d+)\]\s*\((-?\d+),\s*(-?\d+)\)\s*button\s*"([^"]+)"')


def button_rect(hwnd: int, text: str) -> tuple[int, int, int, int]:
    found = []
    win32gui.EnumChildWindows(
        hwnd, lambda h, _: found.append(h) if win32gui.GetWindowText(h) == text else None, None
    )
    return win32gui.GetWindowRect(found[0])


def scale_info(hwnd: int) -> str:
    monitor = win32api.MonitorFromWindow(hwnd)
    dx, dy = ctypes.c_uint(), ctypes.c_uint()
    ctypes.windll.shcore.GetDpiForMonitor(int(monitor), 0, ctypes.byref(dx), ctypes.byref(dy))
    return (
        f"monitor DPI {dx.value} ({dx.value * 100 // 96}%), system DPI "
        f"{ctypes.windll.user32.GetDpiForSystem()}, harness window DPI "
        f"{ctypes.windll.user32.GetDpiForWindow(hwnd)}"
    )


async def main(hwnd: int) -> list[str]:
    fails = []
    print(scale_info(hwnd))
    async with mcp_client() as c:
        r = await c.call_tool("DisplayInventory", {}, raise_on_error=False)
        print("DisplayInventory:", " | ".join(b.text for b in r.content if b.type == "text")[:600])

        region = list(win32gui.GetWindowRect(hwnd))
        r = await c.call_tool("Snapshot", {"region": region, "use_vision": False})
        text = "\n".join(b.text for b in r.content if b.type == "text").replace('\\"', '"')
        found = {m[3]: (int(m[0]), int(m[1]), int(m[2])) for m in LINE.findall(text)}
        coord_line = next((ln for ln in text.splitlines() if ln.startswith("Coordinates")), "")
        print("Snapshot buttons:", found, coord_line)
        if not found:
            print("Snapshot raw:", r.is_error, text[:2500])

        for name in BUTTONS:
            left, top, right, bottom = button_rect(hwnd, name)
            print(f"{name}: real rect {(left, top, right, bottom)}")
            if name not in found:
                fails.append(f"{name}: not in Snapshot")
                continue
            label, x, y = found[name]
            if not (left <= x < right and top <= y < bottom):
                fails.append(
                    f"{name}: Snapshot centre ({x},{y}) outside {left, top, right, bottom}"
                )

            await guarded_call(c, hwnd, "Move", {"loc": [x, y]}, points=[(x, y)])
            cx, cy = win32gui.GetCursorPos()
            if abs(cx - x) > 1 or abs(cy - y) > 1:
                fails.append(f"{name}: Move to ({x},{y}) put the pointer at ({cx},{cy})")

            await guarded_call(c, hwnd, "Click", {"label": label}, points=[(x, y)])

            r = await c.call_tool(
                "Screenshot", {"region": [left, top, right, bottom]}, raise_on_error=False
            )
            images = [b for b in r.content if b.type == "image"]
            if r.is_error or not images:
                fails.append(f"{name}: Screenshot region failed")
            else:
                size = Image.open(io.BytesIO(base64.b64decode(images[0].data))).size
                if size != (right - left, bottom - top):
                    fails.append(f"{name}: region image {size} != {(right - left, bottom - top)}")

    log = read_settled(LOG) or ""
    for name in BUTTONS:
        if f"click {name}" not in log:
            fails.append(f"{name}: harness did not log the click")
    print("harness log:", log.strip().replace("\n", " | "))
    return fails


proc, hwnd = start_window("LiveTest51", LOG, rect=(300, 300, 480, 260), buttons=BUTTONS)
try:
    failures = asyncio.run(main(hwnd))
finally:
    close_window(proc, hwnd)
print("RESULT:", "PASS" if not failures else "FAIL")
for f in failures:
    print("  -", f)
sys.exit(1 if failures else 0)
