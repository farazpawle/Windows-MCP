"""Round-2 2.5: every button's multi-click lands inside the double-click time."""

from unittest.mock import MagicMock, patch

import pytest

import windows_mcp.uia as uia
from windows_mcp.desktop.service import Desktop

_PRESS = {"left": "Click", "right": "RightClick", "middle": "MiddleClick"}


@pytest.mark.parametrize("button", _PRESS)
@pytest.mark.parametrize("clicks", [2, 3])
def test_multi_click_gap_is_half_the_double_click_time(button, clicks):
    press = MagicMock()
    with (
        patch.object(uia, _PRESS[button], press),
        patch.object(uia, "GetDoubleClickTime", return_value=500),
    ):
        Desktop.__new__(Desktop)._click_button(10, 20, button, clicks)

    waits = [c.kwargs["waitTime"] for c in press.call_args_list]
    # The last press settles in click(), after the modifiers are released (2.6).
    assert waits == [0.25] * (clicks - 1) + [0]
