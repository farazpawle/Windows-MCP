from windows_mcp.desktop.utils import (
    is_window_hung,
    resolve_known_folder_guid_path,
)
from windows_mcp.powershell.utils import ps_quote
from windows_mcp.powershell import PowerShellExecutor
from windows_mcp.tree.utils import (
    covering_window,
    spot_on_element,
    is_fully_covered,
    is_unreadable_window,
    top_level_window_at,
)
from windows_mcp.vdm.core import (
    get_all_desktops,
    get_current_desktop,
    is_window_on_current_desktop,
)
from windows_mcp.desktop.views import DesktopState, Window, Browser, Status, Size, Display
from windows_mcp.tree.views import (
    BoundingBox,
    ScrollElementNode,
    TreeElementNode,
    TreeState,
    SemanticNode,
)
from PIL import ImageFont, ImageDraw, Image
from windows_mcp.tree.service import Tree
from windows_mcp.desktop import screenshot as screenshot_capture
from windows_mcp.desktop import flash_overlay
from windows_mcp.desktop import window_control
from windows_mcp.infrastructure import validate_url
from importlib import metadata
from urllib.parse import urljoin
from contextlib import contextmanager
from locale import getpreferredencoding
from typing import Literal
from markdownify import MarkdownConverter
from bs4 import BeautifulSoup
from fuzzywuzzy import process
from time import sleep, time, perf_counter
from psutil import Process
import math
import win32api
import win32process
import win32gui
import win32con
import requests
import ssl
import truststore
import logging
import random
import ctypes
import csv
import re
import os
import io

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

import windows_mcp.uia as uia  # noqa: E402

# Invisible characters some apps put in window titles (Edge: "Microsoft\u200b Edge").
_ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")

# Key name aliases for shortcut keys that differ from UIA SpecialKeyNames
_KEY_ALIASES = {
    "backspace": "Back",
    "capslock": "Capital",
    "scrolllock": "Scroll",
    "windows": "Win",
    "command": "Win",
    "cmd": "Win",
    "super": "Win",
    "meta": "Win",
    "option": "Alt",
    "menu": "Apps",
    # Punctuation by name, so a shortcut never has to spell a separator or brace.
    "plus": "+",
    "minus": "-",
    "equal": "=",
    "equals": "=",
    "comma": ",",
    "period": ".",
    "slash": "/",
    "backslash": "\\",
    "semicolon": ";",
    "quote": "'",
    "grave": "`",
    "bracketleft": "[",
    "bracketright": "]",
    "braceleft": "{",
    "braceright": "}",
}


def _shortcut_keys(shortcut: str) -> list[str]:
    """Split "ctrl+shift+a" into key names; a trailing "+" ("ctrl++", "+") is the plus key."""
    keys = [key.strip() for key in shortcut.split("+") if key.strip()]
    if shortcut.strip().endswith("+"):
        keys.append("+")
    if not keys:
        raise ValueError("shortcut is empty")
    # Resolve every key here so an unknown one is reported the same way on both
    # paths: SendKeys raises its own wording, and only once it is already typing.
    for key in keys:
        _virtual_key(key)
    return keys


def _key_name(key: str) -> str:
    """Our name for one key, also accepting the xdotool names computer-use models send.

    xdotool spells "Page_Down", "KP_Enter" (numpad), "Super_L" (left/right side).
    """
    lower = key.lower()
    if lower in _KEY_ALIASES:
        return _KEY_ALIASES[lower]
    if len(key) == 1 or key.upper() in uia.SpecialKeyNames:
        return key
    if lower.startswith("kp_"):
        lower = lower[3:]
        if lower.isdigit():
            return "Numpad" + lower
    side = ""
    if lower.endswith(("_l", "_r")):
        side, lower = lower[-1], lower[:-2]
    lower = lower.replace("_", "")
    return side + _KEY_ALIASES.get(lower, lower)


def _virtual_key(key: str) -> int:
    """Virtual-key code for one shortcut key name ("shift", "down", "a", "/")."""
    name = _key_name(key)
    if len(name) == 1:
        code = ctypes.windll.user32.VkKeyScanW(ord(name))
        if code != -1:
            return code & 0xFF
    elif name.upper() in uia.SpecialKeyNames:
        return uia.SpecialKeyNames[name.upper()]
    raise ValueError(f"Unknown key {key!r}")


# Keys whose bare release opens something: Alt the menu bar, Win the Start menu.
_MASKED_KEYS = frozenset(
    [uia.Keys.VK_MENU, uia.Keys.VK_LMENU, uia.Keys.VK_RMENU, uia.Keys.VK_LWIN, uia.Keys.VK_RWIN]
)
_MENU_MASK_KEY = 0xE8  # unassigned virtual key


@contextmanager
def _keys_held(keys: list[str]):
    """Hold *keys* down for the duration of the block; always release them, last first."""
    codes = [_virtual_key(k) for k in keys]  # resolve all before pressing any
    pressed = []
    try:
        for code in codes:
            uia.PressKey(code, waitTime=0.05)
            pressed.append(code)
        yield
    finally:
        for code in reversed(pressed):
            _release_key(code)


def _release_key(code: int) -> None:
    if code in _MASKED_KEYS:
        # An unassigned key between key-down and key-up cancels what a bare
        # Alt/Win release would open (AutoHotkey's "menu mask").
        uia.PressKey(_MENU_MASK_KEY, waitTime=0)
        uia.ReleaseKey(_MENU_MASK_KEY, waitTime=0)
    uia.ReleaseKey(code, waitTime=0.05)


# What Shortcut release_all checks, keys before buttons: a drop made while Ctrl is
# still down would copy instead of move.
_RELEASABLE_KEYS = (
    ("left Shift", uia.Keys.VK_LSHIFT),
    ("right Shift", uia.Keys.VK_RSHIFT),
    ("left Ctrl", uia.Keys.VK_LCONTROL),
    ("right Ctrl", uia.Keys.VK_RCONTROL),
    ("left Alt", uia.Keys.VK_LMENU),
    ("right Alt", uia.Keys.VK_RMENU),
    ("left Win", uia.Keys.VK_LWIN),
    ("right Win", uia.Keys.VK_RWIN),
)
# ponytail: GetAsyncKeyState reads physical buttons, so with swapped buttons a stuck
# logical left shows as right; add a GetSystemMetrics(SM_SWAPBUTTON) check if that bites.
_RELEASABLE_BUTTONS = (
    ("left mouse button", uia.Keys.VK_LBUTTON, "ReleaseMouse"),
    ("right mouse button", uia.Keys.VK_RBUTTON, "RightReleaseMouse"),
    ("middle mouse button", uia.Keys.VK_MBUTTON, "MiddleReleaseMouse"),
)


class _WindowsTrustAdapter(requests.adapters.HTTPAdapter):
    # Verify HTTPS against the Windows certificate store, as browsers do. Python
    # 3.13+'s strict X.509 checks reject antivirus TLS-inspection roots (Avast),
    # which failed every HTTPS scrape. Scoped to Scrape: truststore is client-only.
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        return super().init_poolmanager(*args, **kwargs)


_http_session = requests.Session()
_http_session.mount("https://", _WindowsTrustAdapter())


def _package_version() -> str:
    try:
        return metadata.version("windows-mcp")
    except metadata.PackageNotFoundError:
        return "dev"


# Wikimedia and others answer 403 to the default "python-requests/x.y" identity;
# their policy asks for a tool name, version and a contact URL.
_http_session.headers["User-Agent"] = (
    f"windows-mcp/{_package_version()} (+https://github.com/CursorTouch/Windows-MCP)"
)


