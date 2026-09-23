"""Round-2 3.13: Type's reply shortens long text and says what else it did."""

import asyncio
from unittest.mock import MagicMock

import pytest

from windows_mcp.tools import input as input_tool_module


def _type(**kwargs) -> str:
    tools = {}

    class FakeMCP:
        def tool(self, *, name, **_):
            return lambda func: tools.setdefault(name, func)

    desktop = MagicMock()
    desktop.release_held_button.return_value = False
    desktop.describe_focused_element.return_value = None
    input_tool_module.register(FakeMCP(), get_desktop=lambda: desktop, get_analytics=lambda: None)
    return asyncio.run(tools["Type"](**kwargs))


LONG = "x" * 1_047 + "y" * 50  # 1,097 characters


def test_long_text_reply_gives_length_and_a_preview_plus_clear_and_enter():
    reply = _type(text=LONG, loc=[5, 6], clear=True, press_enter=True)
    assert reply == (
        f'Typed 1,097 characters ("{"x" * 50}...") at (5,6). '
        "Cleared the existing text first. Pressed Enter."
    )


def test_long_text_into_the_focused_element_is_shortened_too():
    reply = _type(text=LONG)
    assert reply == f'Typed 1,097 characters ("{"x" * 50}...") into the focused element.'


@pytest.mark.parametrize("text", ["abc", "z" * 50])
def test_short_text_is_echoed_whole(text):
    assert _type(text=text, loc=[1, 2]) == f"Typed {text} at (1,2)."


def test_enter_alone_is_reported():
    assert _type(text="abc", press_enter=True) == (
        "Typed abc into the focused element. Pressed Enter."
    )


def test_clear_given_as_text_true_is_reported():
    assert _type(text="abc", loc=[1, 2], clear="true") == (
        "Typed abc at (1,2). Cleared the existing text first."
    )
