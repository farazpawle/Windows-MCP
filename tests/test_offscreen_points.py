"""Round-2 1.4: points outside every display are refused before any input is sent."""

from unittest.mock import MagicMock, patch

import pytest

import windows_mcp.uia as uia
from windows_mcp.desktop.service import Desktop

OFF_SCREEN = [(-50, 99999), (1920, 0), (0, 1080)]
ON_SCREEN = [(0, 0), (1919, 1079)]

# Every uia call that sends mouse or keyboard input from the paths under test.
_INPUT_CALLS = (
    "Click",
    "RightClick",
    "MiddleClick",
    "SetCursorPos",
    "MoveTo",
    "PressMouse",
    "ReleaseMouse",
    "DragDrop",
    "SendKeys",
    "PressKey",
    "ReleaseKey",
    "WheelDown",
)


@pytest.fixture
def desktop():
    d = Desktop.__new__(Desktop)
    display = MagicMock()
    display.rect = uia.Rect(0, 0, 1920, 1080)
    d.get_displays = MagicMock(return_value=[display])
    return d


@pytest.fixture
def sent():
    mocks = {name: MagicMock() for name in _INPUT_CALLS}
    with patch.multiple(uia, **mocks):
        yield mocks


def _nothing_sent(sent) -> bool:
    return not any(m.called for m in sent.values())


@pytest.mark.parametrize("point", OFF_SCREEN)
@pytest.mark.parametrize(
    "action",
    [
        lambda d, p: d.click(list(p)),
        lambda d, p: d.click(list(p), clicks=0),
        lambda d, p: d.type(p, text="x"),
        lambda d, p: d.scroll(p),
        lambda d, p: d.move(p),
        lambda d, p: d.mouse_button(p, "down"),
        lambda d, p: d.drag(p, from_loc=(5, 5)),
        lambda d, p: d.drag((5, 5), from_loc=p),
        lambda d, p: d.multi_select(False, [(5, 5), p]),
        lambda d, p: d.multi_edit([(5, 5, "a"), (*p, "b")]),
    ],
)
def test_off_screen_point_is_refused_without_input(desktop, sent, point, action):
    with pytest.raises(ValueError, match="outside every display"):
        action(desktop, point)
    assert _nothing_sent(sent)


@pytest.mark.parametrize("point", ON_SCREEN)
def test_edge_points_are_accepted(desktop, sent, point):
    desktop.click(list(point))
    sent["Click"].assert_called_once_with(*point)


def test_gap_between_displays_is_refused(desktop, sent):
    left, right = MagicMock(), MagicMock()
    left.rect = uia.Rect(0, 0, 1920, 1080)
    right.rect = uia.Rect(1920, 0, 3840, 720)  # shorter screen: (2000, 900) is in no display
    desktop.get_displays.return_value = [left, right]
    with pytest.raises(ValueError, match="outside every display"):
        desktop.click([2000, 900])
    desktop.click([2000, 700])
    sent["Click"].assert_called_once_with(2000, 700)


def test_multi_edit_names_every_bad_target(desktop, sent):
    with pytest.raises(ValueError) as err:
        desktop.multi_edit([(253, 391, "A"), (99999, 99999, "lost"), (-1, 5, "x")])
    message = str(err.value)
    assert "target 2 (99999,99999)" in message
    assert "target 3 (-1,5)" in message
    assert "target 1" not in message
    assert _nothing_sent(sent)


def test_multi_edit_failure_reports_done_and_not_done(desktop, sent):
    desktop.type = MagicMock(side_effect=[None, RuntimeError("boom"), None])
    with pytest.raises(RuntimeError) as err:
        desktop.multi_edit([(10, 10, "A"), (20, 20, "B"), (30, 30, "C")])
    message = str(err.value)
    assert "(20,20)" in message and "boom" in message
    assert "done: (10,10)" in message
    assert "not done: (20,20), (30,30)" in message
    assert desktop.type.call_count == 2