def _snapshot_profile_enabled() -> bool:
    value = os.getenv("WINDOWS_MCP_PROFILE_SNAPSHOT", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def draw_grid(image: Image.Image, grid_lines: tuple[int, int]) -> None:
    """Draw a reference grid in place: *grid_lines* = (columns, rows); 1 means no lines."""
    draw = ImageDraw.Draw(image)
    width, height = image.size
    columns, rows = grid_lines
    for i in range(1, columns):
        x = width * i // columns
        draw.line([(x, 0), (x, height)], fill=(200, 200, 200, 128), width=1)
    for i in range(1, rows):
        y = height * i // rows
        draw.line([(0, y), (width, y)], fill=(200, 200, 200, 128), width=1)


def place_badge(
    box: tuple[int, int, int, int],
    size: tuple[int, int],
    placed: list[tuple[int, int, int, int]],
    image_size: tuple[int, int],
) -> tuple[int, int]:
    """Top-left corner for an element's number badge, inside its box's top-left corner.

    Badges outside the box (the old spot, above it) landed in the gap between
    stacked fields and read as the neighbour's number. A badge that would cover
    an already *placed* badge moves right past it, then down a row when the box
    runs out of width. The result is always wholly inside the image.
    """
    left, top, right, _ = box
    width, height = size
    image_width, image_height = image_size
    x, y = left + 2, top + 2  # just inside the 2 px outline
    # ponytail: greedy scan, O(n^2) over badges; fine for a few hundred elements.
    for _ in range(2 * len(placed) + 1):
        x = max(0, min(x, image_width - width))
        y = max(0, min(y, image_height - height))
        hit = next(
            (p for p in placed if x < p[2] and p[0] < x + width and y < p[3] and p[1] < y + height),
            None,
        )
        if hit is None:
            break
        x = hit[2] + 1
        if x + width > max(right, left + 2 + width):
            x, y = left + 2, hit[3] + 1
    return max(0, min(x, image_width - width)), max(0, min(y, image_height - height))


def _escape_text_for_sendkeys(text: str) -> str:
    """Escape special characters so uia.SendKeys types them correctly."""
    result = []
    for ch in text:
        if ch == "{":
            result.append("{{}")
        elif ch == "}":
            result.append("{}}")
        elif ch == "\n":
            result.append("{Enter}")
        elif ch == "\t":
            result.append("{Tab}")
        elif ch == "\r":
            continue
        else:
            result.append(ch)
    return "".join(result)


class Desktop:
    # Caller coordinates = screen pixels x this; set by the last full screenshot
    # (tools/_coords.py, round-2 B.1). Only messages here use it; input is already converted.
    coordinate_scale: float = 1.0

    def __init__(self):
        self.encoding = getpreferredencoding()
        self.tree = Tree(self)
        self.desktop_state = None
        # The tree whose [label:N] ids the last Snapshot printed. Only Snapshot sets it:
        # every other capture (WaitFor, App, Scrape, Screenshot) replaces desktop_state,
        # which silently renumbered labels.
        self.label_tree_state: TreeState | None = None

    def get_state(
        self,
        use_annotation: bool | str = True,
        use_vision: bool | str = False,
        use_dom: bool | str = False,
        use_ui_tree: bool | str = True,
        as_bytes: bool | str = False,
        scale: float = 1.0,
        grid_lines: tuple[int, int] | None = None,
        display_indices: list[int] | None = None,
        region: list[int] | tuple[int, ...] | None = None,
        max_image_size: Size | None = None,
    ) -> DesktopState:
        use_annotation = use_annotation is True or (
            isinstance(use_annotation, str) and use_annotation.lower() == "true"
        )
        use_vision = use_vision is True or (
            isinstance(use_vision, str) and use_vision.lower() == "true"
        )
        use_dom = use_dom is True or (isinstance(use_dom, str) and use_dom.lower() == "true")
        use_ui_tree = use_ui_tree is True or (
            isinstance(use_ui_tree, str) and use_ui_tree.lower() == "true"
        )
        as_bytes = as_bytes is True or (isinstance(as_bytes, str) and as_bytes.lower() == "true")

        if use_dom and not use_ui_tree:
            raise ValueError("use_dom=True requires use_ui_tree=True")

        start_time = time()
        profile_enabled = _snapshot_profile_enabled()
        profile_started_at = perf_counter()
        stage_started_at = profile_started_at
        desktop_context_ms = 0.0
        tree_capture_ms = 0.0
        region_filter_ms = 0.0
        screenshot_capture_ms = 0.0
        screenshot_resize_ms = 0.0
        state_build_ms = 0.0
        displays = self.get_displays()
        available_displays = [self._display_to_view(display) for display in displays]
        region_rect = self.parse_region_selection(region)
        capture_rect = (
            region_rect
            if region_rect is not None
            else (
                self.get_display_union_rect(display_indices, displays) if display_indices else None
            )
        )
        screenshot_region = self._rect_to_bounding_box(capture_rect) if capture_rect else None

        # Fast path for Screenshot tool (use_ui_tree=False): skip window enumeration.
        # UIAutomation calls (get_controls_handles / get_windows / get_active_window)
        # can hang when an app is launching and not responding to WM messages.
        if use_ui_tree:
            controls_handles = self.get_controls_handles()  # Taskbar,Program Manager,Apps, Dialogs
            windows, windows_handles = self.get_windows(controls_handles=controls_handles)  # Apps
            active_window = self.get_active_window(windows=windows)  # Active Window
            active_window_handle = active_window.handle if active_window else None
        else:
            controls_handles = []
            windows = []
            windows_handles = set()
            active_window = None
            active_window_handle = None

        cursor_position = self.get_cursor_location()

        try:
            active_desktop = get_current_desktop()
            all_desktops = get_all_desktops()
        except RuntimeError:
            active_desktop = {
                "id": "00000000-0000-0000-0000-000000000000",
                "name": "Default Desktop",
            }
            all_desktops = [active_desktop]

        if active_window is not None and active_window in windows:
            windows.remove(active_window)

        if profile_enabled:
            desktop_context_ms = (perf_counter() - stage_started_at) * 1000
            stage_started_at = perf_counter()

        logger.debug(f"Active window: {active_window or 'No Active Window Found'}")
        logger.debug(f"Windows: {windows}")

        if use_ui_tree:
            other_windows_handles = set(controls_handles) - windows_handles
            if active_window_handle is not None:
                other_windows_handles.discard(active_window_handle)
            tree_active_window_handle, tree_other_handles = self._select_tree_handles(
                active_window, other_windows_handles, windows, screenshot_region
            )
            tree_state = self.tree.get_state(
                tree_active_window_handle, tree_other_handles, use_dom=use_dom
            )
        else:
            root_box = screenshot_region or self.get_screen_box()
            tree_state = TreeState(
                status=True,
                root_node=TreeElementNode(
                    name="Desktop",
                    control_type="PaneControl",
                    bounding_box=root_box,
                    center=root_box.get_center(),
                    window_name="Desktop",
                    metadata={},
                ),
            )

        if profile_enabled:
            tree_capture_ms = (perf_counter() - stage_started_at) * 1000
            stage_started_at = perf_counter()

        if screenshot_region:
            # The focused window stays named even outside the region: it is still where
            # keys go, and dropping it read as "No active window found".
            windows = self._filter_windows_to_region(windows, screenshot_region)
            if use_ui_tree:
                tree_state = self._filter_tree_state_to_region(tree_state, screenshot_region)
            if cursor_position and not self._point_in_region(cursor_position, screenshot_region):
                cursor_position = None

        if profile_enabled:
            region_filter_ms = (perf_counter() - stage_started_at) * 1000
            stage_started_at = perf_counter()

        screenshot_original_size = None
        applied_scale = None
        if use_vision:
            if use_annotation:
                nodes = tree_state.interactive_nodes
                screenshot = self.get_annotated_screenshot(
                    nodes=nodes,
                    cursor_pos=cursor_position,
                    grid_lines=grid_lines,
                    capture_rect=capture_rect,
                )
            else:
                screenshot = self.get_screenshot(capture_rect=capture_rect)
                if grid_lines:
                    draw_grid(screenshot, grid_lines)

            screenshot_original_size = Size(width=screenshot.width, height=screenshot.height)

            if profile_enabled:
                screenshot_capture_ms = (perf_counter() - stage_started_at) * 1000
                stage_started_at = perf_counter()

            if max_image_size:
                scale_width = (
                    max_image_size.width / screenshot.width
                    if screenshot.width > max_image_size.width
                    else 1.0
                )
                scale_height = (
                    max_image_size.height / screenshot.height
                    if screenshot.height > max_image_size.height
                    else 1.0
                )
                scale = min(scale, scale_width, scale_height)

            applied_scale = scale
            if scale != 1.0:
                screenshot = screenshot.resize(
                    (int(screenshot.width * scale), int(screenshot.height * scale)),
                    Image.LANCZOS,
                )

            if profile_enabled:
                screenshot_resize_ms = (perf_counter() - stage_started_at) * 1000
                stage_started_at = perf_counter()

            if as_bytes:
                buffered = io.BytesIO()
                screenshot.save(buffered, format="PNG", optimize=True, compress_level=6)
                screenshot = buffered.getvalue()
                buffered.close()
        else:
            screenshot = None

        self.desktop_state = DesktopState(
            active_window=active_window,
            windows=windows,
            active_desktop=active_desktop,
            all_desktops=all_desktops,
            screenshot=screenshot,
            cursor_position=cursor_position,
            screenshot_original_size=screenshot_original_size,
            screenshot_scale=applied_scale,
            screenshot_region=screenshot_region,
            screenshot_displays=display_indices,
            available_displays=available_displays,
            tree_state=tree_state,
            screenshot_backend=getattr(self, "_last_screenshot_backend", None)
            if use_vision
            else None,
            capture_sec=time() - start_time,
        )
        if profile_enabled:
            state_build_ms = (perf_counter() - stage_started_at) * 1000
            total_profile_ms = (perf_counter() - profile_started_at) * 1000
            logger.info(
                "Snapshot profile: desktop_context_ms=%.1f tree_capture_ms=%.1f region_filter_ms=%.1f screenshot_capture_ms=%.1f screenshot_resize_ms=%.1f state_build_ms=%.1f total_ms=%.1f use_vision=%s use_dom=%s use_ui_tree=%s use_annotation=%s displays=%s",
                desktop_context_ms,
                tree_capture_ms,
                region_filter_ms,
                screenshot_capture_ms,
                screenshot_resize_ms,
                state_build_ms,
                total_profile_ms,
                use_vision,
                use_dom,
                use_ui_tree,
                use_annotation,
                display_indices,
            )
        # Log the time taken to capture the state
        end_time = time()
        logger.info(f"Desktop State capture took {end_time - start_time:.2f} seconds")
        return self.desktop_state

    def get_window_status(self, control: uia.Control) -> Status:
        if uia.IsIconic(control.NativeWindowHandle):
            return Status.MINIMIZED
        elif uia.IsZoomed(control.NativeWindowHandle):
            return Status.MAXIMIZED
        elif uia.IsWindowVisible(control.NativeWindowHandle):
            return Status.NORMAL
        else:
            return Status.HIDDEN

    def get_cursor_location(self) -> tuple[int, int]:
        return uia.GetCursorPos()

    def get_apps_from_start_menu(self) -> dict[str, str]:
        """Get installed apps. Tries Get-StartApps first, falls back to shortcut scanning."""
        command = "Get-StartApps | ConvertTo-Csv -NoTypeInformation"
        apps_info, status = PowerShellExecutor.execute_command(command)

        apps: dict[str, str] = {}
        if status == 0 and apps_info and apps_info.strip():
            try:
                reader = csv.DictReader(io.StringIO(apps_info.strip()))
                apps = {
                    row.get("Name", "").lower(): row.get("AppID", "")
                    for row in reader
                    if row.get("Name") and row.get("AppID")
                }
            except Exception as e:
                logger.warning(f"Error parsing Get-StartApps output: {e}")

        if not apps:
            # Fallback: scan Start Menu shortcut folders (works on all Windows versions)
            logger.info("Get-StartApps unavailable, falling back to Start Menu folder scan")
            apps = self._get_apps_from_shortcuts()

        # AppsFolder supplies the display name rendered for the current Windows locale.
        for name, appid in self._get_apps_folder_display_names().items():
            apps.setdefault(name, appid)
        return apps

    def _get_apps_folder_display_names(self) -> dict[str, str]:
        """Return localized Start Menu display names mapped to AppUserModelIDs."""
        command = (
            "(New-Object -ComObject Shell.Application)."
            "NameSpace('shell:::{4234d49b-0245-4df3-b780-3893943456e1}').Items() "
            "| Select-Object Name,@{n='AppID';e={$_.Path}} | ConvertTo-Csv -NoTypeInformation"
        )
        apps_info, status = PowerShellExecutor.execute_command(command)

        if status == 0 and apps_info and apps_info.strip():
            try:
                reader = csv.DictReader(io.StringIO(apps_info.strip()))
                return {
                    row.get("Name", "").lower(): row.get("AppID", "")
                    for row in reader
                    if row.get("Name") and row.get("AppID")
                }
            except Exception as e:
                logger.warning(f"Error parsing AppsFolder display names: {e}")
        return {}

    def _get_apps_from_shortcuts(self) -> dict[str, str]:
        """Scan Start Menu folders for .lnk shortcuts as a fallback for Get-StartApps."""
        import glob

        apps = {}
        start_menu_paths = [
            os.path.join(
                os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                r"Microsoft\Windows\Start Menu\Programs",
            ),
            os.path.join(
                os.environ.get("APPDATA", ""),
                r"Microsoft\Windows\Start Menu\Programs",
            ),
        ]
        for base_path in start_menu_paths:
            if not os.path.isdir(base_path):
                continue
            for lnk_path in glob.glob(os.path.join(base_path, "**", "*.lnk"), recursive=True):
                name = os.path.splitext(os.path.basename(lnk_path))[0].lower()
                if name and name not in apps:
                    apps[name] = lnk_path
        return apps

    def execute_command(
        self, command: str, timeout: int = 10, shell: str | None = None
    ) -> tuple[str, int]:
        return PowerShellExecutor.execute_command(command, timeout, shell)

    def is_window_browser(self, node: uia.Control):
        """Give any node of the app and it will return True if the app is a browser, False otherwise."""
        try:
            process = Process(node.ProcessId)
            return Browser.has_process(process.name())
        except Exception:
            return False

    def _find_windows_by_name(self, name: str | None) -> tuple[list["Window"], str]:
        """Find the windows matching a name, best match first. Returns (windows, error_msg).
        If no window matches, the list is empty and error_msg describes the failure reason.

        Reads the live window list: the last capture's list misses windows opened since,
        and a full get_state() (UI tree + screenshot) is far more than a lookup needs.
        """
        if not name or not name.strip():
            # "" is a substring of every title, so it picked an arbitrary window.
            return [], "Provide the name of a window (the name was empty)."
        window_list, _ = self.get_windows()
        if not window_list:
            return [], "No windows found on the desktop."

        # Keyed by position, not title: two windows can share a title.
        titles = {index: window.name for index, window in enumerate(window_list)}
        matches = process.extractBests(name, titles, score_cutoff=70, limit=None)
        found = [window_list[index] for _, _, index in matches]
        # Short names score too low against long titles ("Edge" vs "... - Microsoft\u200b Edge",
        # whose zero-width space also defeats the fuzzy match), so plain title substrings are
        # added after the fuzzy matches - "h" fuzzy-matched only "Shell" and hid "WMCP Harness".
        # The process name ("msedge", "notepad.exe") is the last resort.
        query = name.casefold().strip()
        found += [
            w
            for w in window_list
            if w not in found and query in _ZERO_WIDTH.sub("", w.name).casefold()
        ]
        # A whole title wins outright; only other windows with that same title stay (R3-6).
        exact = [w for w in found if _ZERO_WIDTH.sub("", w.name).casefold().strip() == query]
        if exact or found:
            return exact or found, ""
        query = query.removesuffix(".exe")
        for window in window_list:
            try:
                exe = Process(window.process_id).name().casefold().removesuffix(".exe")
            except Exception:
                continue
            if exe == query:
                found.append(window)
        if found:
            return found, ""
        return [], f'Window "{name}" not found.'

    @staticmethod
    def _other_matches_note(windows: list["Window"]) -> str:
        """Name the windows a vague name also matched, so a wrong pick is visible."""
        others = [window.name for window in windows[1:]]
        if not others:
            return ""
        shown = ", ".join(f'"{title}"' for title in others[:5])
        more = f" and {len(others) - 5} more" if len(others) > 5 else ""
        return f" Also matched {shown}{more}; use a longer name to pick another."

    def pick_window(
        self, name: str | None, handle: int | None, *, required: bool = False
    ) -> tuple["Window", str]:
        """The window an App window mode acts on, and a note naming other name matches.

        By handle (exact, from App mode='list'), by name, or else the live foreground
        window unless *required*. Raises ValueError when there is no such window.
        """
        if name is not None and handle is not None:
            raise ValueError("Give the window's name or its handle, not both.")
        if handle is not None:
            windows, _ = self.get_windows()
            for window in windows:
                if window.handle == handle:
                    return window, ""
            raise ValueError(
                f"No window has handle {handle}; App mode='list' shows the current ones."
            )
        if name is not None:
            windows, error = self._find_windows_by_name(name)
            if not windows:
                raise ValueError(error)
            return windows[0], self._other_matches_note(windows)
        if required:
            raise ValueError("Give the window's name or handle (App mode='list' shows handles).")
        window = self.get_active_window()
        if window is None:
            raise ValueError("No active window found")
        return window, ""

    def resize_app(
        self,
        name: str | None = None,
        size: tuple[int, int] = None,
        loc: tuple[int, int] = None,
        handle: int | None = None,
    ) -> tuple[str, int]:
        # [0, -5] was applied (the window shrank to its minimum) and a one-number list
        # failed with "not enough values to unpack".
        if size is not None and not (len(size) == 2 and all(v > 0 for v in size)):
            return f"window_size must be two positive numbers [width, height], got {list(size)}", 1
        if loc is not None and len(loc) != 2:
            return f"window_loc must be two numbers [x, y], got {list(loc)}", 1
        try:
            # No name or handle: the live foreground window (the last capture's could be stale).
            target_window, note = self.pick_window(name, handle)
        except ValueError as e:
            return str(e), 1
        if target_window.status == Status.MINIMIZED:
            return f"Cannot resize {target_window.name}: it is minimized. Switch to it first.", 1
        elif target_window.status == Status.MAXIMIZED:
            return (
                f"Cannot resize {target_window.name}: it is maximized. "
                'Restore it first with App mode="restore".',
                1,
            )
        else:
            window_control = uia.ControlFromHandle(target_window.handle)
            # window_loc/window_size mean the visible window, as App list and screenshots
            # show it. MoveWindow takes the outer rect, which adds invisible resize borders
            # (7 px left, right and bottom on Windows 11), so add them back (round-3 R3-I11).
            outer = window_control.BoundingRectangle
            visible = uia.DwmGetWindowExtendFrameBounds(target_window.handle) or outer
            if loc is None:
                loc = (visible.left, visible.top)
            if size is None:
                size = (visible.width(), visible.height())
            x, y = loc
            width, height = size
            # A window fully off every display is unreachable by mouse and looks lost.
            displays = self.get_displays()
            if displays and not any(
                x < d.rect.right
                and d.rect.left < x + width
                and y < d.rect.bottom
                and d.rect.top < y + height
                for d in displays
            ):
                return (
                    f"window_loc {[x, y]} with size {width}x{height} puts "
                    f"{target_window.name} fully off every display.",
                    1,
                )
            left, top = visible.left - outer.left, visible.top - outer.top
            right, bottom = outer.right - visible.right, outer.bottom - visible.bottom
            window_control.MoveWindow(
                x - left, y - top, width + left + right, height + top + bottom
            )
            return (f"{target_window.name} resized to {width}x{height} at {x},{y}.{note}", 0)

    def app(
        self,
        mode: str,
        name: str | None = None,
        loc: tuple[int, int] | None = None,
        size: tuple[int, int] | None = None,
        *,
        handle: int | None = None,
        display: int | None = None,
    ):
        match mode:
            case "minimize" | "maximize" | "restore":
                window, note = self.pick_window(name, handle)
                return window_control.show(window, mode) + note
            case "close":
                # Required: the foreground window is often the client itself.
                window, note = self.pick_window(name, handle, required=True)
                return window_control.close(window) + note
            case "list":
                return window_control.format_list(self.get_windows()[0])
            case "move":
                window, note = self.pick_window(name, handle)
                return window_control.move_to_display(window, self.get_displays(), display) + note
            case "launch":
                # Windows open before the launch are never the launched one: a title match
                # named an older "*report.txt - Notepad" (round-4 R4-2).
                existing = self._top_level_handles()
                response, status, pid = self.launch_app(name)
                if status != 0:
                    # Raised, not returned: a returned message reached the client as a
                    # successful result (is_error=False).
                    raise ValueError(response)
                # On success launch_app returns the matched Start Menu name ("code" ->
                # "visual studio code"); the window title contains that, not the typed text.
                name = response

                # The window's own title: the Start Menu name is lower-cased, and
                # str.title() re-capitalised names wrongly ("Wmcp Harness").
                found = self._wait_for_launched_window(pid, name, existing)
                if found:
                    title, handle = found
                    return f"{title} launched (handle {handle})."
                # Store Notepad can open a tab in its running window instead of a new one.
                front = win32gui.GetForegroundWindow()
                front_title = win32gui.GetWindowText(front) if front in existing else ""
                if name.casefold() in front_title.casefold():
                    return (
                        f"Launching {name} sent; no new window appeared, but the open window "
                        f'"{front_title}" (handle {front}) came to the front (it may have opened '
                        "there)."
                    )
                return f"Launching {name} sent, but window not detected yet."
            case "resize":
                response, status = self.resize_app(name=name, size=size, loc=loc, handle=handle)
            case "switch":
                response, status = self.switch_app(name, handle)
        if status != 0:
            raise ValueError(response)
        return response

    _LAUNCH_WAIT = 10.0  # seconds to look for a launched app's window

    @staticmethod
    def _top_level_handles() -> set[int]:
        handles: set[int] = set()
        win32gui.EnumWindows(lambda handle, _: handles.add(handle) or True, None)
        return handles

    def _wait_for_launched_window(
        self, pid: int, name: str, existing: set[int]
    ) -> tuple[str, int] | None:
        """Title and handle of a new visible, titled window from *pid* or with *name* in its title.

        Handles in *existing* (open before the launch) are skipped. Polls win32 window
        titles instead of a UIA tree walk, which asked every top-level window and failed
        after ~15 s with a UIA timeout when one was slow (round-3 R3-10).
        """
        needle = name.casefold()
        deadline = perf_counter() + self._LAUNCH_WAIT
        while True:
            found = []

            def check(handle, _):
                if handle in existing:
                    return True
                if win32gui.IsWindowVisible(handle) and (title := win32gui.GetWindowText(handle)):
                    if needle in title.casefold() or (
                        pid and win32process.GetWindowThreadProcessId(handle)[1] == pid
                    ):
                        found.append((title, handle))
                return True

            win32gui.EnumWindows(check, None)
            if found:
                return found[0]
            if perf_counter() >= deadline:
                return None
            sleep(0.2)

    def _check_app_exists(self, app_id: str) -> bool:
        """Check if an app with the given AppID exists in shell:AppsFolder."""
        safe_app_id = ps_quote(app_id)
        command = (
            f"$folder = (New-Object -ComObject Shell.Application).NameSpace('shell:AppsFolder'); "
            f"if ($folder) {{ [bool]$folder.ParseName({safe_app_id}) }} else {{ $false }}"
        )
        response, status = PowerShellExecutor.execute_command(command)
        return status == 0 and response.strip().lower() == "true"

    def launch_app(self, name: str | None) -> tuple[str, int, int]:
        if not name or not name.strip():
            return ("Provide the name of an app to launch (the name was empty).", 1, 0)
        apps_map = self.get_apps_from_start_menu()
        matched_app = process.extractOne(name, apps_map.keys(), score_cutoff=70)
        if matched_app is None:
            return (f'"{name}" not found in start menu.', 1, 0)
        app_name, _ = matched_app
        appid = apps_map.get(app_name)
        if appid is None:
            return (f'"{name}" not found in start menu.', 1, 0)

        pid = 0
        if os.path.exists(appid) or "\\" in appid:
            exe_path = resolve_known_folder_guid_path(appid)
            safe_exe_path = ps_quote(exe_path)
            command = f"Start-Process {safe_exe_path} -PassThru | Select-Object -ExpandProperty Id"
            response, status = PowerShellExecutor.execute_command(command)
            if status == 0 and response.strip().isdigit():
                pid = int(response.strip())
        else:
            if not self._check_app_exists(appid):
                return (f"Invalid app identifier: {appid}", 1, 0)

            safe = ps_quote(f"shell:AppsFolder\\{appid}")
            command = f"Start-Process {safe}"
            response, status = PowerShellExecutor.execute_command(command)

        return (app_name if status == 0 else response), status, pid

    def switch_app(self, name: str | None, handle: int | None = None):
        try:
            try:
                window, note = self.pick_window(name, handle, required=True)
            except ValueError as e:
                return str(e), 1

            target_handle = window.handle

            was_minimized = uia.IsIconic(target_handle)
            self.bring_window_to_top(target_handle)
            if was_minimized:
                content = f"Restored {window.name} from minimized and switched to it."
            else:
                content = f"Switched to {window.name} window."
            return content + note, 0
        except Exception as e:
            return (f"Error switching app: {str(e)}", 1)

    def bring_window_to_top(self, target_handle: int):
        if not win32gui.IsWindow(target_handle):
            raise ValueError("Invalid window handle")

        try:
            if win32gui.IsIconic(target_handle):
                win32gui.ShowWindow(target_handle, win32con.SW_RESTORE)

            foreground_handle = win32gui.GetForegroundWindow()

            # Validate both handles before proceeding
            if not win32gui.IsWindow(foreground_handle):
                # No valid foreground window, just try to set target as foreground
                win32gui.SetForegroundWindow(target_handle)
                win32gui.BringWindowToTop(target_handle)
                return

            # We attach our own thread (current_tid) to both the foreground and
            # target window threads to make focus change succeed.
            #
            # Simply attaching foreground_thread to target_thread is not sufficient:
            # SetForegroundWindow is called from our MCP thread, and Windows requires
            # the calling process to satisfy the "received the last input event"
            # criterion. Without attaching current_tid, the system may only bring the
            # target window to the front but refuse to transfer keyboard
            # focus, causing subsequent keyboard input to remain in the previous window.
            #
            # By attaching current_tid to both threads, our thread shares
            # their input state and inherits that eligibility, allowing the system to
            # grant the focus switch.
            foreground_thread, _ = win32process.GetWindowThreadProcessId(foreground_handle)
            target_thread, _ = win32process.GetWindowThreadProcessId(target_handle)
            current_tid = ctypes.windll.kernel32.GetCurrentThreadId()

            if not foreground_thread or not target_thread or foreground_thread == target_thread:
                win32gui.SetForegroundWindow(target_handle)
                win32gui.BringWindowToTop(target_handle)
                return

            ctypes.windll.user32.AllowSetForegroundWindow(-1)

            attached_threads = []
            try:
                for thread in (foreground_thread, target_thread):
                    if thread and thread != current_tid:
                        try:
                            win32process.AttachThreadInput(current_tid, thread, True)
                            attached_threads.append(thread)
                        except Exception as e:
                            # AttachThreadInput fails with Access Denied for elevated
                            # processes (e.g. Settings, Task Manager). Skip the attach
                            # and still attempt SetForegroundWindow below.
                            logger.debug(
                                f"AttachThreadInput failed for thread {thread} "
                                f"(likely elevated process), skipping: {e}"
                            )

                win32gui.SetForegroundWindow(target_handle)
                win32gui.BringWindowToTop(target_handle)

                win32gui.SetWindowPos(
                    target_handle,
                    win32con.HWND_TOP,
                    0,
                    0,
                    0,
                    0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
                )

            finally:
                for tid in reversed(attached_threads):
                    win32process.AttachThreadInput(current_tid, tid, False)

        except Exception as e:
            logger.exception(f"Failed to bring window to top: {e}")

    def find_text(self, text: str, handles: list[int]) -> bool:
        """Return True if any element in the given windows has a name containing `text`.

        The tree capture keeps only interactive/scrollable nodes outside browsers, so
        plain labels ("Saved", "Done") are invisible to it. One native UIA FindFirst
        per window (case-insensitive substring) finds them in tens of milliseconds.
        """
        ia = uia.core._AutomationClient.instance().IUIAutomation
        flags = (
            uia.PropertyConditionFlags.PropertyConditionFlags_IgnoreCase
            | uia.PropertyConditionFlags.PropertyConditionFlags_MatchSubstring
        )
        for handle in handles:
            if is_window_hung(handle) or is_unreadable_window(handle):
                continue
            try:
                condition = ia.CreatePropertyConditionEx(uia.PropertyId.NameProperty, text, flags)
                found = ia.ElementFromHandle(handle).FindFirst(
                    uia.TreeScope.TreeScope_Descendants, condition
                )
            except Exception as e:
                logger.debug("find_text failed for window %s: %s", handle, e)
                continue
            if found:
                return True
        return False

    def _label_tree(self) -> TreeState:
        if self.label_tree_state is None:
            raise ValueError("No element labels yet. Call Snapshot first.")
        return self.label_tree_state

    def get_coordinates_from_label(self, label: int) -> tuple[int, int]:
        return self.get_coordinates_from_labels([label])[0]

    def label_node(self, label: int) -> TreeElementNode | ScrollElementNode:
        """The last Snapshot's element for *label* (interactive first, then scrollable)."""
        tree_state = self._label_tree()
        interactive_nodes = tree_state.interactive_nodes
        scrollable_nodes = tree_state.scrollable_nodes
        if label < 0:  # a negative index would silently pick from the end of the list
            raise IndexError(f"Label {label} out of range")
        if label < len(interactive_nodes):
            return interactive_nodes[label]
        scroll_idx = label - len(interactive_nodes)
        if scroll_idx < len(scrollable_nodes):
            return scrollable_nodes[scroll_idx]
        raise IndexError(f"Label {label} out of range")

    def get_coordinates_from_labels(self, labels: list[int]) -> list[tuple[int, int]]:
        """Resolve multiple UI element labels to screen coordinates in bulk."""
        results = []
        for label in labels:
            element_node = self.label_node(label)
            x, y = element_node.center.x, element_node.center.y
            box = element_node.bounding_box
            window = element_node.window_name
            spot = spot_on_element(
                element_node.name,
                element_node.control_type,
                x,
                y,
                rect=(box.left, box.top, box.right, box.bottom),
                window=window,
            )
            if spot is None:
                what = f'label {label} ({element_node.control_type.lower()} "{element_node.name}")'
                if cover := covering_window(x, y, window):
                    raise ValueError(
                        f'{what} is covered by "{cover}"; bring "{window}" to the front.'
                    )
                raise ValueError(
                    f"{what} is no longer at its spot; the screen changed since Snapshot. "
                    "Take a new Snapshot."
                )
            results.append(spot)
        return results

    def _require_on_screen(self, points: list[tuple[int, int]]) -> None:
        """Refuse points that lie outside every display, before any input is sent.

        Windows clamps an off-screen point to the nearest screen edge and acts
        there (e.g. the show-desktop corner), so the action would land somewhere
        the caller never named. Checked per display, not against the virtual
        screen box, so gaps between displays of different sizes are refused too.
        """
        rects = [display.rect for display in self.get_displays()]
        if not rects:  # monitor enumeration failed: fall back to the virtual screen
            box = self.get_screen_box()
            rects = [uia.Rect(box.left, box.top, box.right, box.bottom)]
        bad = [
            (i, x, y)
            for i, (x, y) in enumerate(points, start=1)
            if not any(rect.contains(x, y) for rect in rects)
        ]
        if not bad:
            return

        def shown(x: int, y: int) -> str:  # in the caller's coordinates, not screen pixels
            return f"({round(x * self.coordinate_scale)},{round(y * self.coordinate_scale)})"

        screens = ", ".join(
            f"{shown(r.left, r.top)}-{shown(r.right - 1, r.bottom - 1)}" for r in rects
        )
        if len(points) == 1:
            targets = f"{shown(bad[0][1], bad[0][2])} is"
        else:
            targets = ", ".join(f"target {i} {shown(x, y)}" for i, x, y in bad)
            targets += " is" if len(bad) == 1 else " are"
        raise ValueError(f"{targets} outside every display; no input was sent. Displays: {screens}")

    # Pause after a click, hover or wheel so the app can react before the reply.
    # Was 0.5 s (round-3 R3-I1); callers needing longer use WaitFor.
    _SETTLE = 0.1

    def is_on_screen(self, x: int, y: int) -> bool:
        """True when the point lies on some display (the same test input tools apply)."""
        try:
            self._require_on_screen([(x, y)])
        except ValueError:
            return False
        return True

    def click(
        self,
        loc: tuple[int, int] | list[int],
        button: str = "left",
        clicks: int = 1,
        modifiers: list[str] = (),
    ):
        if isinstance(loc, list):
            x, y = loc[0], loc[1]
        else:
            x, y = loc
        self._require_on_screen([(x, y)])
        if clicks == 0:
            uia.SetCursorPos(x, y)
            return
        with _keys_held(list(modifiers)):
            self._click_button(x, y, button, clicks)
        sleep(self._SETTLE)  # let the app react; outside the block so modifiers lift at mouse-up

    def _click_button(self, x: int, y: int, button: str, clicks: int) -> None:
        press = {"left": uia.Click, "right": uia.RightClick, "middle": uia.MiddleClick}[button]
        # Presses must fall inside the double-click time, or apps see separate single clicks.
        # Press to press is 0.05 s held + this gap = 0.1 s, inside the fastest setting the
        # Mouse settings slider allows (200 ms). Half the double-click time (0.25 s by
        # default) made a double click 0.48 s (round-4 R4-I4).
        for i in range(clicks):
            press(x, y, waitTime=0.05 if i < clicks - 1 else 0)

    def type(
        self,
        loc: tuple[int, int] | None,
        text: str,
        caret_position: Literal["start", "idle", "end"] = "idle",
        clear: bool | str = False,
        press_enter: bool | str = False,
    ):
        # No location: type into whatever has focus, without a click that could
        # move the caret or drop the selection.
        if loc is not None:
            x, y = loc
            self._require_on_screen([(x, y)])
            uia.Click(x, y, waitTime=self._SETTLE)
        if caret_position == "start":
            uia.SendKeys("{Home}", waitTime=0.05)
        elif caret_position == "end":
            uia.SendKeys("{End}", waitTime=0.05)
        if clear is True or (isinstance(clear, str) and clear.lower() == "true"):
            sleep(self._SETTLE)
            uia.SendKeys("{Ctrl}a", waitTime=0.05)
            uia.SendKeys("{Back}", waitTime=0.05)
            self._finish_clear()
        # Text goes as chunked Unicode events: per-key SendKeys drops keys on slow
        # VMs ("hello tttt…") and cost 0.04 s a key, 26 s for 622 characters
        # (round-3 R3-I2, round-4 R4-1). The clipboard is never used (round-2 2.14).
        # Only line breaks and tabs are real key presses, since apps act on the
        # Enter/Tab keys (new line, next cell) rather than on the characters.
        for part in re.split(r"([\n\t])", text.replace("\r\n", "\n").replace("\r", "")):
            if part == "\n":
                uia.SendKeys("{Enter}", waitTime=0)
            elif part == "\t":
                uia.SendKeys("{Tab}", waitTime=0)
            elif part:
                uia.SendUnicodeText(part)
        if press_enter is True or (isinstance(press_enter, str) and press_enter.lower() == "true"):
            uia.SendKeys("{Enter}", waitTime=0.05)

    def describe_focused_element(self) -> dict[str, object] | None:
        """Name, control type and whether the focused element can take typed text.

        Returns None when nothing has focus or UIA cannot be reached, so a caller
        can fall back to a reply that makes no claim about the focus.
        """
        try:
            focused = uia.GetFocusedControl()
            if focused is None:
                return None
            value = focused.GetPattern(uia.PatternId.ValuePattern)
            if value is not None:
                # A read-only value (a label, a disabled box) takes no text either.
                accepts_text = not value.IsReadOnly
            else:
                accepts_text = focused.GetPattern(uia.PatternId.TextPattern) is not None
            # Localized name ("Button", "Edit") to match what Snapshot prints.
            control_type = (focused.LocalizedControlType or "").title() or focused.ControlTypeName
            return {
                "name": focused.Name,
                "control_type": control_type,
                "accepts_text": accepts_text,
            }
        except Exception as e:
            logger.debug("Could not describe the focused element: %s", e)
            return None

    def _finish_clear(self) -> None:
        # Legacy Win32 EDIT boxes (no visual styles) ignore Ctrl+A, so the Back
        # above removed a single char. Empty any leftover through ValuePattern;
        # fields that cleared normally are untouched.
        try:
            focused = uia.GetFocusedControl()
            pattern = focused.GetPattern(uia.PatternId.ValuePattern) if focused else None
            if pattern is not None and not pattern.IsReadOnly and pattern.Value:
                pattern.SetValue("", waitTime=0.05)  # default waits 0.5 s
        except Exception as e:
            logger.debug("ValuePattern clear fallback failed: %s", e)

    def scroll(
        self,
        loc: tuple[int, int] = None,
        axis: Literal["horizontal", "vertical"] = "vertical",
        direction: Literal["up", "down", "left", "right"] = "down",
        wheel_times: int = 1,
        modifiers: list[str] = (),
    ) -> str | None:
        if loc:
            self.move(loc)
        with _keys_held(list(modifiers)):
            return self._scroll_wheel(axis, direction, wheel_times, bool(modifiers))

    def _scroll_wheel(
        self, axis: str, direction: str, wheel_times: int, keys_held: bool = False
    ) -> str | None:
        match axis:
            case "vertical":
                match direction:
                    case "up":
                        uia.WheelUp(wheel_times, waitTime=self._SETTLE)
                    case "down":
                        uia.WheelDown(wheel_times, waitTime=self._SETTLE)
                    case _:
                        return 'Invalid direction. Use "up" or "down".'
            case "horizontal":
                if direction not in ("left", "right"):
                    return 'Invalid direction. Use "left" or "right".'
                self._scroll_horizontal(direction == "right", wheel_times, keys_held)
            case _:
                return 'Invalid axis. Use "horizontal" or "vertical".'
        return None

    def _cursor_over_unreadable(self) -> bool:
        """True over a hung or VS Code-family window, whose UIA read stalls or freezes it (3.34)."""
        handle = top_level_window_at(*self.get_cursor_location())
        return bool(handle) and (is_window_hung(handle) or is_unreadable_window(handle))

    def _scroll_horizontal(self, right: bool, wheel_times: int, keys_held: bool = False) -> None:
        # Shift+wheel is only a browser/Explorer convention; native apps scroll
        # vertically on it. Prefer the ScrollPattern of the nearest horizontally
        # scrollable element under the cursor, else send a real horizontal wheel.
        # ScrollPattern never sees held keys, so with modifiers only a real wheel is honest.
        pattern = None
        try:
            control = (
                None if keys_held or self._cursor_over_unreadable() else uia.ControlFromCursor()
            )
            while control is not None and pattern is None:
                candidate = control.GetPattern(uia.PatternId.ScrollPattern)
                if candidate is not None and candidate.HorizontallyScrollable:
                    pattern = candidate
                control = control.GetParentControl()
        except Exception as e:
            logger.debug("Horizontal ScrollPattern lookup failed, using wheel: %s", e)
            pattern = None
        if pattern is not None:
            step = uia.ScrollAmount.SmallIncrement if right else uia.ScrollAmount.SmallDecrement
            for _ in range(wheel_times * 3):  # one wheel notch ~ 3 lines, as vertically
                pattern.Scroll(step, uia.ScrollAmount.NoAmount)
            return
        for _ in range(wheel_times):
            uia.mouse_event(uia.MouseEventFlag.HWheel, 0, 0, 120 if right else -120, 0)
            sleep(0.05)

    def _normalize_drag_duration(self, duration: float | int | str | None) -> float | None:
        if duration is None:
            return None
        if isinstance(duration, bool):
            raise ValueError("duration must be a finite number of seconds")
        try:
            effective_duration = float(duration)
        except (TypeError, ValueError) as exc:
            raise ValueError("duration must be a finite number of seconds") from exc
        if not math.isfinite(effective_duration):
            raise ValueError("duration must be a finite number of seconds")
        if effective_duration < 0 or effective_duration > 10:
            raise ValueError("duration must be between 0 and 10 seconds")
        return effective_duration

    @staticmethod
    def _normalize_drag_point(value: object, name: str) -> tuple[int, int]:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError(f"{name} must be a list or tuple of exactly 2 integers [x, y]")
        x, y = value
        if any(isinstance(item, bool) or not isinstance(item, int) for item in (x, y)):
            raise ValueError(f"{name} must contain exactly 2 integers")
        return x, y

    def drag(
        self,
        loc: tuple[int, int] | list[int],
        from_loc: tuple[int, int] | list[int] | None = None,
        duration: float | int | str | None = None,
        modifiers: list[str] = (),
    ) -> dict[str, object]:
        x, y = self._normalize_drag_point(loc, "loc")
        normalized_from_loc = (
            None if from_loc is None else self._normalize_drag_point(from_loc, "from_loc")
        )
        effective_duration = self._normalize_drag_duration(duration)
        self._require_on_screen([(x, y)] + ([normalized_from_loc] if normalized_from_loc else []))
        if normalized_from_loc is None:
            cx, cy = uia.GetCursorPos()
        else:
            cx, cy = normalized_from_loc
        # No fixed 0.5 s before and after (round-4 R4-I4: drag took 1.29 s); the settle
        # matches the other input tools (R3-I1). The pointer path itself is unchanged.
        with _keys_held(list(modifiers)):
            uia.DragDrop(
                cx, cy, x, y, moveSpeed=1, waitTime=self._SETTLE, duration=effective_duration
            )
        return {
            "start": [cx, cy],
            "end": [x, y],
            "duration": effective_duration,
        }

    def move(self, loc: tuple[int, int]):
        x, y = loc
        self._require_on_screen([(x, y)])
        uia.MoveTo(x, y, moveSpeed=10, waitTime=self._SETTLE)

    _left_held = False  # set by mouse_button("down"), cleared by any release

    def mouse_button(self, loc: tuple[int, int] | list[int], action: Literal["down", "up"]) -> bool:
        """Press or release the left button at *loc*, for drags one straight move can't do.

        Returns False, sending nothing, for "up" when this server holds no button.
        """
        x, y = loc
        self._require_on_screen([(x, y)])
        if action == "down":
            if self._left_held:
                raise ValueError(
                    "The left mouse button is already held; release it with mouse_button='up' first."
                )
            uia.PressMouse(x, y, waitTime=0.05)
            self._left_held = True
            return True
        if not self._left_held:
            return False
        uia.SetCursorPos(x, y)
        uia.ReleaseMouse(waitTime=0.05)
        self._left_held = False
        return True

    def release_held_button(self) -> bool:
        """Release a button left down by mouse_button("down"), in place; True if one was held.

        A held button captures the mouse, so another click would go to the drag target.
        """
        if not self._left_held:
            return False
        uia.ReleaseMouse(waitTime=0.05)
        self._left_held = False
        return True

    def release_all(self) -> list[str]:
        """Send key-up/button-up for every modifier and mouse button that is down.

        Returns the names of what was released; nothing is sent for what is already up.
        """
        released = []
        for name, code in _RELEASABLE_KEYS:
            if uia.IsKeyPressed(code):
                _release_key(code)
                released.append(name)
        for name, code, release in _RELEASABLE_BUTTONS:
            ours = code == uia.Keys.VK_LBUTTON and self._left_held
            if ours or uia.IsKeyPressed(code):
                getattr(uia, release)(waitTime=0.05)
                released.append(name)
        self._left_held = False
        return released

    def shortcut(self, shortcut: str, repeat: int = 1, hold: float | None = None):
        keys = _shortcut_keys(shortcut)
        if hold is not None:
            # Held down as real key-down events; like a physical key held by
            # software, it does not auto-repeat characters (use repeat for that).
            with _keys_held(keys):
                sleep(hold)
            return
        sendkeys_str = ""
        for key in keys:
            name = _key_name(key)
            if name == "+" and len(keys) > 1:
                # "+" is not a SendKeys character code, so Ctrl would not combine with
                # it; the "=/+" key is what apps read as Ctrl+Plus (zoom in).
                sendkeys_str += "{OEM_PLUS}"
            elif len(name) == 1:
                sendkeys_str += _escape_text_for_sendkeys(name)
            else:
                sendkeys_str += "{" + name + "}"
        for _ in range(repeat):
            # SendKeys' default 0.5 s settle made repeat=100 block for ~50 s.
            uia.SendKeys(sendkeys_str, interval=0.01, waitTime=0.02)

    def multi_select(self, press_ctrl: bool | str = False, locs: list[tuple[int, int]] = []):
        press_ctrl = press_ctrl is True or (
            isinstance(press_ctrl, str) and press_ctrl.lower() == "true"
        )
        self._require_on_screen([(loc[0], loc[1]) for loc in locs])
        if press_ctrl:
            uia.PressKey(uia.Keys.VK_CONTROL, waitTime=0.05)
        for loc in locs:
            x, y = loc
            uia.Click(x, y, waitTime=self._SETTLE)
        uia.ReleaseKey(uia.Keys.VK_CONTROL, waitTime=0.05)

    def multi_edit(self, locs: list[tuple[int, int, str]]):
        points = [(loc[0], loc[1]) for loc in locs]
        self._require_on_screen(points)
        for i, (x, y, text) in enumerate(locs):
            try:
                self.type((x, y), text=text, clear=True)
            except Exception as e:
                done = ", ".join(f"({px},{py})" for px, py in points[:i]) or "none"
                not_done = ", ".join(f"({px},{py})" for px, py in points[i:])
                raise RuntimeError(
                    f"MultiEdit stopped at ({x},{y}): {e}. done: {done}; not done: {not_done}"
                ) from e

    def scrape(self, url: str) -> str:
        current_url = url
        try:
            for _ in range(5):
                validate_url(current_url)
                response = _http_session.get(current_url, timeout=10, allow_redirects=False)
                if not response.is_redirect:
                    break
                location = response.headers.get("Location")
                if not location:
                    raise ValueError(f"Redirect from {current_url} has no Location header")
                current_url = urljoin(current_url, location)
            else:
                raise ValueError("Too many redirects while fetching URL")
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise ValueError(f"HTTP error for {current_url}: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to {current_url}: {e}") from e
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"Request timed out for {current_url}: {e}") from e
        # Relative links ("/domains") mean nothing once the page is text; resolve them
        # against the address the page was actually served from (after redirects).
        soup = BeautifulSoup(response.text, "html.parser")
        for attr in ("href", "src"):
            for tag in soup.find_all(attrs={attr: True}):
                tag[attr] = urljoin(current_url, tag[attr])
        return MarkdownConverter().convert_soup(soup)

    def is_overlay_window(self, element: uia.Control) -> bool:
        """Return True if the window is a decorative overlay rather than a real app window.

        "No children" alone is deliberately not enough. When UIA child
        enumeration degrades — as it does on Windows ARM64 under x86-emulated
        Python — every window looks childless, and treating that as an overlay
        filters out the entire desktop and leaves the caller blind. A real app
        window always has a title, so require both signals.
        """
        name = element.Name.strip()
        if "Overlay" in name:
            return True
        return not name and len(element.GetChildren()) == 0

    def get_controls_handles(self, optimized: bool = False) -> list[int]:
        # A dict, not a set: EnumWindows lists windows front to back, and App list and the
        # Depth column show that order (round-4 R4-I6).
        handles: dict[int, None] = {}

        # For even more faster results (still under development)
        def callback(hwnd, _):
            try:
                # Validate handle before checking properties
                if (
                    win32gui.IsWindow(hwnd)
                    and win32gui.IsWindowVisible(hwnd)
                    and is_window_on_current_desktop(hwnd)
                    # UIA calls on a not-responding window block forever, stalling the
                    # whole capture — drop it before anything downstream touches it.
                    and not is_window_hung(hwnd)
                ):
                    handles[hwnd] = None
            except Exception:
                # Skip invalid handles without logging (common during window enumeration)
                pass

        win32gui.EnumWindows(callback, None)

        for class_name in ("Progman", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            if hwnd := win32gui.FindWindow(class_name, None):
                handles.setdefault(hwnd, None)
        return list(handles)

    # Tuned retry envelope for transient UIA empty results. The OS
    # briefly returns NULL from GetForegroundWindow during focus
    # transitions, app launches, and notification overlays — three
    # attempts at 100 ms each covers the typical race without
    # noticeably slowing the snapshot path when state is steady.
    _UIA_RETRIES = 3
    _UIA_RETRY_SLEEP_MS = 100

    def get_active_window(self, windows: list[Window] | None = None) -> Window | None:
        """Return the foreground app window, retrying briefly on transient
        empty results.

        GetForegroundWindow can return NULL during focus transitions, app
        launches, and notification-overlay flicker — even when there is a
        visible focused window on screen. Without a retry, Snapshot
        reports "No active window found" and the caller is left blind.
        """
        last_error = None
        for attempt in range(self._UIA_RETRIES):
            try:
                if windows is None:
                    windows, _ = self.get_windows()
                active_window = self.get_foreground_window()
                if active_window is None:
                    # NULL foreground — retry, this often clears on the
                    # next pass once whatever was transitioning settles.
                    sleep(self._UIA_RETRY_SLEEP_MS / 1000.0)
                    continue
                if active_window.ClassName == "Progman":
                    return None
                active_window_handle = active_window.NativeWindowHandle
                for window in windows:
                    if window.handle != active_window_handle:
                        continue
                    return window
                # In case active window is not present in the windows list
                return Window(
                    **{
                        "name": active_window.Name,
                        "is_browser": self.is_window_browser(active_window),
                        "depth": 0,
                        "bounding_box": self._window_box(active_window),
                        "status": self.get_window_status(active_window),
                        "handle": active_window_handle,
                        "process_id": active_window.ProcessId,
                    }
                )
            except Exception as ex:
                last_error = ex
                # Same retry policy for transient exceptions —
                # ControlFromHandle(NULL) raises during focus transitions
                # and the next attempt usually succeeds.
                sleep(self._UIA_RETRY_SLEEP_MS / 1000.0)
                continue
        if last_error is not None:
            logger.error(
                f"Error in get_active_window after {self._UIA_RETRIES} retries: {last_error}"
            )
        return None

    def get_foreground_window(self) -> uia.Control | None:
        handle = uia.GetForegroundWindow()
        # NULL handle means no window has foreground focus right now —
        # don't pass that into ControlFromHandle, which would raise.
        # A not-responding foreground window would make ControlFromHandle block forever.
        if not handle or is_window_hung(handle):
            return None
        return self.get_window_from_element_handle(handle)

    def get_window_from_element_handle(self, element_handle: int) -> uia.Control:
        current = uia.ControlFromHandle(element_handle)
        root_handle = uia.GetRootControl().NativeWindowHandle

        while True:
            parent = current.GetParentControl()
            if parent is None or parent.NativeWindowHandle == root_handle:
                return current
            current = parent

    def get_windows(
        self, controls_handles: list[int] | None = None
    ) -> tuple[list[Window], set[int]]:
        try:
            windows = []
            window_handles = set()
            controls_handles = controls_handles or self.get_controls_handles()
            foreground = uia.GetForegroundWindow()
            for depth, hwnd in enumerate(controls_handles):
                try:
                    child = uia.ControlFromHandle(hwnd)
                except Exception:
                    continue

                # Filter out Overlays (e.g. NVIDIA, Steam)
                if self.is_overlay_window(child):
                    continue

                if isinstance(child, (uia.WindowControl, uia.PaneControl)):
                    window_pattern = child.GetPattern(uia.PatternId.WindowPattern)
                    if window_pattern is None:
                        continue

                    # Not CanMaximize: fixed-size dialogs and apps showing a modal question
                    # can't maximize but are real windows. Helpers are tool windows or
                    # untitled; whatever is in front always counts (e.g. antivirus alerts).
                    is_tool = (
                        win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                        & win32con.WS_EX_TOOLWINDOW
                    )
                    if hwnd == foreground or (child.Name.strip() and not is_tool):
                        status = self.get_window_status(child)

                        bounding_rect = child.BoundingRectangle
                        if bounding_rect.isempty() and status != Status.MINIMIZED:
                            continue

                        windows.append(
                            Window(
                                **{
                                    "name": child.Name,
                                    "depth": depth,
                                    "status": status,
                                    "bounding_box": self._window_box(child),
                                    "handle": child.NativeWindowHandle,
                                    "process_id": child.ProcessId,
                                    "is_browser": self.is_window_browser(child),
                                }
                            )
                        )
                        window_handles.add(child.NativeWindowHandle)
        except Exception as ex:
            logger.error(f"Error in get_windows: {ex}")
            windows = []
        return windows, window_handles

    def _window_box(self, control: uia.Control) -> BoundingBox:
        # The visible frame: the outer rect adds invisible resize borders (7 px a side,
        # 8 when maximised), so the listed size would not match what the image shows.
        handle = control.NativeWindowHandle
        box = self._rect_to_bounding_box(
            uia.DwmGetWindowExtendFrameBounds(handle) or control.BoundingRectangle
        )
        if uia.IsZoomed(handle):
            # Some apps' DWM frame is the outer rect (FactsERP: (-8,-8) 1936x1048); a
            # maximised window shows only its monitor's work area (round-4 R4-12).
            monitor = win32api.MonitorFromWindow(handle, win32con.MONITOR_DEFAULTTONEAREST)
            left, top, right, bottom = win32api.GetMonitorInfo(monitor)["Work"]
            box = self._rect_to_bounding_box(
                uia.Rect(
                    max(box.left, left),
                    max(box.top, top),
                    min(box.right, right),
                    min(box.bottom, bottom),
                )
            )
        return box

    def get_screen_size(self) -> Size:
        width, height = uia.GetVirtualScreenSize()
        return Size(width=width, height=height)

    def get_screen_box(self) -> BoundingBox:
        left, top, width, height = uia.GetVirtualScreenRect()
        return BoundingBox(
            left=left,
            top=top,
            right=left + width,
            bottom=top + height,
            width=width,
            height=height,
        )

    @staticmethod
    def parse_display_selection(
        display: int | list[int] | tuple[int, ...] | None,
    ) -> list[int] | None:
        if display is None or display == "":
            return None

        if isinstance(display, bool):
            raise ValueError(
                "display must be a JSON array of zero-based active display indices, for example [0] or [0,1]"
            )

        if isinstance(display, int):
            values = [display]
        elif isinstance(display, (list, tuple)):
            values = list(display)
        else:
            raise ValueError(
                "display must be a JSON array of zero-based active display indices, for example [0] or [0,1]"
            )

        unique_values: list[int] = []
        for value in values:
            if not isinstance(value, int) or value < 0:
                raise ValueError("display must contain only zero-based active display indices")
            if value not in unique_values:
                unique_values.append(value)
        return unique_values or None

    def parse_region_selection(self, region: list[int] | tuple[int, ...] | None) -> uia.Rect | None:
        if region is None or region == "":
            return None

        if not isinstance(region, (list, tuple)) or len(region) != 4:
            raise ValueError("region must be a JSON array of 4 integers [left, top, right, bottom]")

        values = []
        for item in region:
            if isinstance(item, bool) or not isinstance(item, int):
                raise ValueError("region must contain only integers [left, top, right, bottom]")
            values.append(item)

        left, top, right, bottom = values
        if right <= left or bottom <= top:
            raise ValueError("region must satisfy right > left and bottom > top")

        candidate = uia.Rect(left, top, right, bottom)
        screen_box = self.get_screen_box()
        screen_rect = uia.Rect(screen_box.left, screen_box.top, screen_box.right, screen_box.bottom)
        overlap = candidate.intersect(screen_rect)
        if overlap.width() <= 0 or overlap.height() <= 0:
            raise ValueError(
                f"region {region} does not overlap the virtual screen bounds "
                f"{screen_box.xyxy_to_string()}"
            )
        if overlap != candidate:
            # Capturing only the on-screen part would silently return less than was asked.
            raise ValueError(
                f"region {region} goes past the screen bounds {screen_box.xyxy_to_string()} "
                "(right and bottom are exclusive)"
            )

        return candidate

    @staticmethod
    def get_displays() -> list[uia.DisplayInfo]:
        return uia.GetDisplays()

    @staticmethod
    def _display_to_view(display: uia.DisplayInfo) -> Display:
        return Display(
            index=display.index,
            device_name=display.device_name,
            bounding_box=Desktop._rect_to_bounding_box(display.rect),
            primary=display.primary,
        )

    def get_display_union_rect(
        self,
        display_indices: list[int],
        displays: list[uia.DisplayInfo] | None = None,
    ) -> uia.Rect:
        displays = displays if displays is not None else self.get_displays()
        if not displays:
            logger.warning(
                "Monitor enumeration returned no monitors while display filter was requested"
            )
            raise ValueError("No displays detected")

        display_by_index = {display.index: display for display in displays}
        invalid_indices = [index for index in display_indices if index not in display_by_index]
        if invalid_indices:
            available_indices = ",".join(str(display.index) for display in displays)
            logger.warning(
                "Invalid display selection %s. Available displays: %s",
                invalid_indices,
                available_indices,
            )
            raise ValueError(
                f"Invalid display index {invalid_indices[0]}. Available displays: {available_indices}"
            )

        selected_rects = [display_by_index[index].rect for index in display_indices]
        return uia.Rect(
            left=min(rect.left for rect in selected_rects),
            top=min(rect.top for rect in selected_rects),
            right=max(rect.right for rect in selected_rects),
            bottom=max(rect.bottom for rect in selected_rects),
        )

    def get_screenshot(self, capture_rect: uia.Rect | None = None) -> Image.Image:
        flash_overlay.cancel_active_flash()
        image, used_backend = screenshot_capture.capture(capture_rect)
        self._last_screenshot_backend = used_backend
        flash_overlay.show_capture_flash(capture_rect)
        return image

    def get_annotated_screenshot(
        self,
        nodes: list[TreeElementNode],
        cursor_pos: tuple[int, int] | None = None,
        grid_lines: tuple[int, int] | None = None,
        capture_rect: uia.Rect | None = None,
    ) -> Image.Image:
        screenshot = self.get_screenshot(capture_rect=capture_rect)
        annotated_screenshot = screenshot.copy()
        draw = ImageDraw.Draw(annotated_screenshot)
        image_width, image_height = annotated_screenshot.size
        font_size = 12
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()

        def get_random_color():
            return "#{:06x}".format(random.randint(0, 0xFFFFFF))

        def clamp(value: float, minimum: float, maximum: float) -> float:
            return max(minimum, min(value, maximum))

        def get_label_size(text: str) -> tuple[int, int]:
            text_box = draw.textbbox((0, 0), text, font=font)
            return text_box[2] - text_box[0] + 4, text_box[3] - text_box[1] + 4

        def draw_label(text: str, x: float, y: float, color: str) -> None:
            label_width, label_height = get_label_size(text)
            label_x = int(clamp(x, 0, max(0, image_width - label_width)))
            label_y = int(clamp(y, 0, max(0, image_height - label_height)))
            draw.rectangle(
                [(label_x, label_y), (label_x + label_width, label_y + label_height)],
                fill=color,
            )
            draw.text((label_x + 2, label_y + 2), text, fill=(255, 255, 255), font=font)

        if capture_rect:
            left_offset, top_offset = capture_rect.left, capture_rect.top
        else:
            left_offset, top_offset, _, _ = uia.GetVirtualScreenRect()

        if grid_lines:
            draw_grid(annotated_screenshot, grid_lines)

        def clip_box(node: TreeElementNode) -> tuple[int, int, int, int] | None:
            box = node.bounding_box
            adjusted_left = int(box.left - left_offset)
            adjusted_top = int(box.top - top_offset)
            adjusted_right = int(box.right - left_offset)
            adjusted_bottom = int(box.bottom - top_offset)
            clipped_box = (
                int(clamp(adjusted_left, 0, image_width - 1)),
                int(clamp(adjusted_top, 0, image_height - 1)),
                int(clamp(adjusted_right, 0, image_width - 1)),
                int(clamp(adjusted_bottom, 0, image_height - 1)),
            )
            left, top, right, bottom = clipped_box
            if right <= left or bottom <= top:
                return None
            return clipped_box

        # Draw annotations sequentially: PIL ImageDraw is not thread-safe and
        # drawing is GIL-bound, so parallel execution adds risk without speed.
        # All outlines go down before any badge so a later box's outline can
        # never paint over an earlier element's number.
        boxes = [(i, clip_box(node), get_random_color()) for i, node in enumerate(nodes)]
        boxes = [(i, box, color) for i, box, color in boxes if box is not None]
        for _, box, color in boxes:
            draw.rectangle(box, outline=color, width=2)
        placed: list[tuple[int, int, int, int]] = []
        for i, box, color in boxes:
            label_text = str(i)
            label_width, label_height = get_label_size(label_text)
            label_x, label_y = place_badge(
                box, (label_width, label_height), placed, (image_width, image_height)
            )
            placed.append((label_x, label_y, label_x + label_width, label_y + label_height))
            draw_label(label_text, label_x, label_y, color)

        # Draw cursor highlight if pos provided
        if cursor_pos:
            cx, cy = cursor_pos
            acx = int(cx - left_offset)
            acy = int(cy - top_offset)

            # Draw a distinctive marker (e.g., a circle or crosshair with a box)
            r = 15
            draw.ellipse([acx - r, acy - r, acx + r, acy + r], outline="red", width=3)
            draw.line([acx - r, acy, acx + r, acy], fill="red", width=2)
            draw.line([acx, acy - r, acx, acy + r], fill="red", width=2)

            # Draw "Cursor" label
            c_label = "CURSOR"
            draw_label(c_label, acx + r, acy - r, "red")

        return annotated_screenshot

    @staticmethod
    def _rect_to_bounding_box(rect: uia.Rect | None) -> BoundingBox | None:
        if rect is None:
            return None
        return BoundingBox(
            left=rect.left,
            top=rect.top,
            right=rect.right,
            bottom=rect.bottom,
            width=rect.width(),
            height=rect.height(),
        )

    @staticmethod
    def _point_in_region(point: tuple[int, int], region: BoundingBox) -> bool:
        x, y = point
        return region.left <= x < region.right and region.top <= y < region.bottom

    @staticmethod
    def _clip_bounding_box_to_region(
        box: BoundingBox | None, region: BoundingBox
    ) -> BoundingBox | None:
        if box is None:
            return None
        left = max(box.left, region.left)
        top = max(box.top, region.top)
        right = min(box.right, region.right)
        bottom = min(box.bottom, region.bottom)
        if right <= left or bottom <= top:
            return None
        return BoundingBox(
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            width=right - left,
            height=bottom - top,
        )

    def _select_tree_handles(
        self,
        active_window: Window | None,
        other_handles: set[int],
        windows: list[Window],
        region: BoundingBox | None,
    ) -> tuple[int | None, list[int]]:
        """Pick the windows whose UI tree is read.

        Without a region: the active window plus the non-app windows (taskbar,
        desktop, pop-ups). With a region: only windows whose visible frame overlaps
        it, so a small-area Snapshot no longer reads the whole desktop first.
        """
        active_handle = active_window.handle if active_window else None
        if region is None:
            return active_handle, list(other_handles)

        def in_region(handle: int, known_box: BoundingBox | None = None) -> bool:
            return self._visible_frame_overlaps(handle, known_box, region)

        def seen_in_region(handle: int, known_box: BoundingBox | None = None) -> bool:
            # Overlapping is not enough: a window buried under others in the region
            # would spend the element cap on elements that are then dropped as hidden.
            if not in_region(handle, known_box):
                return False
            frame = uia.DwmGetWindowExtendFrameBounds(handle) or known_box
            if frame is None:
                return True
            part = uia.Rect(
                max(frame.left, region.left),
                max(frame.top, region.top),
                min(frame.right, region.right),
                min(frame.bottom, region.bottom),
            )
            return not is_fully_covered(handle, part)

        active = (
            active_handle
            if active_window and in_region(active_handle, active_window.bounding_box)
            else None
        )
        others = [h for h in other_handles if seen_in_region(h)]
        others += [w.handle for w in windows if seen_in_region(w.handle, w.bounding_box)]
        return active, others

    @staticmethod
    def _visible_frame_overlaps(
        handle: int, known_box: BoundingBox | None, region: BoundingBox
    ) -> bool:
        # The visible frame excludes invisible resize borders: a maximised window's border
        # reaches under the taskbar, or 8 px onto the next display, and would otherwise
        # count as overlapping.
        rect = uia.DwmGetWindowExtendFrameBounds(handle) or known_box
        if rect is None:
            return True  # can't measure it: keep it, as before
        return (
            rect.left < region.right
            and rect.right > region.left
            and rect.top < region.bottom
            and rect.bottom > region.top
        )

    def _filter_window_to_region(self, window: Window | None, region: BoundingBox) -> Window | None:
        # Kept whole, not clipped: a clipped box listed every maximised window at the
        # region's own size (e.g. 500x40).
        if window is None:
            return None
        if not self._visible_frame_overlaps(window.handle, window.bounding_box, region):
            return None
        return window

    def _filter_windows_to_region(self, windows: list[Window], region: BoundingBox) -> list[Window]:
        filtered_windows: list[Window] = []
        for window in windows:
            filtered_window = self._filter_window_to_region(window, region)
            if filtered_window is not None:
                filtered_windows.append(filtered_window)
        return filtered_windows

    def _filter_tree_node_to_region(
        self, node: TreeElementNode, region: BoundingBox
    ) -> TreeElementNode | None:
        clipped_box = self._clip_bounding_box_to_region(node.bounding_box, region)
        if clipped_box is None:
            return None
        return TreeElementNode(
            name=node.name,
            control_type=node.control_type,
            window_name=node.window_name,
            bounding_box=clipped_box,
            center=clipped_box.get_center(),
            metadata=node.metadata,
        )

    def _filter_scroll_node_to_region(self, node, region: BoundingBox):
        clipped_box = self._clip_bounding_box_to_region(node.bounding_box, region)
        if clipped_box is None:
            return None
        return node.__class__(
            name=node.name,
            control_type=node.control_type,
            window_name=node.window_name,
            bounding_box=clipped_box,
            center=clipped_box.get_center(),
            metadata=node.metadata,
        )

    @staticmethod
    def _clip_moves_onto_other_window(center, clipped_box: BoundingBox) -> bool:
        """True when clipping moved an element's click point onto a different window.

        The hidden-element filter already proved the window at the original centre
        is the element's own. A partly-in-region element gets its centre moved into
        the clipped part, which a covering window may own: a click there would hit
        that window instead.
        """
        new = clipped_box.get_center()
        if center is None or (new.x, new.y) == (center.x, center.y):
            return False
        return top_level_window_at(center.x, center.y) != top_level_window_at(new.x, new.y)

    def _filter_semantic_node_to_region(
        self,
        node: SemanticNode | None,
        region: BoundingBox,
    ) -> SemanticNode | None:
        if node is None:
            return None

        clipped_box = None
        if node.bounding_box is not None:
            clipped_box = self._clip_bounding_box_to_region(node.bounding_box, region)
            if clipped_box is None:
                return None
            if node.element_type in ("interactive", "scrollable") and (
                self._clip_moves_onto_other_window(node.center, clipped_box)
            ):
                return None

        filtered_children = []
        for child in node.children:
            filtered_child = self._filter_semantic_node_to_region(child, region)
            if filtered_child is not None:
                filtered_children.append(filtered_child)

        if node.element_type != "desktop" and clipped_box is None and not filtered_children:
            return None

        filtered_node = SemanticNode(
            control_type=node.control_type,
            element_type=node.element_type,
            name=node.name,
            window_name=node.window_name,
            center=clipped_box.get_center() if clipped_box is not None else node.center,
            bounding_box=clipped_box,
            metadata=dict(node.metadata),
        )
        filtered_node.children = filtered_children
        return filtered_node

    def _filter_tree_state_to_region(self, tree_state, region: BoundingBox):
        def reachable(node, filtered_node) -> bool:
            return filtered_node is not None and not self._clip_moves_onto_other_window(
                node.center, filtered_node.bounding_box
            )

        filtered_interactive_nodes = []
        for node in tree_state.interactive_nodes:
            filtered_node = self._filter_tree_node_to_region(node, region)
            if reachable(node, filtered_node):
                filtered_interactive_nodes.append(filtered_node)

        filtered_scrollable_nodes = []
        for node in tree_state.scrollable_nodes:
            filtered_node = self._filter_scroll_node_to_region(node, region)
            if reachable(node, filtered_node):
                filtered_scrollable_nodes.append(filtered_node)

        filtered_dom_node = None
        if tree_state.dom_node is not None:
            filtered_dom_node = self._filter_scroll_node_to_region(tree_state.dom_node, region)

        filtered_semantic_root = self._filter_semantic_node_to_region(
            tree_state.semantic_tree_root,
            region,
        )
        if filtered_semantic_root is not None:
            filtered_semantic_root.bounding_box = region
            filtered_semantic_root.center = region.get_center()

        return tree_state.__class__(
            status=tree_state.status,
            root_node=TreeElementNode(
                name="Desktop",
                control_type="PaneControl",
                bounding_box=region,
                center=region.get_center(),
                window_name="Desktop",
                metadata={},
            ),
            dom_node=filtered_dom_node,
            interactive_nodes=filtered_interactive_nodes,
            scrollable_nodes=filtered_scrollable_nodes,
            dom_informative_nodes=tree_state.dom_informative_nodes if filtered_dom_node else [],
            capture_sec=tree_state.capture_sec,
            semantic_tree_root=filtered_semantic_root,
            truncated=tree_state.truncated,
            element_limit=tree_state.element_limit,
        )
