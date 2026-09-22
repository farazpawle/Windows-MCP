"""Process tool — list and kill running processes."""

from typing import Literal

from mcp.types import ToolAnnotations
from windows_mcp.infrastructure import with_analytics
from fastmcp import Context
from windows_mcp import process
from windows_mcp.tools._args import as_bool
from windows_mcp.tools._output import cap_text


def register(mcp, *, get_desktop, get_analytics):
    @mcp.tool(
        name="Process",
        description='List and kill running processes. Keywords: task manager, running tasks, kill, terminate, stop process, PID, CPU, memory usage. Use mode="list" to list running processes with filtering and sorting options. Use mode="kill" to terminate processes by PID or name.',
        annotations=ToolAnnotations(
            title="Process",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "Process-Tool")
    def process_tool(
        mode: Literal["list", "kill"],
        name: str | None = None,
        pid: int | None = None,
        sort_by: Literal["memory", "cpu", "name"] = "memory",
        limit: int = 20,
        force: bool | str = False,
        ctx: Context = None,
    ) -> str:
        try:
            if mode == "list":
                # 0 listed nothing and a negative number listed everything (list slicing).
                if limit < 1:
                    raise ValueError(f"limit must be at least 1 (got {limit})")
                return cap_text(process.list_processes(name=name, sort_by=sort_by, limit=limit))
            elif mode == "kill":
                force = as_bool(force, "force")
                return process.kill_process(name=name, pid=pid, force=force)
            else:
                return 'Error: mode must be either "list" or "kill".'
        except Exception:
            raise
