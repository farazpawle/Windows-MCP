"""Reply-size cap shared by the tool modules."""

# A 300,000-character PowerShell reply made Claude Code spill it to a file; this keeps
# a reply readable in one piece while still showing plenty of output.
MAX_REPLY_CHARS = 50_000


def cap_text(text: str) -> str:
    """Cut *text* to MAX_REPLY_CHARS characters, saying how many were dropped."""
    if len(text) <= MAX_REPLY_CHARS:
        return text
    dropped = len(text) - MAX_REPLY_CHARS
    return f"{text[:MAX_REPLY_CHARS]}\n... [truncated - {dropped:,} more characters]"
