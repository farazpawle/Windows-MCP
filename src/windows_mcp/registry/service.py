"""
Registry service for the Windows MCP server.
Provides structured operations for reading and writing the Windows Registry
via PowerShell cmdlets.
"""

import json
import logging
import re

from windows_mcp.powershell import PowerShellExecutor
from windows_mcp.powershell.utils import ps_quote
from windows_mcp.registry.views import ALLOWED_REGISTRY_TYPES, RegistryType

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


_HIVES = {
    "HKCU": "HKEY_CURRENT_USER",
    "HKLM": "HKEY_LOCAL_MACHINE",
    "HKCR": "HKEY_CLASSES_ROOT",
    "HKU": "HKEY_USERS",
    "HKCC": "HKEY_CURRENT_CONFIG",
}
_HIVE_PATH = re.compile(r"(?i)(HK[A-Z_]+)(:?)(.*)", re.DOTALL)


def resolve_path(path: str) -> str:
    """Return *path* in a form PowerShell resolves inside the registry.

    Without a hive prefix PowerShell resolves a path against the working folder,
    so the Registry tool would read or delete files. ``HKCU:``/``HKLM:`` drive
    paths are kept; other hives and regedit-style names ("HKLM\\X",
    "HKEY_USERS\\X") become ``Registry::HKEY_...`` provider paths, since only
    HKCU and HKLM exist as PowerShell drives. Raises ValueError otherwise.
    """
    error = ValueError(
        f'"{path}" is not a registry path; nothing was done. Start it with a hive: '
        "HKCU:\\, HKLM:\\, HKCR:\\, HKU:\\, HKCC:\\ or a full name like HKEY_CURRENT_USER\\."
    )
    if path[:10].lower() == "registry::":
        path = path[10:]
    match = _HIVE_PATH.fullmatch(path)
    if not match:
        raise error
    hive, colon, rest = match[1].upper(), match[2], match[3]
    if rest and not rest.startswith("\\"):
        rest = "\\" + rest
    if colon and hive in ("HKCU", "HKLM"):
        return f"{match[1]}:{rest}"
    full = _HIVES.get(hive, hive)
    if full not in _HIVES.values():
        raise error
    return f"Registry::{full}{rest}"


def parse_binary(value: str) -> bytes:
    """Parse a REG_BINARY value.

    Accepts hex bytes separated by commas, spaces or semicolons ("01,02,ff",
    optional 0x prefixes), one unbroken hex string ("0102ff"), or a JSON list
    of decimal byte values ("[1, 2, 255]"). Raises ValueError otherwise.
    """
    text = value.strip()
    if text.startswith("["):
        try:
            items = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid byte list {value!r}: {e}") from None
        if not all(type(i) is int and 0 <= i <= 255 for i in items):
            raise ValueError(f"byte list must hold whole numbers 0-255 (got {value!r})")
        return bytes(items)
    tokens = [t for t in re.split(r"[\s,;]+", text) if t]
    if len(tokens) == 1 and len(tokens[0]) != 2 and not tokens[0].lower().startswith("0x"):
        token = tokens[0]
        if len(token) % 2:
            raise ValueError(f"hex string needs an even number of digits (got {value!r})")
        tokens = [token[i : i + 2] for i in range(0, len(token), 2)]
    try:
        data = [int(t, 16) for t in tokens]
    except ValueError:
        raise ValueError(f"not a hex byte list: {value!r}") from None
    if any(b > 255 or b < 0 for b in data):
        raise ValueError(f"each byte must be 00-ff (got {value!r})")
    return bytes(data)


def get_value(path: str, name: str) -> str:
    """Read a registry value at *path* with the given *name*."""
    q_path = ps_quote(path)
    q_name = ps_quote(name)
    command = f"Get-ItemProperty -LiteralPath {q_path} -Name {q_name} | Select-Object -ExpandProperty {q_name}"
    response, status = PowerShellExecutor.execute_command(command)
    if status != 0:
        return f"Error reading registry: {response.strip()}"
    return f'Registry value [{path}] "{name}" = {response.strip()}'


