"""Steps tool: several input steps in one call (round-6 R6-9).

Each step is run by calling the registered tool through the server itself, so it keeps
every check the tool has on its own (label re-check, expect=, new-window notes, the
action log). Design: Plan/windows-mcp-r6-9-steps-tool-design.md.
"""

import json
import re

from fastmcp import Context
from fastmcp.exceptions import NotFoundError, ToolError
from fastmcp.exceptions import ValidationError as ArgumentError
from mcp.types import ToolAnnotations
from pydantic import ValidationError

from windows_mcp.infrastructure import with_analytics
from windows_mcp.tools._args import as_bool
from windows_mcp.tools._output import cap_text
from windows_mcp.tools.input import _as_seconds

MAX_STEPS = 20
MAX_WAIT_SECONDS = 60

# Step type -> registered tool name.
_TOOLS = {
    "click": "Click",
    "type": "Type",
    "shortcut": "Shortcut",
    "scroll": "Scroll",
    "move": "Move",
    "wait_for": "WaitFor",
    "wait": "Wait",
}

# Argument -> (default seconds) that holds the run for that long, per tool.
_WAITS = {
    "Wait": ("duration", 0.0),
    "WaitFor": ("timeout", 10.0),
    "Move": ("duration", 0.0),
    "Shortcut": ("hold", 0.0),
}

# Written by @note_new_windows (tools/_new_windows.py) at the end of an input reply.
_NEW_WINDOW_NOTES = (
    "\n\nNote: a new window appeared",
    "\n\nNote: new windows appeared",
    "\n\nNote: a dialog is open",
)


class _Stop(Exception):
    """A step failed or opened an unexpected window; ends the run after that step."""


async def _checked(mcp, step_list: object) -> list[tuple[str, str, dict, bool]]:
    """Every step as (type, tool name, arguments, allow_new_window), or ValueError.

    Checked in full before the first step runs, so a typo in a later step never
    leaves the earlier ones done.
    """
    if isinstance(step_list, str):
        step_list = json.loads(step_list)  # Claude Desktop may send a list as JSON text
    if not isinstance(step_list, list) or not 1 <= len(step_list) <= MAX_STEPS:
        raise ValueError(f"steps must be a list of 1 to {MAX_STEPS} steps.")
    plan, waits = [], 0.0
    for number, step in enumerate(step_list, 1):
        if not isinstance(step, dict):
            raise ValueError(f'Step {number}: each step must be an object like {{"do": "click"}}.')
        args = dict(step)
        kind = args.pop("do", None)
        name = _TOOLS.get(kind)
        if name is None:
            raise ValueError(
                f"Step {number}: do must be one of {', '.join(_TOOLS)} (got {kind!r})."
            )
        allow = as_bool(args.pop("allow_new_window", False), "allow_new_window")
        try:
            tool = await mcp.get_tool(name)
        except NotFoundError:
            tool = None
        if tool is None:  # removed with --exclude-tools / --tools
            raise ValueError(f"Step {number}: {name} is turned off on this server.")
        params = tool.parameters
        known = set(params.get("properties", {})) - {"ctx"}
        if unknown := sorted(set(args) - known):
            raise ValueError(
                f"Step {number}: {name} has no {', '.join(unknown)} "
                f"(it takes {', '.join(sorted(known))})."
            )
        if missing := sorted(set(params.get("required", [])) - set(args)):
            raise ValueError(f"Step {number}: {name} needs {', '.join(missing)}.")
        if name in _WAITS:
            key, default = _WAITS[name]
            value = args.get(key)
            try:
                waits += default if value is None else _as_seconds(value, key)
            except ValueError as e:
                raise ValueError(f"Step {number}: {e}") from None
        plan.append((kind, name, args, allow))
    if waits > MAX_WAIT_SECONDS:
        raise ValueError(
            f"The steps wait {waits:g} s in all (Wait, WaitFor timeouts, Move duration, "
            f"Shortcut hold); at most {MAX_WAIT_SECONDS} s. Split the job into two calls."
        )
    return plan


def _error_text(error: Exception) -> str:
    # A bad argument value comes as FastMCP's ValidationError wrapping pydantic's.
    error = error.__cause__ if isinstance(error.__cause__, ValidationError) else error
    if isinstance(error, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
    return re.sub(r"^Error calling tool '[^']*': ", "", str(error))


def _indented(text: str) -> str:
    return "\n".join(f"   {line}" if line.strip() else "" for line in text.strip().splitlines())[3:]


def register(mcp, *, get_desktop, get_analytics):
    @mcp.tool(
        name="Steps",
        description=(
            "Runs up to 20 input steps in one call, in order: "
            'steps=[{"do": "click", "element": "button:Save"}, {"do": "type", "text": "hi"}]. '
            "do is one of click, type, shortcut, scroll, move, wait_for, wait (the tools "
            "Click, Type, Shortcut, Scroll, Move, WaitFor, Wait); every other key is that "
            "tool's own argument, and each step keeps all of that tool's checks. The whole "
            "list is checked before the first step runs; waits (Wait, WaitFor timeout, Move "
            "duration, Shortcut hold) may add up to 60 s. The run stops at the first step "
            "that fails, or whose reply names a new window or dialog, unless that step has "
            '"allow_new_window": true (use it on a step that opens one on purpose, then '
            "wait_for it). The reply gives each step's own reply, or where the run stopped "
            "and which steps did not run. There is no screenshot mid-run: prefer element= "
            "and wait_for, and put expect= on loc clicks after the first step."
        ),
        annotations=ToolAnnotations(
            title="Steps",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "Steps-Tool")
    async def steps_tool(steps: list | str, ctx: Context = None) -> str:
        plan = await _checked(mcp, steps)
        lines = []
        total = len(plan)
        for number, (kind, name, args, allow) in enumerate(plan, 1):
            try:
                try:
                    result = await mcp.call_tool(name, args)
                except (ToolError, ArgumentError, ValidationError) as e:
                    raise _Stop(_error_text(e)) from None
                text = "\n".join(p.text for p in result.content if hasattr(p, "text"))
                lines.append(f"{number}. {kind}: {_indented(text)}")
                if not allow and any(note in text for note in _NEW_WINDOW_NOTES):
                    raise _Stop(
                        "a new window or dialog appeared (see its note below); later steps "
                        'could go to it. Add "allow_new_window": true to a step that opens '
                        "one on purpose."
                    )
            except _Stop as stop:
                left = f"\nSteps {number + 1}-{total} were not run." if number < total else ""
                done = "\n".join(lines)
                raise ToolError(
                    cap_text(f"Stopped at step {number} of {total}: {stop}{left}\n{done}".strip())
                ) from None
        return cap_text(f"Ran {total} of {total} steps.\n" + "\n".join(lines))
