"""Round-6 R6-10: window and app names match through thefuzz, picking what fuzzywuzzy picked."""

import pytest

import windows_mcp.desktop.service as service
from tests.test_app_replies import _desktop, _window

TITLES = [
    "Untitled - Notepad",
    "notes.txt - Notepad",
    "New tab - Microsoft​ Edge",
    "Windows PowerShell",
    "Shell",
    "WMCP Harness",
    "Visual Studio Code",
    "Calculator",
    "Notepad++",
    "Paint",
    "Paint 3D",
    "Snipping Tool",
    "Snip & Sketch",
    "Paint",
]


def test_matching_uses_thefuzz():
    assert service.process.__name__ == "thefuzz.process"


# Handles are 1-based positions in TITLES; order is best match first, as fuzzywuzzy gave it.
@pytest.mark.parametrize(
    "query, handles",
    [
        ("Notepad", [9, 1, 2]),
        ("note", [1, 2, 9]),
        ("Edge", [3]),
        ("Microsoft Edge", [3]),
        ("​Edge", [3]),
        ("h", [5, 4, 6, 13]),
        ("PowerShell", [4, 5]),
        ("power shell", [5, 4]),
        ("Paint", [10, 14]),
        ("Paint 3D", [11]),
        ("Snip", [12, 13]),
        ("Code", [7]),
    ],
)
def test_window_name_picks(query, handles):
    desktop = _desktop([_window(t, i + 1) for i, t in enumerate(TITLES)])
    windows, error = desktop._find_windows_by_name(query)
    assert error == ""
    assert [w.handle for w in windows] == handles


class _AppsMap(dict):
    """Records the app name launch_app picked; returns no id so nothing is launched."""

    picked = None

    def get(self, key, default=None):
        self.picked = key
        return None


APPS = [
    "Notepad",
    "Notepad++",
    "Paint",
    "Paint 3D",
    "Calculator",
    "Microsoft Teams",
    "Teams (work or school)",
    "File Explorer",
    "Snipping Tool",
    "Windows PowerShell",
]


@pytest.mark.parametrize(
    "query, picked",
    [
        ("notepad", "Notepad"),
        # Both libraries drop the "+" signs, so "Notepad" ties at 100 and, listed first, wins.
        ("Notepad++", "Notepad"),
        ("Paint 3D", "Paint 3D"),
        ("calc", "Calculator"),
        ("Teams", "Microsoft Teams"),
        ("explorer", "File Explorer"),
        ("power shell", "Windows PowerShell"),
        ("zz", None),
    ],
)
def test_app_name_picks(query, picked):
    apps = _AppsMap.fromkeys(APPS, "id")
    desktop = _desktop([])
    desktop.get_apps_from_start_menu = lambda: apps
    reply, status, _ = desktop.launch_app(query)
    assert status == 1 and "not found" in reply
    assert apps.picked == picked
