"""MultiSelect and MultiEdit tools — batch element interaction."""

import json

from mcp.types import ToolAnnotations
from windows_mcp.infrastructure import with_analytics
from fastmcp import Context
from windows_mcp.tools._args import as_bool
from windows_mcp.tools._new_windows import note_new_windows
from windows_mcp.tools._coords import to_model, to_screen
from windows_mcp.tools.input import release_held_button


def _as_loc(value: list | str | None) -> list | None:
    """Coerce a JSON-stringified list back to a list (Claude Desktop workaround)."""
    if value is None or isinstance(value, list):
        return value
    return json.loads(value)


def register(mcp, *, get_desktop, get_analytics):
    @mcp.tool(
        name="MultiSelect",
        description="Selects multiple items such as files, folders, or checkboxes if press_ctrl=True, or performs multiple clicks if False. Pass locs (list of coordinates) or labels (list of UI element labels/ids).",
        annotations=ToolAnnotations(
            title="MultiSelect",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "Multi-Select-Tool")
    @note_new_windows
    def multi_select_tool(
        locs: list[list[int]] | str | None = None,
        labels: list[int] | str | None = None,
        press_ctrl: bool | str = True,
        ctx: Context = None,
    ) -> str:
        desktop = get_desktop()
        locs = _as_loc(locs)
        labels = _as_loc(labels)
        if locs is None and labels is None:
            raise ValueError("Either locs or labels must be provided.")
        locs = [to_screen(desktop, loc) for loc in locs or []]
        if labels is not None and desktop.label_tree_state is None:
            raise ValueError("Desktop state is empty. Please call Snapshot first.")

        press_ctrl = as_bool(press_ctrl, "press_ctrl")
        released = release_held_button(desktop)
        # Labels are resolved one at a time just before each click (R6-2).
        done = desktop.multi_select(press_ctrl, locs, labels or [])
        elements_str = "\n".join("({},{})".format(*to_model(desktop, p[:2])) for p in done)
        action = "Ctrl-selected elements" if press_ctrl else "Clicked in sequence"
        return f"{action} at:\n{elements_str}{released}"

    @mcp.tool(
        name="MultiEdit",
        description="Enters text into multiple input fields at specified coordinates locs=[[x,y,text], ...] or using labels=[[label,text], ...]. Provide either locs or labels.",
        annotations=ToolAnnotations(
            title="MultiEdit",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "Multi-Edit-Tool")
    @note_new_windows
    def multi_edit_tool(
        locs: list[list] | str | None = None,
        labels: list[list] | str | None = None,
        ctx: Context = None,
    ) -> str:
        desktop = get_desktop()
        locs = _as_loc(locs)
        labels = _as_loc(labels)
        if locs is None and labels is None:
            raise ValueError("Either locs or labels must be provided.")
        locs = [to_screen(desktop, loc) for loc in locs or []]
        if labels is not None:
            if desktop.label_tree_state is None:
                raise ValueError("Desktop state is empty. Please call Snapshot first.")

            # Pre-validate and extract labels and texts
            processed_labels = []
            for item in labels:
                if len(item) != 2:
                    raise ValueError(f"Each label item must be [label, text]. Invalid: {item}")
                try:
                    processed_labels.append((int(item[0]), item[1]))
                except ValueError, TypeError:
                    raise ValueError(f"Invalid label id in item: {item}")

            labels = processed_labels

        released = release_held_button(desktop)
        done = desktop.multi_edit(locs, labels or [])
        elements_str = ", ".join(
            "({},{})".format(*to_model(desktop, e[:2])) + f" with text '{e[2]}'" for e in done
        )
        return f"Multi-edited elements at: {elements_str}{released}"
