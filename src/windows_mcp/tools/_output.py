"""Reply helpers shared by the tool modules: size cap and error replies."""

from functools import wraps

from fastmcp.exceptions import ToolError

# A 300,000-character PowerShell reply made Claude Code spill it to a file; this keeps
# a reply readable in one piece while still showing plenty of output.
MAX_REPLY_CHARS = 50_000


def cap_text(text: str) -> str:
    """Cut *text* to MAX_REPLY_CHARS characters, saying how many were dropped."""
    if len(text) <= MAX_REPLY_CHARS:
        return text
    dropped = len(text) - MAX_REPLY_CHARS
    return f"{text[:MAX_REPLY_CHARS]}\n... [truncated - {dropped:,} more characters]"


def raise_error_replies(func):
    """Raise an "Error..." reply of *func* as a tool error.

    The services report expected failures as text starting with "Error"; returned
    as-is, FastMCP sends them as successful results (is_error=False). Apply directly
    on the tool function, inside @with_analytics.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        reply = func(*args, **kwargs)
        if isinstance(reply, str) and reply.startswith("Error"):
            raise ToolError(reply)
        return reply

    return wrapper
