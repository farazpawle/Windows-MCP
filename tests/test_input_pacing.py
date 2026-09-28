"""Round-2 2.6: Shortcut repeat is fast; modifier clicks release the keys right after the mouse."""

from unittest.mock import MagicMock, patch

import pytest

import windows_mcp.desktop.service as service
import windows_mcp.uia as uia
from windows_mcp.desktop.service import Desktop


def test_repeat_waits_no_more_than_30ms_per_press():
    send = MagicMock()
    with patch.object(uia, "SendKeys", send):
        Desktop.__new__(Desktop).shortcut("shift+left", repeat=20)

    assert send.call_count == 20
    for call in send.call_args_list:
        assert call.kwargs["waitTime"] <= 0.03


@pytest.mark.parametrize("clicks", [1, 2])
def test_modifier_click_releases_keys_within_100ms_of_mouse_up(clicks):
    # Each entry is (event, seconds waited after it); the sum of waits from the
    # last mouse-up to the last key release is how long Shift stays down alone.
    events = []
    d = Desktop.__new__(Desktop)
    d._require_on_screen = lambda points: None
    with (
        patch.object(uia, "PressKey", lambda code, waitTime: events.append(("down", waitTime))),
        patch.object(uia, "ReleaseKey", lambda code, waitTime: events.append(("up", waitTime))),
        patch.object(uia, "Click", lambda x, y, waitTime=0.5: events.append(("click", waitTime))),
        patch.object(service, "sleep", lambda s: events.append(("sleep", s))),
    ):
        d.click((10, 20), clicks=clicks, modifiers=["shift"])

    last_click = max(i for i, (e, _) in enumerate(events) if e == "click")
    last_up = max(i for i, (e, _) in enumerate(events) if e == "up")
    assert last_up > last_click
    held_after_mouse_up = sum(w for _, w in events[last_click:last_up])
    assert held_after_mouse_up <= 0.1


@pytest.mark.parametrize(
    "action",
    [
        lambda d: d.click((10, 20)),
        lambda d: d.move((10, 20)),
        lambda d: d.scroll((10, 20)),
        lambda d: d.multi_select(True, [(10, 20), (30, 40)]),
        lambda d: d.multi_edit([(10, 20, "hi")]),
        # Round-4 R4-I4: drag kept two 0.5 s waits (1.29 s) and a double click waited
        # half the double-click time between presses (0.48 s).
        lambda d: d.drag((50, 60), from_loc=(10, 20)),
        lambda d: d.click((10, 20), clicks=2),
    ],
    ids=["click", "move", "scroll", "multi_select", "multi_edit", "drag", "double_click"],
)
def test_no_input_waits_more_than_100ms(action):
    # Round-3 R3-I1: a fixed 0.5 s settle made every click/hover/scroll cost ~0.5 s.
    waits = []

    def rec(default):
        return lambda *a, waitTime=default, **k: waits.append(waitTime)

    d = Desktop.__new__(Desktop)
    d._require_on_screen = lambda points: None
    d._finish_clear = lambda: None
    with (
        patch.object(uia, "Click", rec(0.5)),
        patch.object(uia, "DragDrop", rec(0.5)),
        patch.object(uia, "MoveTo", rec(0.5)),
        patch.object(uia, "WheelDown", rec(0.5)),
        patch.object(uia, "PressKey", rec(0.5)),
        patch.object(uia, "ReleaseKey", rec(0.5)),
        patch.object(uia, "SendKeys", rec(0.5)),
        patch.object(service, "sleep", waits.append),
    ):
        action(d)

    assert waits and max(waits) <= 0.1


@pytest.mark.parametrize("direction", ["up", "down"])
def test_scroll_wheel_adds_no_wait_after_the_last_notch(direction):
    # R6-5: the Scroll tool waits for the position to settle itself, so a fixed 0.1 s
    # after the wheel only added time.
    wheel = MagicMock()
    with patch.object(uia, "WheelUp" if direction == "up" else "WheelDown", wheel):
        Desktop.__new__(Desktop)._scroll_wheel("vertical", direction, 3)
    assert wheel.call_args.kwargs["waitTime"] == 0


def test_scroll_moves_the_pointer_without_a_settle_wait():
    # R6-5: the wheel goes to the window under the pointer when it is sent, so the
    # 0.1 s hover settle before it only added time.
    d = Desktop.__new__(Desktop)
    d._require_on_screen = lambda points: None
    with (
        patch.object(uia, "MoveTo") as move,
        patch.object(uia, "WheelDown"),
    ):
        d.scroll((10, 20))
    move.assert_called_once()
    assert move.call_args.args[:2] == (10, 20)
    assert move.call_args.kwargs["waitTime"] == 0


def test_clear_fallback_does_not_wait_half_a_second():
    # Live R3-I2 follow-up: SetValue's default 0.5 s wait made MultiEdit ~0.95 s a field
    # whenever Ctrl+A left text behind.
    pattern = MagicMock(IsReadOnly=False, Value="left over")
    focused = MagicMock()
    focused.GetPattern.return_value = pattern
    with patch.object(uia, "GetFocusedControl", return_value=focused):
        Desktop.__new__(Desktop)._finish_clear()
    pattern.SetValue.assert_called_once()
    assert pattern.SetValue.call_args.kwargs.get("waitTime", 0.5) <= 0.1
