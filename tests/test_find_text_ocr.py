"""Round-2 C.6: find text on screen with Windows' built-in OCR (FindText, WaitFor screen_text)."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from windows_mcp.ocr import service as ocr
from windows_mcp.tools import find_text as find_text_tools
from windows_mcp.tools import input as input_tools


def _word(text, x, y, w=40, h=10):
    return {"t": text, "x": x, "y": y, "w": w, "h": h}


LINES = [
    {"words": [_word("Please", 0, 0), _word("Sign", 50, 0), _word("in", 100, 0, w=20)]},
    {"words": [_word("sign", 0, 30), _word("out", 50, 30)]},
    {"words": [_word("SIGN", 0, 60), _word("IN", 50, 60)]},
]


# --- find_phrase (pure) ----------------------------------------------------------------


def test_a_phrase_spans_words_and_gives_the_centre_of_them():
    matches = ocr.find_phrase(LINES[:1], "sign in", 1000, 500)
    # "Sign" starts at x=50, "in" ends at 120: centre 85; rows 0..10: centre 5.
    assert matches == [("Please Sign in", 1085, 505)]


def test_every_line_with_the_phrase_is_found_ignoring_case():
    assert [m[0] for m in ocr.find_phrase(LINES, "Sign In", 0, 0)] == ["Please Sign in", "SIGN IN"]


def test_part_of_a_word_matches():
    assert ocr.find_phrase(LINES, "lease", 0, 0) == [("Please Sign in", 20, 5)]


def test_words_in_another_order_do_not_match():
    assert ocr.find_phrase(LINES, "in sign", 0, 0) == []


def test_extra_spaces_in_the_phrase_are_ignored():
    assert len(ocr.find_phrase(LINES, "  sign   out ", 0, 0)) == 1


def test_a_phrase_spans_table_columns_on_one_row():
    # Round-3 R3-I6: OCR splits a row at wide gaps, listing each column as its own line
    # (and not always left to right); "North 460 units" spans three of them.
    row = [
        {"words": [_word("units", 400, 101)]},
        {"words": [_word("North", 0, 100)]},
        {"words": [_word("460", 200, 99)]},
        {"words": [_word("South", 0, 130)]},  # the next row stays separate
    ]
    matches = ocr.find_phrase(row, "north 460 units", 0, 0)
    # "North" starts at 0, "units" ends at 440: centre 220; rows 99..111: centre 105.
    assert matches == [("North 460 units", 220, 105)]
    assert ocr.find_phrase(row, "units south", 0, 0) == []


def test_lines_of_two_windows_on_one_row_are_not_joined():
    # Round-4 R4-9: a full-screen search read ".venv North 460 units" (VS Code's side bar
    # beside Notepad). Lines are joined only within the window under them.
    row = [
        {"words": [_word(".venv", 0, 100)]},
        {"words": [_word("North", 200, 100)]},
        {"words": [_word("460", 400, 100)]},
    ]

    def window_at(x, y):
        return 1 if x < 1100 else 2  # screen x: ".venv" 1010, "North" 1110, "460" 1210

    matches = ocr.find_phrase(row, "460", 1000, 0, 2, window_at=window_at)
    assert [m[0] for m in matches] == ["North 460"]
    assert ocr.find_phrase(row, ".venv north", 1000, 0, 2, window_at=window_at) == []


def test_the_window_is_looked_up_at_screen_points(monkeypatch):
    seen = []
    row = [{"words": [_word("North", 200, 100)]}]
    ocr.find_phrase(row, "north", 1000, 50, 2, window_at=lambda x, y: seen.append((x, y)))
    # Word centre (220, 105) in the 2x image is (110, 52) on screen, offset by (1000, 50).
    assert seen == [(1110, 102)]


def test_find_on_screen_splits_rows_by_window(monkeypatch):
    monkeypatch.setattr(
        ocr.screenshot_capture, "capture", lambda rect: (Image.new("RGB", (5000, 100)), "x")
    )
    monkeypatch.setattr(
        ocr,
        "read_lines",
        lambda image: [{"words": [_word("A", 0, 0)]}, {"words": [_word("B", 5000, 0)]}],
    )
    monkeypatch.setattr(ocr, "top_level_window_at", lambda x, y: x)
    rect = SimpleNamespace(left=0, top=0, right=5000, bottom=100)
    assert ocr.find_on_screen("a b", rect) == []


# --- find_on_screen (enlarges before reading) ------------------------------------------


@pytest.mark.parametrize(("width", "factor"), [(420, 3), (5000, 2)])
def test_the_capture_is_enlarged_and_positions_scaled_back(monkeypatch, width, factor):
    # Measured live: at 1x Windows OCR read "Zebra Q uartz" and missed "Save"; 3x read both.
    # The engine refuses images over 10,000 px, so wide captures are enlarged less.
    seen = []
    monkeypatch.setattr(
        ocr.screenshot_capture, "capture", lambda rect: (Image.new("RGB", (width, 100)), "x")
    )

    def read(image):
        seen.append(image.size)
        return [{"words": [_word("Save", 30 * factor, 30 * factor, 10 * factor, 10 * factor)]}]

    monkeypatch.setattr(ocr, "read_lines", read)
    rect = SimpleNamespace(left=100, top=200, right=100 + width, bottom=300)
    assert ocr.find_on_screen("save", rect) == [("Save", 135, 235)]
    assert seen == [(width * factor, 100 * factor)]


# --- read_lines (runs Windows PowerShell) ----------------------------------------------


def test_read_lines_runs_windows_powershell_and_parses_json(monkeypatch):
    run = MagicMock(return_value=(json.dumps({"angle": 0, "lines": LINES}), 0))
    monkeypatch.setattr(ocr.PowerShellExecutor, "execute_command", run)
    assert ocr.read_lines(Image.new("RGB", (10, 10))) == LINES
    # pwsh 7 cannot load WinRT types; only Windows PowerShell 5.1 can.
    assert run.call_args.kwargs["shell"] == "powershell"


def test_read_lines_wraps_a_single_line(monkeypatch):
    out = json.dumps({"angle": None, "lines": LINES[0]})
    monkeypatch.setattr(ocr.PowerShellExecutor, "execute_command", lambda *a, **k: (out, 0))
    assert ocr.read_lines(Image.new("RGB", (10, 10))) == LINES[:1]


def test_word_boxes_are_turned_back_by_the_text_angle(monkeypatch):
    # Round-3 R3-I6, real Windows OCR output (2026-09-24) for words drawn level at a
    # 3x-enlarged 2700x480 image: it reported TextAngle 1.5 and boxes in the tilted
    # frame, so one row's words sat 18 px apart vertically and clicks drifted.
    lines = [
        {"words": [{"t": "North", "x": 62, "y": 106, "w": 212, "h": 72}]},
        {"words": [{"t": "460", "x": 1137, "y": 80, "w": 148, "h": 70}]},
        {"words": [{"t": "units", "x": 2161, "y": 53, "w": 185, "h": 70}]},
    ]
    out = json.dumps({"angle": 1.5, "lines": lines})
    monkeypatch.setattr(ocr.PowerShellExecutor, "execute_command", lambda *a, **k: (out, 0))
    words = [line["words"][0] for line in ocr.read_lines(Image.new("RGB", (2700, 480)))]
    centres = [(w["x"] + w["w"] / 2, w["y"] + w["h"] / 2) for w in words]
    # Drawn centres (3x): x 171, 1216.5, 2256; y 111 for all three. 3 px here is 1 on screen.
    assert all(abs(x - drawn) < 3 for (x, _), drawn in zip(centres, (171, 1216.5, 2256)))
    assert all(abs(y - 111) < 3 for _, y in centres)
    assert ocr.find_phrase(
        ocr.read_lines(Image.new("RGB", (2700, 480))), "North 460 units", 0, 0, 3
    )


def test_read_lines_with_no_text(monkeypatch):
    monkeypatch.setattr(ocr.PowerShellExecutor, "execute_command", lambda *a, **k: ("", 0))
    assert ocr.read_lines(Image.new("RGB", (10, 10))) == []


def test_read_lines_failure_is_an_error_and_the_temp_image_is_removed(monkeypatch):
    seen = []

    def run(command, **kwargs):
        seen.append(command.split("'")[1])  # the quoted image path
        return "No text recognition language is installed.", 1

    monkeypatch.setattr(ocr.PowerShellExecutor, "execute_command", run)
    with pytest.raises(RuntimeError, match="language"):
        ocr.read_lines(Image.new("RGB", (10, 10)))
    assert seen and not __import__("os").path.exists(seen[0])


# --- FindText tool ---------------------------------------------------------------------


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _tool(module, name, desktop):
    mcp = FakeMCP()
    module.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return lambda **kw: asyncio.run(mcp.tools[name](**kw))


def _desktop(scale=1.0):
    desktop = MagicMock()
    desktop.coordinate_scale = scale
    desktop.get_screen_box.return_value = SimpleNamespace(left=0, top=0, right=1920, bottom=1080)
    desktop.parse_region_selection.side_effect = lambda r: (
        None if r is None else SimpleNamespace(left=r[0], top=r[1], right=r[2], bottom=r[3])
    )
    return desktop


@pytest.fixture
def screen(monkeypatch):
    state = SimpleNamespace(matches=[], rects=[])

    def find(text, rect):
        state.rects.append((rect.left, rect.top, rect.right, rect.bottom))
        return state.matches

    monkeypatch.setattr(find_text_tools, "find_on_screen", find)
    return state


def test_find_text_lists_every_spot_in_caller_coordinates(screen):
    screen.matches = [("Sign in", 200, 100), ("Sign in again", 400, 300)]
    reply = _tool(find_text_tools, "FindText", _desktop(scale=0.5))(text="Sign in")
    assert reply == (
        'Found "Sign in" 2 times: (100,50) in "Sign in"; (200,150) in "Sign in again".'
    )
    assert screen.rects == [(0, 0, 1920, 1080)]


def test_find_text_region_is_in_caller_coordinates(screen):
    _tool(find_text_tools, "FindText", _desktop(scale=0.5))(text="x", region="10,20,110,220")
    assert screen.rects == [(20, 40, 220, 440)]


def test_find_text_caps_the_list(screen):
    screen.matches = [("a", i, i) for i in range(12)]
    reply = _tool(find_text_tools, "FindText", _desktop())(text="a")
    assert reply.startswith('Found "a" 12 times') and reply.endswith("and 2 more.")


def test_find_text_not_found_is_a_plain_reply(screen):
    reply = _tool(find_text_tools, "FindText", _desktop())(text="Sign in")
    assert reply.startswith('"Sign in" was not found on screen')


def test_find_text_needs_text(screen):
    with pytest.raises(ValueError, match="text"):
        _tool(find_text_tools, "FindText", _desktop())(text="  ")


# --- WaitFor screen_text ---------------------------------------------------------------


def test_wait_for_screen_text_reports_where_without_reading_the_ui_tree(screen):
    screen.matches = [("Ready", 50, 60)]
    desktop = _desktop()
    reply = _tool(input_tools, "WaitFor", desktop)(condition="screen_text", text="Ready")
    assert "satisfied" in reply and '(50,60) in "Ready"' in reply
    desktop.get_state.assert_not_called()


def test_wait_for_screen_text_times_out(screen):
    with pytest.raises(TimeoutError, match="not on screen"):
        _tool(input_tools, "WaitFor", _desktop())(
            condition="screen_text", text="Ready", timeout=0.05, interval=0.01
        )


def test_wait_for_screen_text_needs_text(screen):
    with pytest.raises(ValueError, match="text is required"):
        _tool(input_tools, "WaitFor", _desktop())(condition="screen_text")


def test_wait_for_screen_text_refuses_window_name(screen):
    with pytest.raises(ValueError, match="region"):
        _tool(input_tools, "WaitFor", _desktop())(
            condition="screen_text", text="Ready", window_name="Notepad"
        )


def test_region_only_goes_with_screen_text(screen):
    with pytest.raises(ValueError, match="screen_text"):
        _tool(input_tools, "WaitFor", _desktop())(
            condition="text_exists", text="Ready", region=[0, 0, 10, 10]
        )
