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


def parse_number(value: str, reg_type: str) -> int:
    """Parse a DWord/QWord value: decimal or hex with a 0x prefix.

    An empty value used to be stored as 0 while the reply claimed "" was set,
    so it is refused here. Raises ValueError for anything that is not a number.
    """
    text = value.strip()
    if not text:
        raise ValueError(f"{reg_type} needs a number; got an empty value")
    digits = text[1:] if text[:1] in "+-" else text
    base = 16 if digits[:2].lower() == "0x" else 10
    try:
        number = int(digits[2:] if base == 16 else digits, base)
    except ValueError:
        raise ValueError(
            f"{reg_type} needs a whole number, decimal or 0x-prefixed hex (got {value!r})"
        ) from None
    return -number if text.startswith("-") else number


def parse_multistring(value: str) -> list[str]:
    """Parse a MultiString value: a JSON list of strings, or one plain string."""
    text = value.strip()
    if not text.startswith("["):
        return [value]
    try:
        items = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid string list {value!r}: {e}") from None
    if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
        raise ValueError(f"MultiString list must hold text items (got {value!r})")
    return items


def _is_default(name: str) -> bool:
    """An empty name or "(Default)" means the key's unnamed default value."""
    return name == "" or name.lower() == "(default)"


def _value_name(name: str) -> tuple[str, str]:
    """(name for PowerShell, name for the reply).

    PowerShell refuses -Name '' but maps '(default)' to the unnamed value.
    """
    return ("(default)", "(Default)") if _is_default(name) else (name, name)


# PowerShell expression showing $v in the shape set accepts: hex bytes, a JSON string list.
# Shared by get and list so both show a value the same way (R3-9).
_FORMAT_VALUE = (
    "$(if ($v -is [byte[]]) { ($v | ForEach-Object { $_.ToString('x2') }) -join ',' } "
    "elseif ($v -is [string[]]) { ConvertTo-Json -Compress -InputObject @($v) } "
    "else { $v })"
)


def get_value(path: str, name: str) -> str:
    """Read a registry value at *path* with the given *name*."""
    name, shown_name = _value_name(name)
    q_path = ps_quote(path)
    q_name = ps_quote(name)
    command = (
        # Property access, not -ExpandProperty: the latter unrolls a byte array
        # into loose objects, losing the type this formatting depends on.
        f"$v = (Get-ItemProperty -LiteralPath {q_path} -Name {q_name} -ErrorAction Stop).{q_name}; "
        f"{_FORMAT_VALUE}"
    )
    response, status = PowerShellExecutor.execute_command(command)
    if status != 0:
        return f"Error reading registry: {response.strip()}"
    return f'Registry value [{path}] "{shown_name}" = {response.strip()}'


def set_value(path: str, name: str, value: str, reg_type: RegistryType = "String") -> str:
    """Create or update a registry value, creating the key if it does not exist."""
    if reg_type not in ALLOWED_REGISTRY_TYPES:
        return (
            f"Error: invalid registry type '{reg_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_REGISTRY_TYPES))}"
        )
    name, shown_name = _value_name(name)
    q_path = ps_quote(path)
    q_name = ps_quote(name)
    shown = value
    if reg_type == "Binary":
        try:
            data = parse_binary(value)
        except ValueError as e:
            return f"Error: invalid binary value: {e}"
        # A quoted string would be stored as a single byte; build a real byte array.
        q_value = f"([byte[]]({','.join(map(str, data))}))" if data else "([byte[]]@())"
    elif reg_type in ("DWord", "QWord"):
        try:
            number = parse_number(value, reg_type)
        except ValueError as e:
            return f"Error: invalid {reg_type} value: {e}"
        q_value = shown = str(number)
    elif reg_type == "MultiString":
        try:
            items = parse_multistring(value)
        except ValueError as e:
            return f"Error: invalid MultiString value: {e}"
        q_value = f"@({','.join(map(ps_quote, items))})"
    else:
        q_value = ps_quote(value)
    command = (
        f"if (-not (Test-Path -LiteralPath {q_path})) {{ New-Item -Path {q_path} -Force | Out-Null }}; "
        f"Set-ItemProperty -LiteralPath {q_path} -Name {q_name} -Value {q_value} -Type {reg_type} -Force"
    )
    response, status = PowerShellExecutor.execute_command(command)
    if status != 0:
        return f"Error writing registry: {response.strip()}"
    return f'Registry value [{path}] "{shown_name}" set to "{shown}" (type: {reg_type}).'


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
        if _is_default(name):
            # Remove-ItemProperty cannot delete '(default)', and the key Get-Item
            # returns is read-only, so reopen it writable from its hive.
            name = "(Default)"
            command = (
                f"$hive, $sub = (Get-Item -LiteralPath {q_path} -ErrorAction Stop).Name "
                "-split '\\\\', 2; "
                "$base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(@{"
                "HKEY_CURRENT_USER='CurrentUser'; HKEY_LOCAL_MACHINE='LocalMachine'; "
                "HKEY_CLASSES_ROOT='ClassesRoot'; HKEY_USERS='Users'; "
                "HKEY_CURRENT_CONFIG='CurrentConfig'}[$hive], 'Default'); "
                "$key = if ($sub) { $base.OpenSubKey($sub, $true) } else { $base }; "
                "try { $key.DeleteValue('') } finally { $key.Close() }"
            )
        else:
            command = f"Remove-ItemProperty -LiteralPath {q_path} -Name {ps_quote(name)} -Force"
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
        f"$item = Get-ItemProperty -LiteralPath {q_path} -ErrorAction Stop; "
        "$values = @(foreach ($p in @($item.PSObject.Properties | "
        "Where-Object Name -notlike 'PS*')) { "
        f'$v = $p.Value; "$($p.Name) : {_FORMAT_VALUE}" }}) -join "`n"; '
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
