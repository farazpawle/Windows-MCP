"""Opt-in action log (round-2 C.8): one readable line per tool call, secrets hidden.

The server has full system access and no rollback; this lets a person see afterwards
exactly what an agent did. Off unless ``serve --action-log`` / WINDOWS_MCP_ACTION_LOG
is set. Written at the tool boundary by ``with_analytics``, so every tool is covered.
"""

import json
import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from windows_mcp.infrastructure.config import CONFIG_DIR

logger = logging.getLogger(__name__)

DEFAULT_PATH = CONFIG_DIR / "actions.log"
_ON = {"1", "true", "yes", "on"}
_OFF = {"", "0", "false", "no", "off"}
_REPLY_CHARS = 300
_ARG_CHARS = 200
HIDDEN = "[hidden]"

# with_analytics labels that differ from the registered tool names. The labels are the
# telemetry event names, so they stay; the log shows the name the caller used.
_TOOL_NAMES = {
    "Powershell": "PowerShell",
    "State": "Snapshot",
    "Multi-Edit": "MultiEdit",
    "Multi-Select": "MultiSelect",
}

# Argument names whose value is always hidden.
_SECRET_NAMES = ("password", "passwd", "secret", "token", "api_key", "apikey", "auth", "credential")

# Secret shapes inside any text (arguments and replies).
_VALUE = r"(\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
_PATTERNS = [
    # PowerShell parameters: -Password hunter2
    (
        re.compile(
            r"(?i)(-(?:password|passwd|pass|token|secret|api_?key|key|credential|cred)\s+)" + _VALUE
        ),
        rf"\1{HIDDEN}",
    ),
    # HTTP credentials: Bearer abc.def
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+"), rf"\1 {HIDDEN}"),
    # password=..., "api_key": "..."
    (
        re.compile(
            r"(?i)((?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
            r"client[_-]?secret)[\"']?\s*[=:]\s*)" + _VALUE
        ),
        rf"\1{HIDDEN}",
    ),
    # Well-known key prefixes (OpenAI/Anthropic, GitHub, Slack, AWS).
    (re.compile(r"\b(?:sk-|ghp_|gho_|ghu_|github_pat_|xox[abprs]-|AKIA)[A-Za-z0-9_-]{8,}"), HIDDEN),
    # ponytail: long random-looking tokens (32+ chars with upper, lower and digits). GUIDs and
    # hashes are single-case so they stay; a secret that is all one case slips through.
    (
        re.compile(
            r"(?<![A-Za-z0-9+/_=-])(?=[A-Za-z0-9+/_=-]*[a-z])(?=[A-Za-z0-9+/_=-]*[A-Z])"
            r"(?=[A-Za-z0-9+/_=-]*\d)[A-Za-z0-9+/_=-]{32,}"
        ),
        HIDDEN,
    ),
]

_lock = threading.Lock()
_path: Path | None = None


def configure(value: str | None) -> Path | None:
    """Turn the log on ("on" = the settings folder, or a file path) or off; the path used."""
    global _path
    text = (value or "").strip()
    if text.lower() in _OFF:
        _path = None
        return None
    path = DEFAULT_PATH if text.lower() in _ON else Path(text).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    _path = path
    return path


def redact(text: str) -> str:
    """Hide secret-looking values in *text*."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _redacted(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: _redacted(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redacted(v) for v in value]
    return value


def tool_name(label: str) -> str:
    """The registered tool name for a with_analytics label ("Powershell-Tool" -> "PowerShell")."""
    name = label.removesuffix("-Tool")
    return _TOOL_NAMES.get(name, name)


def _quoted(text: str) -> str:
    # Not JSON: a person reads paths, and JSON doubles every backslash.
    return '"' + text.replace('"', '\\"').replace("\r", "").replace("\n", "\\n") + '"'


def _argument(name: str, value: Any) -> str:
    if any(secret in name.lower() for secret in _SECRET_NAMES):
        return f"{name}={HIDDEN}"
    value = _redacted(value)
    if isinstance(value, str):
        if len(value) > _ARG_CHARS:
            return f'{name}={_quoted(value[:_ARG_CHARS])[:-1]}..." ({len(value)} characters)'
        return f"{name}={_quoted(value)}"
    shown = json.dumps(value, ensure_ascii=False, default=str)
    if len(shown) > _ARG_CHARS:
        shown = f"{shown[:_ARG_CHARS]}... ({len(shown)} characters)"
    return f"{name}={shown}"


def _reply_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    items = result if isinstance(result, (list, tuple)) else [result]
    parts = []
    for item in items:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, (dict, list, int, float, bool)) or item is None:
            parts.append(json.dumps(item, ensure_ascii=False, default=str))
        else:
            parts.append(f"[{type(item).__name__}]")
    return " ".join(parts)


def record(tool: str, arguments: dict[str, Any], ok: bool, result: Any, seconds: float) -> None:
    """Append one line for a finished tool call; does nothing while the log is off."""
    path = _path
    if path is None:
        return
    shown = " ".join(
        _argument(name, value)
        for name, value in arguments.items()
        if value is not None and name != "ctx"
    )
    text = _reply_text(result)
    size = len(text)
    reply = re.sub(r"\s*\n\s*", " | ", redact(text)).strip()
    if len(reply) > _REPLY_CHARS:
        reply = f"{reply[:_REPLY_CHARS]}... ({size} characters)"
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {tool}"
    if shown:
        line += f"  {shown}"
    line += f"  -> {'ok' if ok else 'error'} {seconds:.2f}s" + (f": {reply}" if reply else "")
    try:
        with _lock, path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
    except OSError:
        # A full disk or a locked file must not fail the tool call itself.
        logger.warning("Could not write the action log %s", path, exc_info=True)