def set_value(path: str, name: str, value: str, reg_type: RegistryType = "String") -> str:
    """Create or update a registry value, creating the key if it does not exist."""
    if reg_type not in ALLOWED_REGISTRY_TYPES:
        return (
            f"Error: invalid registry type '{reg_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_REGISTRY_TYPES))}"
        )
    q_path = ps_quote(path)
    q_name = ps_quote(name)
    if reg_type == "Binary":
        try:
            data = parse_binary(value)
        except ValueError as e:
            return f"Error: invalid binary value: {e}"
        # A quoted string would be stored as a single byte; build a real byte array.
        q_value = f"([byte[]]({','.join(map(str, data))}))" if data else "([byte[]]@())"
    else:
        q_value = ps_quote(value)
    command = (
        f"if (-not (Test-Path -LiteralPath {q_path})) {{ New-Item -Path {q_path} -Force | Out-Null }}; "
        f"Set-ItemProperty -LiteralPath {q_path} -Name {q_name} -Value {q_value} -Type {reg_type} -Force"
    )
    response, status = PowerShellExecutor.execute_command(command)
    if status != 0:
        return f"Error writing registry: {response.strip()}"
    return f'Registry value [{path}] "{name}" set to "{value}" (type: {reg_type}).'


def delete_entry(path: str, name: str | None = None, recursive: bool = False) -> str:
    """Delete a registry value when *name* is provided, otherwise remove the key.

    A key that has sub-keys is only removed with recursive=True, so a missing
    ``name`` can no longer wipe a whole tree by accident. Paths holding ``*`` or
    ``?`` are refused: a wildcard delete could wipe many keys at once.
    """
    if "*" in path or "?" in path:
        return (
            f"Error: Registry path [{path}] contains a wildcard (* or ?); nothing was deleted. "
            "Give the exact key path."
        )
    q_path = ps_quote(path)
    if name:
        q_name = ps_quote(name)
        command = f"Remove-ItemProperty -LiteralPath {q_path} -Name {q_name} -Force"
        response, status = PowerShellExecutor.execute_command(command)
        if status != 0:
            return f"Error deleting registry value: {response.strip()}"
        return f'Registry value [{path}] "{name}" deleted.'
    if recursive:
        command = f"Remove-Item -LiteralPath {q_path} -Recurse -Force"
    else:
        command = (
            f"$n = @(Get-ChildItem -LiteralPath {q_path} -ErrorAction Stop).Count; "
            f'if ($n -gt 0) {{ Write-Output "HAS_SUBKEYS:$n"; exit 2 }}; '
            f"Remove-Item -LiteralPath {q_path} -Force -ErrorAction Stop"
        )
    response, status = PowerShellExecutor.execute_command(command)
    if status == 2 and response.strip().startswith("HAS_SUBKEYS:"):
        count = response.strip().split(":", 1)[1]
        return (
            f"Error: Registry key [{path}] has {count} sub-key(s); nothing was deleted. "
            "Pass recursive=true to delete the key with all its sub-keys."
        )
    if status != 0:
        return f"Error deleting registry key: {response.strip()}"
    return f"Registry key [{path}] deleted."


def list_key(path: str) -> str:
    """List values and sub-keys under *path*."""
    q_path = ps_quote(path)
    command = (
        f"$values = (Get-ItemProperty -LiteralPath {q_path} -ErrorAction Stop | "
        f"Select-Object * -ExcludeProperty PS* | Format-List | Out-String).Trim(); "
        f"$subkeys = (Get-ChildItem -LiteralPath {q_path} -ErrorAction SilentlyContinue | "
        f'Select-Object -ExpandProperty PSChildName) -join "`n"; '
        f'if ($values) {{ Write-Output "Values:`n$values" }}; '
        f'if ($subkeys) {{ Write-Output "`nSub-Keys:`n$subkeys" }}; '
        f"if (-not $values -and -not $subkeys) {{ Write-Output 'No values or sub-keys found.' }}"
    )
    response, status = PowerShellExecutor.execute_command(command)
    if status != 0:
        return f"Error listing registry: {response.strip()}"
    return f"Registry key [{path}]:\n{response.strip()}"
