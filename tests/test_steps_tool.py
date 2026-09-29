"""Round-6 R6-9: Steps runs several input steps in one call through the server's own tools."""

import asyncio

import pytest
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from windows_mcp.__main__ import _apply_tool_filter
from windows_mcp.infrastructure import action_log
from windows_mcp.infrastructure.analytics import with_analytics
from windows_mcp.tools import steps

NEW_WINDOW = '\n\nNote: a new window appeared: "Save As" (handle=5, pid=6 notepad.exe).'
DIALOG = '\n\nNote: a dialog is open: "Notepad" in "a.txt - Notepad".'


def _server(fail: str | None = None, note: str = "", exclude: str | None = None):
    """A server with stand-in input tools that record their calls, plus Steps."""
    mcp, calls = FastMCP("t"), []

    @mcp.tool(name="Click")
    @with_analytics(None, "Click-Tool")
    def click(loc: list[int] | None = None, expect: str | None = None, ctx: Context = None):
        calls.append(("Click", loc))
        if fail == "Click":
            raise ValueError("found pane in Popup, not Save")
        return f"Single left clicked at ({loc[0]},{loc[1]})."

    @mcp.tool(name="Type")
    def type_(text: str, press_enter: bool = False, ctx: Context = None):
        calls.append(("Type", text))
        return f"Typed {text!r} into the focused element."

    @mcp.tool(name="Shortcut")
    def shortcut(shortcut: str | None = None, hold: float | None = None, ctx: Context = None):
        calls.append(("Shortcut", shortcut))
        return f"Pressed {shortcut}.{note}"

    @mcp.tool(name="WaitFor")
    def wait_for(condition: str, text: str | None = None, timeout: float = 10.0, ctx=None):
        calls.append(("WaitFor", text))
        if fail == "WaitFor":
            raise TimeoutError(f"Timed out after {timeout:.2f}s waiting for '{condition}'.")
        return f"WaitFor condition '{condition}' satisfied."

    @mcp.tool(name="Wait")
    def wait(duration: float, ctx: Context = None):
        calls.append(("Wait", duration))
        return f"Waited for {duration} s."

    @mcp.tool(name="Scroll")
    def scroll(direction: str = "down", ctx: Context = None):
        return "Scrolled."

    @mcp.tool(name="Move")
    def move(loc: list[int], duration: float | None = None, ctx: Context = None):
        return "Moved."

    steps.register(mcp, get_desktop=lambda: None, get_analytics=lambda: None)
    if exclude:
        _apply_tool_filter(mcp, None, [exclude])
    return mcp, calls


def _run(mcp, step_list):
    result = asyncio.run(mcp.call_tool("Steps", {"steps": step_list}))
    return "\n".join(part.text for part in result.content)


SAVE_AS = [
    {"do": "shortcut", "shortcut": "ctrl+shift+s", "allow_new_window": True},
    {"do": "wait_for", "condition": "active_window", "text": "Save As", "timeout": 5},
    {"do": "type", "text": "week39.txt", "press_enter": True},
    {"do": "wait_for", "condition": "active_window", "text": "week39.txt", "timeout": 5},
]


# d. bad lists are refused, naming the step, before anything runs
@pytest.mark.parametrize(
    ("step_list", "message"),
    [
        ([{"do": "click", "loc": [1, 2]}, {"do": "fly"}], "Step 2: do must be one of"),
        ([{"do": "click", "loc": [1, 2]}, {"do": "type", "txt": "x"}], "Step 2: Type has no txt"),
        ([{"do": "click", "loc": [1, 2]}, {"do": "type"}], "Step 2: Type needs text"),
        ([{"loc": [1, 2]}], "Step 1: do must be one of"),
        (["click"], "Step 1: each step must be an object"),
        ([{"do": "steps"}], "Step 1: do must be one of"),
        ([], "1 to 20 steps"),
        ([{"do": "wait", "duration": 0.1}] * 21, "1 to 20 steps"),
        (
            [{"do": "wait", "duration": 30}, {"do": "wait_for", "condition": "x"}] * 2,
            "at most 60 s",
        ),
        ([{"do": "wait", "duration": "soon"}], "Step 1: duration must be a number"),
    ],
)
def test_bad_lists_are_refused_before_anything_runs(step_list, message):
    mcp, calls = _server()
    with pytest.raises(ToolError, match=message):
        _run(mcp, step_list)
    assert calls == []


