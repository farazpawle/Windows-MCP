"""Round-2 3.18: Screenshot region text form and use_annotation refusal."""

import asyncio
from unittest.mock import MagicMock

import pytest

from windows_mcp.tools._snapshot_helpers import _as_region
from windows_mcp.tools.snapshot import register


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("100,100,300,200", [100, 100, 300, 200]),
        (" 100, 100 ,300,200 ", [100, 100, 300, 200]),
        ("[100, 100, 300, 200]", [100, 100, 300, 200]),
        ([1, 2, 3, 4], [1, 2, 3, 4]),
        (None, None),
        ("", None),
    ],
)
def test_region_forms(value, expected):
    assert _as_region(value) == expected


@pytest.mark.parametrize("value", ["a,b,c,d", "100 100 300 200", "[1, 2"])
def test_region_text_that_is_not_numbers_is_refused(value):
    with pytest.raises(ValueError, match="left, top, right, bottom"):
        _as_region(value)


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def test_screenshot_refuses_use_annotation():
    # Screenshot skips the UI tree, so there are no element boxes to draw.
    mcp = FakeMCP()
    desktop = MagicMock()
    register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)

    with pytest.raises(ValueError, match="use_annotation.*Snapshot"):
        asyncio.run(mcp.tools["Screenshot"](use_annotation=True))
    desktop.get_state.assert_not_called()


@pytest.mark.parametrize("tool", ["Screenshot", "Snapshot"])
def test_bad_option_is_not_told_to_try_again(tool):
    # Retrying the same bad region cannot help, so the reply must not suggest it.
    mcp = FakeMCP()
    register(mcp, get_desktop=MagicMock, get_analytics=lambda: None)

    with pytest.raises(Exception, match="region must be") as caught:
        asyncio.run(mcp.tools[tool](region="a,b,c,d"))
    assert "try again" not in str(caught.value)


@pytest.mark.parametrize("tool", ["Screenshot", "Snapshot"])
def test_capture_failure_still_suggests_retry(tool):
    mcp = FakeMCP()
    desktop = MagicMock()
    desktop.get_state.side_effect = RuntimeError("capture backend hiccup")
    register(mcp, get_desktop=lambda: desktop, get_analytics=lambda: None)

    with pytest.raises(Exception, match="Please try again"):
        asyncio.run(mcp.tools[tool]())
