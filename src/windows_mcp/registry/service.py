"""
Registry service for the Windows MCP server.
Provides structured operations for reading and writing the Windows Registry
via PowerShell cmdlets.
"""

import logging

from windows_mcp.powershell import PowerShellExecutor
from windows_mcp.powershell.utils import ps_quote
from windows_mcp.registry.views import ALLOWED_REGISTRY_TYPES, RegistryType

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_value(path: str, name: str) -> str:
    """Read a registry value at *path* with the given *name*."""
    q_path = ps_quote(path)
    q_name = ps_quote(name)
    command = (
        f"Get-ItemProperty -Path {q_path} -Name {q_name} | "
        f"Select-Object -ExpandProperty {q_name}"
    )
    response, status = PowerShellExecutor.execute_command(command)
    if status != 0:
        return f'Error reading registry: {response.strip()}'
    return f'Registry value [{path}] "{name}" = {response.strip()}'


def set_value(path: str, name: str, value: str, reg_type: RegistryType = 'String') -> str:
    """Create or update a registry value, creating the key if it does not exist."""
    if reg_type not in ALLOWED_REGISTRY_TYPES:
        return (
            f"Error: invalid registry type '{reg_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_REGISTRY_TYPES))}"
        )
    q_path = ps_quote(path)
    q_name = ps_quote(name)
    q_value = ps_quote(value)
    command = (
        f"if (-not (Test-Path {q_path})) {{ New-Item -Path {q_path} -Force | Out-Null }}; "
        f"Set-ItemProperty -Path {q_path} -Name {q_name} -Value {q_value} -Type {reg_type} -Force"
    )
    response, status = PowerShellExecutor.execute_command(command)
    if status != 0:
        return f'Error writing registry: {response.strip()}'
    return f'Registry value [{path}] "{name}" set to "{value}" (type: {reg_type}).'


def delete_entry(path: str, name: str | None = None, recursive: bool = False) -> str:
    """Delete a registry value when *name* is provided, otherwise remove the key.

    A key that has sub-keys is only removed with recursive=True, so a missing
    ``name`` can no longer wipe a whole tree by accident.
    """
    q_path = ps_quote(path)
    if name:
        q_name = ps_quote(name)
        command = f"Remove-ItemProperty -Path {q_path} -Name {q_name} -Force"
        response, status = PowerShellExecutor.execute_command(command)
        if status != 0:
            return f'Error deleting registry value: {response.strip()}'
        return f'Registry value [{path}] "{name}" deleted.'
    if recursive:
        command = f"Remove-Item -Path {q_path} -Recurse -Force"
    else:
        command = (
            f"$n = @(Get-ChildItem -Path {q_path} -ErrorAction Stop).Count; "
            f"if ($n -gt 0) {{ Write-Output \"HAS_SUBKEYS:$n\"; exit 2 }}; "
            f"Remove-Item -Path {q_path} -Force -ErrorAction Stop"
        )
    response, status = PowerShellExecutor.execute_command(command)
    if status == 2 and response.strip().startswith("HAS_SUBKEYS:"):
        count = response.strip().split(":", 1)[1]
        return (
            f"Error: Registry key [{path}] has {count} sub-key(s); nothing was deleted. "
            "Pass recursive=true to delete the key with all its sub-keys."
        )
    if status != 0:
        return f'Error deleting registry key: {response.strip()}'
    return f'Registry key [{path}] deleted.'


def list_key(path: str) -> str:
    """List values and sub-keys under *path*."""
    q_path = ps_quote(path)
    command = (
        f"$values = (Get-ItemProperty -Path {q_path} -ErrorAction Stop | "
        f"Select-Object * -ExcludeProperty PS* | Format-List | Out-String).Trim(); "
        f"$subkeys = (Get-ChildItem -Path {q_path} -ErrorAction SilentlyContinue | "
        f"Select-Object -ExpandProperty PSChildName) -join \"`n\"; "
        f"if ($values) {{ Write-Output \"Values:`n$values\" }}; "
        f"if ($subkeys) {{ Write-Output \"`nSub-Keys:`n$subkeys\" }}; "
        f"if (-not $values -and -not $subkeys) {{ Write-Output 'No values or sub-keys found.' }}"
    )
    response, status = PowerShellExecutor.execute_command(command)
    if status != 0:
        return f'Error listing registry: {response.strip()}'
    return f'Registry key [{path}]:\n{response.strip()}'
