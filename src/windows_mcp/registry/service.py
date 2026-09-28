"""
Registry service for the Windows MCP server.
Provides structured operations for reading and writing the Windows Registry
through winreg (round-6 R6-6: starting PowerShell took 0.3-0.5 s a call).
"""

import json
import logging
import re
import winreg

import pywintypes
import win32api

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


_HIVE_KEYS = {
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    "HKEY_USERS": winreg.HKEY_USERS,
    "HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
}
_TYPES = {
    "String": winreg.REG_SZ,
    "ExpandString": winreg.REG_EXPAND_SZ,
    "Binary": winreg.REG_BINARY,
    "DWord": winreg.REG_DWORD,
    "MultiString": winreg.REG_MULTI_SZ,
    "QWord": winreg.REG_QWORD,
}


class _Refused(Exception):
    """The reason shown after a reply's "Error ..." prefix."""


def _split(path: str) -> tuple[int, str]:
    """Hive handle and sub-key of a path resolve_path returned (HKCU:\\X or Registry::HKEY_X\\Y)."""
    if path[:10].lower() == "registry::":
        hive, _, sub = path[10:].partition("\\")
    else:
        drive, _, sub = path.partition(":")
        hive = _HIVES[drive.upper()]
    return _HIVE_KEYS[hive.upper()], sub.strip("\\")


def _open(path: str, access: int = winreg.KEY_READ) -> winreg.HKEYType:
    hive, sub = _split(path)
    try:
        return winreg.OpenKey(hive, sub, 0, access)
    except FileNotFoundError:
        raise _Refused(f"key [{path}] does not exist.") from None


def _why(error: OSError, path: str) -> str:
    if isinstance(error, PermissionError):
        return f"access denied to [{path}]."
    return f"{error.strerror or error} [{path}]."


def _show(data: object, kind: int) -> str:
    """A value in the shape set accepts: hex bytes, a JSON string list (R3-9).

    Numbers show unsigned, as PowerShell showed them (a DWord set to -1 reads 4294967295),
    and an ExpandString shows expanded; the stored value keeps its %VARIABLES%.
    """
    if kind == winreg.REG_EXPAND_SZ and isinstance(data, str):
        return winreg.ExpandEnvironmentStrings(data)
    if isinstance(data, list):
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if isinstance(data, bytes):
        return ",".join(f"{byte:02x}" for byte in data)
    return "" if data is None else str(data)


def get_value(path: str, name: str) -> str:
    """Read a registry value at *path* with the given *name*."""
    shown_name = "(Default)" if _is_default(name) else name
    try:
        with _open(path) as key:
            try:
                data, kind = winreg.QueryValueEx(key, "" if _is_default(name) else name)
            except FileNotFoundError:
                raise _Refused(f'value "{shown_name}" does not exist in [{path}].') from None
    except _Refused as e:
        return f"Error reading registry: {e}"
    except OSError as e:
        return f"Error reading registry: {_why(e, path)}"
    return f'Registry value [{path}] "{shown_name}" = {_show(data, kind)}'


def set_value(path: str, name: str, value: str, reg_type: RegistryType = "String") -> str:
    """Create or update a registry value, creating the key if it does not exist."""
    if reg_type not in ALLOWED_REGISTRY_TYPES:
        return (
            f"Error: invalid registry type '{reg_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_REGISTRY_TYPES))}"
        )
    shown_name = "(Default)" if _is_default(name) else name
    shown = value
    if reg_type == "Binary":
        try:
            data = parse_binary(value)
        except ValueError as e:
            return f"Error: invalid binary value: {e}"
    elif reg_type in ("DWord", "QWord"):
        try:
            number = parse_number(value, reg_type)
        except ValueError as e:
            return f"Error: invalid {reg_type} value: {e}"
        bits = 32 if reg_type == "DWord" else 64
        if not -(1 << (bits - 1)) <= number < 1 << bits:
            return (
                f"Error: invalid {reg_type} value: {reg_type} needs a number from "
                f"{-(1 << (bits - 1))} to {(1 << bits) - 1} (got {value!r})"
            )
        # A negative number is stored as its two's complement, as PowerShell stored it.
        data = number & ((1 << bits) - 1)
        shown = str(number)
    elif reg_type == "MultiString":
        try:
            data = parse_multistring(value)
        except ValueError as e:
            return f"Error: invalid MultiString value: {e}"
    else:
        data = value
    hive, sub = _split(path)
    try:
        with winreg.CreateKeyEx(hive, sub, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "" if _is_default(name) else name, 0, _TYPES[reg_type], data)
    except OSError as e:
        return f"Error writing registry: {_why(e, path)}"
    return f'Registry value [{path}] "{shown_name}" set to "{shown}" (type: {reg_type}).'


def delete_entry(path: str, name: str | None = None, recursive: bool = False) -> str:
    """Delete a registry value when *name* is provided, otherwise remove the key.

    A key that has sub-keys is only removed with recursive=True, so a missing
    ``name`` can no longer wipe a whole tree by accident. Paths holding ``*`` or
    ``?`` are refused: a wildcard delete could wipe many keys at once. A whole
    hive is never deleted.
    """
    if "*" in path or "?" in path:
        return (
            f"Error: Registry path [{path}] contains a wildcard (* or ?); nothing was deleted. "
            "Give the exact key path."
        )
    if name is not None:
        # name="" is the default value, as in get and set; before R6-6 it deleted the key.
        shown_name = "(Default)" if _is_default(name) else name
        try:
            with _open(path, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, "" if _is_default(name) else name)
                except FileNotFoundError:
                    raise _Refused(f'value "{shown_name}" does not exist in [{path}].') from None
        except _Refused as e:
            return f"Error deleting registry value: {e}"
        except OSError as e:
            return f"Error deleting registry value: {_why(e, path)}"
        return f'Registry value [{path}] "{shown_name}" deleted.'
    hive, sub = _split(path)
    if not sub:
        return f"Error: [{path}] is a whole hive; nothing was deleted."
    try:
        with _open(path) as key:
            count = winreg.QueryInfoKey(key)[0]
        if count and not recursive:
            return (
                f"Error: Registry key [{path}] has {count} sub-key(s); nothing was deleted. "
                "Pass recursive=true to delete the key with all its sub-keys."
            )
        if recursive:
            win32api.RegDeleteTree(hive, sub)
        else:
            winreg.DeleteKey(hive, sub)
    except _Refused as e:
        return f"Error deleting registry key: {e}"
    except OSError as e:
        return f"Error deleting registry key: {_why(e, path)}"
    except pywintypes.error as e:
        return f"Error deleting registry key: {e.strerror} [{path}]."
    return f"Registry key [{path}] deleted."


def list_key(path: str) -> str:
    """List values and sub-keys under *path*."""
    try:
        with _open(path) as key:
            subkey_count, value_count, _ = winreg.QueryInfoKey(key)
            values = [winreg.EnumValue(key, i) for i in range(value_count)]
            subkeys = [winreg.EnumKey(key, i) for i in range(subkey_count)]
    except _Refused as e:
        return f"Error listing registry: {e}"
    except OSError as e:
        return f"Error listing registry: {_why(e, path)}"
    parts = []
    if values:
        lines = (f"{name or '(default)'} : {_show(data, kind)}" for name, data, kind in values)
        parts.append("Values:\n" + "\n".join(lines))
    if subkeys:
        parts.append("Sub-Keys:\n" + "\n".join(subkeys))
    return f"Registry key [{path}]:\n" + ("\n\n".join(parts) or "No values or sub-keys found.")