def test_move_duration_and_shortcut_hold_count_as_waits():
    mcp, calls = _server()
    long = [{"do": "move", "loc": [1, 2], "duration": 40}, {"do": "shortcut", "hold": 25}]
    with pytest.raises(ToolError, match="at most 60 s"):
        _run(mcp, long)


def test_steps_given_as_json_text_are_accepted():
    # Claude Desktop sometimes sends a list argument as JSON text.
    mcp, calls = _server()
    result = asyncio.run(mcp.call_tool("Steps", {"steps": '[{"do": "wait", "duration": 0}]'}))
    assert "Ran 1 of 1 steps." in result.content[0].text


# e. steps run in order, one numbered line each
def test_steps_run_in_order_with_their_own_arguments():
    mcp, calls = _server(note=NEW_WINDOW)
    reply = _run(mcp, SAVE_AS)
    assert calls == [
        ("Shortcut", "ctrl+shift+s"),
        ("WaitFor", "Save As"),
        ("Type", "week39.txt"),
        ("WaitFor", "week39.txt"),
    ]
    lines = reply.splitlines()
    assert lines[0] == "Ran 4 of 4 steps."
    assert lines[1].startswith("1. shortcut: Pressed ctrl+shift+s.")
    assert "Save As" in reply  # the note of step 1 is kept
    assert "4. wait_for: WaitFor condition 'active_window' satisfied." in reply


# f. a failing step stops the run
def test_a_failing_step_stops_the_run_and_says_what_ran():
    mcp, calls = _server(fail="WaitFor", note=NEW_WINDOW)
    with pytest.raises(ToolError) as error:
        _run(mcp, SAVE_AS)
    text = str(error.value)
    assert text.startswith("Stopped at step 2 of 4: Timed out after 5.00s")
    assert "Error calling tool" not in text
    assert "1. shortcut: Pressed ctrl+shift+s." in text
    assert "Steps 3-4 were not run." in text
    assert [c[0] for c in calls] == ["Shortcut", "WaitFor"]


def test_a_failing_last_step_says_nothing_was_left():
    mcp, _ = _server(fail="Click")
    with pytest.raises(ToolError) as error:
        _run(mcp, [{"do": "wait", "duration": 0}, {"do": "click", "loc": [1, 2], "expect": "Save"}])
    text = str(error.value)
    assert "Stopped at step 2 of 2: found pane in Popup, not Save" in text
    assert "not run" not in text


def test_a_bad_value_found_at_run_time_stops_the_run():
    mcp, calls = _server()
    with pytest.raises(ToolError, match="Stopped at step 2 of 2"):
        _run(mcp, [{"do": "wait", "duration": 0}, {"do": "click", "loc": "not a point"}])
    assert calls == [("Wait", 0)]


# g. an unexpected window or dialog stops the run
@pytest.mark.parametrize("note", [NEW_WINDOW, DIALOG])
def test_an_unallowed_new_window_or_dialog_stops_the_run(note):
    mcp, calls = _server(note=note)
    step_list = [{"do": "shortcut", "shortcut": "ctrl+w"}, {"do": "type", "text": "x"}]
    with pytest.raises(ToolError) as error:
        _run(mcp, step_list)
    text = str(error.value)
    assert text.startswith("Stopped at step 1 of 2: a new window or dialog appeared")
    assert note.strip() in text
    assert ("Type", "x") not in calls


def test_allow_new_window_lets_the_run_continue():
    mcp, calls = _server(note=DIALOG)
    step_list = [
        {"do": "shortcut", "shortcut": "ctrl+w", "allow_new_window": "true"},
        {"do": "type", "text": "x"},
    ]
    assert _run(mcp, step_list).startswith("Ran 2 of 2 steps.")


# h. an excluded tool is refused before the run
def test_a_step_whose_tool_is_excluded_is_refused_before_the_run():
    mcp, calls = _server(exclude="Type")
    with pytest.raises(ToolError, match="Step 2: Type is turned off on this server"):
        _run(mcp, [{"do": "wait", "duration": 0}, {"do": "type", "text": "x"}])
    assert calls == []


# i. one action-log line per step plus the Steps line
def test_the_action_log_has_a_line_per_step(tmp_path):
    path = tmp_path / "actions.log"
    action_log.configure(str(path))
    try:
        mcp, _ = _server()
        _run(mcp, [{"do": "click", "loc": [1, 2]}, {"do": "click", "loc": [3, 4]}])
    finally:
        action_log.configure(None)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [line.split()[2] for line in lines] == ["Click", "Click", "Steps"]
