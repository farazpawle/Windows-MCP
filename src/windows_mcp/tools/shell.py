"""PowerShell tool — shell/command execution."""

from mcp.types import ToolAnnotations
from windows_mcp.infrastructure import with_analytics
from windows_mcp.powershell import PowerShellExecutor
from windows_mcp.tools._output import cap_text
from fastmcp import Context
from fastmcp.exceptions import ToolError


def register(mcp, *, get_desktop, get_analytics):
    @mcp.tool(
        name="PowerShell",
        description="Shell/command execution. Keywords: shell, run, execute, cmd, terminal, command line, script. A comprehensive system tool for executing any PowerShell commands. Use it to navigate the file system, manage files and processes, and execute system-level operations. Capable of accessing web content (e.g., via Invoke-WebRequest), interacting with network resources, and performing complex administrative tasks. This tool provides full access to the underlying operating system capabilities, making it the primary interface for system automation, scripting, and deep system interaction. A non-zero exit code or a timeout is reported as an error, with the output included. For commands that use other exit codes for success, list them in success_exit_codes: e.g. [0, 1] for findstr (1 = no match), [0, 1, 2, 3, 4, 5, 6, 7] for robocopy.",
        annotations=ToolAnnotations(
            title="PowerShell",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    @with_analytics(get_analytics(), "Powershell-Tool")
    def powershell_tool(
        command: str,
        timeout: int = 30,
        success_exit_codes: list[int] | None = None,
        ctx: Context = None,
    ) -> str:
        # 0 would time out every command; "no timeout" is not offered because a
        # stuck command would then block the server forever.
        if timeout < 1:
            raise ValueError(f"timeout must be at least 1 second (got {timeout})")
        # An empty command ran and replied "Response: " as if it had done something.
        if not command.strip():
            raise ValueError("command is empty")
        response, status_code = PowerShellExecutor.execute_command(
            command, timeout, include_errors=True
        )
        reply = f"Response: {cap_text(response)}\nStatus Code: {status_code}"
        # Raised so the client sees is_error=True; returned, a failure looked like success.
        # A timeout is never a success, whatever codes were listed.
        if status_code == PowerShellExecutor.NOT_RUN or status_code not in (
            success_exit_codes or [0]
        ):
            raise ToolError(reply)
        return reply
