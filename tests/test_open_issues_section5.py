"""Regression tests for bugs found while filling Plan/windows-mcp-open-issues.md section 5."""

from unittest.mock import MagicMock, patch

import pytest

from windows_mcp.desktop.service import Desktop
from windows_mcp.powershell import PowerShellExecutor


def test_app_launch_names_the_matched_start_menu_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """5.1: App launch "code" must look for and name "Visual Studio Code", not "Code"."""
    app_id = "Microsoft.VisualStudioCode"
    monkeypatch.setattr(PowerShellExecutor, "execute_command", staticmethod(lambda *_: ("", 0)))
    desktop = Desktop.__new__(Desktop)
    monkeypatch.setattr(desktop, "get_apps_from_start_menu", lambda: {"visual studio code": app_id})
    monkeypatch.setattr(desktop, "_check_app_exists", lambda _: True)

    searched: list[tuple[int, str]] = []

    def wait(pid: int, name: str, existing: set[int]) -> tuple[str, int]:
        searched.append((pid, name))
        return "Visual Studio Code", 7

    monkeypatch.setattr(desktop, "_wait_for_launched_window", wait)
    monkeypatch.setattr(desktop, "_top_level_handles", lambda: set())
    reply = desktop.app("launch", name="code")

    assert reply == "Visual Studio Code launched (handle 7)."
    assert searched == [(0, "visual studio code")]


def _box(left: int, top: int, right: int, bottom: int):
    from windows_mcp.tree.views import BoundingBox

    return BoundingBox(
        left=left, top=top, right=right, bottom=bottom, width=right - left, height=bottom - top
    )


def test_tree_uses_the_current_desktop_size_not_the_startup_one() -> None:
    """5.3: a monitor added after the server started must not be clipped away."""
    from windows_mcp.tree.service import Tree

    desktop = MagicMock()
    desktop.get_screen_box.return_value = _box(0, 0, 1920, 1080)  # one display at startup
    tree = Tree(desktop)
    desktop.get_screen_box.return_value = _box(0, 0, 2720, 1080)  # second display plugged in

    with patch.object(Tree, "get_window_wise_nodes", return_value=([], [], [], [], [])):
        state = tree.get_state(None, [])

    assert state.root_node.bounding_box.right == 2720
    assert (
        tree.iou_bounding_box(_rect(2000, 50, 2640, 500), _rect(2100, 100, 2200, 130)).width == 100
    )


def _rect(left: int, top: int, right: int, bottom: int):
    from windows_mcp.uia.core import Rect

    return Rect(left, top, right, bottom)


def test_window_list_ignores_invisible_border_spilling_onto_another_display() -> None:
    """5.3: a window maximised on display 0 must not be listed on display 1 as 8 px wide."""
    from windows_mcp.desktop.views import Status, Window

    desktop = Desktop.__new__(Desktop)
    display_1 = _box(1920, 0, 2720, 600)
    maximised = Window(
        name="VS Code",
        is_browser=False,
        depth=0,
        status=Status.MAXIMIZED,
        bounding_box=_box(-8, -8, 1928, 1048),
        handle=11,
        process_id=1,
    )
    on_display_1 = Window(
        name="Notepad",
        is_browser=False,
        depth=1,
        status=Status.NORMAL,
        bounding_box=_box(2000, 50, 2640, 500),
        handle=12,
        process_id=2,
    )
    frames = {11: _rect(0, 0, 1920, 1040), 12: _rect(2007, 50, 2633, 493)}

    with patch(
        "windows_mcp.desktop.service.uia.DwmGetWindowExtendFrameBounds", side_effect=frames.get
    ):
        kept = desktop._filter_windows_to_region([maximised, on_display_1], display_1)
        active = desktop._filter_window_to_region(maximised, display_1)

    assert [w.name for w in kept] == ["Notepad"]
    assert active is None
