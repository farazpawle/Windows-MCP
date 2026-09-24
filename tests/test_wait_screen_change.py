"""Round-2 C.7: WaitFor screen_changed / screen_idle compare screen captures."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image, ImageDraw

from windows_mcp.tools import _screen_wait
from windows_mcp.tools import input as input_tools


def _frame(block=None, level=255, size=(400, 300)):
    image = Image.new("RGB", size, "black")
    if block:
        ImageDraw.Draw(image).rectangle(block, fill=(level, level, level))
    return image


BLANK = _frame()


# --- changed_box (pure) ----------------------------------------------------------------


def test_identical_frames_have_no_change():
    assert _screen_wait.changed_box(BLANK, _frame()) is None


def test_a_blinking_caret_is_ignored():
    # 2 x 20 px, the size of a text cursor.
    assert _screen_wait.changed_box(BLANK, _frame((50, 50, 51, 69))) is None


def test_a_faint_change_is_ignored():
    assert _screen_wait.changed_box(BLANK, _frame((0, 0, 199, 199), level=10)) is None


def test_an_icon_sized_change_gives_its_box():
    assert _screen_wait.changed_box(BLANK, _frame((100, 40, 119, 59))) == (100, 40, 120, 60)


def test_a_digit_sized_change_counts_in_a_small_region():
    # R3-4: a clock digit in an 80x30 region changes ~40 px, under the full-screen floor.
    small = _frame(size=(80, 30))
    assert _screen_wait.changed_box(small, _frame((10, 5, 13, 14), size=(80, 30))) is not None


def test_the_same_change_on_a_full_screen_is_ignored():
    full = _frame(size=(1920, 1080))
    assert _screen_wait.changed_box(full, _frame((10, 5, 13, 14), size=(1920, 1080))) is None


def test_a_size_change_counts_as_all_changed():
    assert _screen_wait.changed_box(BLANK, _frame(size=(10, 10))) == (0, 0, 400, 300)


# --- WaitFor ---------------------------------------------------------------------------


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _wait_for(desktop, **kw):
    mcp = FakeMCP()
    input_tools.register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)
    return asyncio.run(mcp.tools["WaitFor"](**kw))


def _desktop(scale=1.0):
    desktop = MagicMock()
    desktop.coordinate_scale = scale
    desktop.get_screen_box.return_value = SimpleNamespace(left=0, top=0, right=1920, bottom=1080)
    desktop.parse_region_selection.side_effect = lambda r: (
        None if r is None else SimpleNamespace(left=r[0], top=r[1], right=r[2], bottom=r[3])
    )
    return desktop


@pytest.fixture
def frames(monkeypatch):
    """Captures come from .queue (the last one repeats); .rects records what was captured."""
    state = SimpleNamespace(queue=[BLANK], rects=[])

    def capture(rect):
        state.rects.append((rect.left, rect.top, rect.right, rect.bottom))
        return state.queue.pop(0) if len(state.queue) > 1 else state.queue[0]

    monkeypatch.setattr(_screen_wait, "capture", capture)
    return state


def test_screen_changed_reports_where_in_caller_coordinates(frames):
    frames.queue = [BLANK, BLANK, _frame((100, 40, 119, 59))]
    desktop = _desktop(scale=0.5)
    reply = _wait_for(desktop, condition="screen_changed", region=[50, 50, 250, 200], interval=0.01)
    # The first capture is the baseline, so the change is seen on the second attempt.
    assert "satisfied" in reply and "2 attempt(s)" in reply
    # Region [100,100,500,400] on screen; change at +(100,40)..(120,60) -> halved.
    assert "changed around [100, 70, 110, 80]" in reply
    assert frames.rects[0] == (100, 100, 500, 400)
    desktop.get_state.assert_not_called()


def test_screen_changed_watches_the_whole_screen_by_default(frames):
    frames.queue = [BLANK, _frame((0, 0, 50, 50))]
    _wait_for(_desktop(), condition="screen_changed", interval=0.01)
    assert frames.rects[0] == (0, 0, 1920, 1080)


def test_screen_changed_times_out(frames):
    with pytest.raises(TimeoutError, match="did not change"):
        _wait_for(_desktop(), condition="screen_changed", timeout=0.05, interval=0.01)


def test_screen_idle_waits_until_still_for_the_settle_time(frames):
    frames.queue = [_frame((0, 0, 50, 50)), BLANK, _frame((0, 0, 50, 50)), BLANK]
    reply = _wait_for(_desktop(), condition="screen_idle", settle=0.05, timeout=2, interval=0.01)
    assert "satisfied" in reply and "still for 0.05 seconds" in reply


def test_screen_idle_times_out_while_it_keeps_changing(frames, monkeypatch):
    flip = iter(range(10_000))
    monkeypatch.setattr(
        _screen_wait, "capture", lambda rect: _frame((0, 0, 50, 50)) if next(flip) % 2 else BLANK
    )
    with pytest.raises(TimeoutError, match="kept changing"):
        _wait_for(_desktop(), condition="screen_idle", settle=0.05, timeout=0.2, interval=0.01)


def test_the_default_settle_time_is_one_second(frames):
    with pytest.raises(ValueError, match=r"settle \(1 second\) must be shorter than timeout"):
        _wait_for(_desktop(), condition="screen_idle", timeout=0.5)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ({"condition": "screen_changed", "text": "x"}, "text"),
        ({"condition": "screen_idle", "window_name": "Notepad"}, "region"),
        ({"condition": "screen_changed", "settle": 1}, "settle"),
        ({"condition": "screen_idle", "settle": 0}, "settle"),
        ({"condition": "text_exists", "text": "x", "region": [0, 0, 5, 5]}, "screen_changed"),
    ],
)
def test_arguments_that_do_not_fit_are_refused(frames, args, message):
    with pytest.raises(ValueError, match=message):
        _wait_for(_desktop(), **args)
