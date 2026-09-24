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
        patch.object(uia, "GetDoubleClickTime", return_value=500),
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
    ],
    ids=["click", "move", "scroll", "multi_select", "multi_edit"],
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
        patch.object(uia, "MoveTo", rec(0.5)),
        patch.object(uia, "WheelDown", rec(0.5)),
        patch.object(uia, "PressKey", rec(0.5)),
        patch.object(uia, "ReleaseKey", rec(0.5)),
        patch.object(uia, "SendKeys", rec(0.5)),
        patch.object(uia, "GetDoubleClickTime", return_value=500),
        patch.object(service, "sleep", waits.append),
    ):
        action(d)

    assert waits and max(waits) <= 0.1
