"""PowerShell command executor service"""

import base64
import ctypes
import ctypes.wintypes
import logging
import os
import re
import winreg
import shutil
import subprocess
import xml.etree.ElementTree as ET

from windows_mcp.desktop.utils import is_elevated
from windows_mcp.powershell.utils import run_with_graceful_timeout

__all__ = ["PowerShellExecutor"]

logger = logging.getLogger(__name__)

# Both pwsh ("PowerShell is ...") and Windows PowerShell ("Windows PowerShell is ...").
_PROMPT_BLOCKED = "NonInteractive mode. Read and Prompt functionality is not available"
_PROMPT_HINT = (
    "Error: interactive input is not available - the command asked for input (Read-Host, "
    "a confirmation or a credential prompt) and nothing was done at that step. Pass the "
    "value as a parameter, or add -Confirm:$false, -Force or -Recurse as appropriate."
)


def _read_reg_env(hkey: int, subkey: str) -> tuple[dict[str, str], str, str]:
    """Read all environment variables from a registry key.

    Returns (vars, path, pathext) where *vars* is a dict of name->value
    (excluding PATH/PATHEXT), and *path*/*pathext* are the raw expanded
    values for those two special keys (empty string if absent).
    """
    variables: dict[str, str] = {}
    path = ""
    pathext = ""

    try:
        with winreg.OpenKey(hkey, subkey) as key:
            i = 0
            while True:
                try:
                    name, value, reg_type = winreg.EnumValue(key, i)
                    if reg_type not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                        i += 1
                        continue
                    if reg_type == winreg.REG_EXPAND_SZ:
                        # Note: ExpandEnvironmentStrings uses the current process
                        # environment, which may be stripped by the MCP host. References
                        # to missing vars (e.g. %COMPUTERNAME%) won't expand correctly.
                        # In practice this is acceptable: most REG_EXPAND_SZ values under
                        # HKLM/HKCU\Environment reference %SystemRoot% or %USERPROFILE%
                        # which are almost always present.
                        value = winreg.ExpandEnvironmentStrings(value)
                    upper = name.upper()
                    if upper == "PATH":
                        path = value
                    elif upper == "PATHEXT":
                        pathext = value
                    else:
                        variables[name] = value
                    i += 1
                except OSError:
                    break
    except OSError:
        pass

    return variables, path, pathext


def _dedup_path(*segments: str) -> str:
    """Join PATH segments and deduplicate entries (case-insensitive)."""
    seen = set()
    deduped = []
    for p in ";".join(filter(None, segments)).split(";"):
        norm = p.lower().rstrip("\\")
        if norm and norm not in seen:
            seen.add(norm)
            deduped.append(p)
    return ";".join(deduped)


def _win32_name(dll: str, func: str) -> str:
    """Call a Win32 GetXxxNameW(LPWSTR, LPDWORD) function.

    Only suitable for APIs with the (buffer, &size) calling convention,
    e.g. kernel32.GetComputerNameW and advapi32.GetUserNameW.
    """
    buf = ctypes.create_unicode_buffer(257)
    size = ctypes.wintypes.DWORD(257)
    fn = getattr(ctypes.windll, dll)
    if getattr(fn, func)(buf, ctypes.byref(size)):
        return buf.value
    return ""


_CLIXML_ESCAPE = re.compile(r"_x([0-9A-Fa-f]{4})_")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CLIXML_STREAM_PREFIX = {
    "error": "",
    "warning": "WARNING: ",
    "verbose": "VERBOSE: ",
    "debug": "DEBUG: ",
}


def decode_clixml(stderr: str) -> str:
    """Turn PowerShell's CLIXML error stream into plain text.

    When stdout/stderr are redirected, PowerShell writes its error, warning,
    verbose, debug and progress streams to stderr as serialized CLIXML. Keep
    error, warning, verbose and debug lines (all but errors prefixed), drop
    progress noise, undo the ``_xHHHH_`` escaping and strip ANSI colours.
    Non-CLIXML stderr (a native exe's) is returned as-is, trimmed.
    """
    text = stderr.strip()
    if not text.startswith("#< CLIXML"):
        return text
    try:
        root = ET.fromstring(text.split("\n", 1)[1])
    except ET.ParseError, IndexError:
        return text
    parts = []
    for node in root.iter():
        prefix = _CLIXML_STREAM_PREFIX.get((node.get("S") or "").lower())
        if prefix is None or not node.tag.endswith("}S") or node.text is None:
            continue
        line = _CLIXML_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), node.text)
        line = prefix + _ANSI.sub("", line)
        # Error lines carry their own CRLF; a warning/verbose/debug record is one whole
        # message without one, and ran into the next line ("warn-streamException: boom").
        if not line.endswith("\n"):
            line += "\n"
        parts.append(line)
    return "".join(parts).replace("\r\n", "\n").strip()


def _decode_output(data: bytes | str | None) -> str:
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data or ""


_FALLBACK_PATHEXT = ".COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC;.CPL;.PY;.PYW"


def _prepare_env() -> dict[str, str]:
    """Prepare a complete environment block for the PowerShell subprocess.

    MCP hosts (e.g. Claude Desktop) may launch this server with a stripped
    environment block missing session-level variables. This function starts
    from os.environ and fills in missing variables from:
      1. System-level env vars from the registry (HKLM)
      2. User-level env vars from the registry (HKCU)
      3. Dynamic vars (COMPUTERNAME, USERNAME, etc.) via Win32 API
    Existing values in os.environ are never overwritten, only missing ones
    are supplemented. PATH is special-cased: inherited entries keep their
    priority and registry entries are appended to fill in missing paths.
    """
    env = os.environ.copy()

    # PYTHONHOME is set by uv to pin its own managed interpreter for this
    # server process. Leaking it into a spawned shell makes any Python found
    # on PATH there resolve its standard library against the server's
    # interpreter instead of its own, breaking unrelated installs (#350).
    env.pop("PYTHONHOME", None)

    try:
        machine_vars, machine_path, machine_pathext = _read_reg_env(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        )
        user_vars, user_path, user_pathext = _read_reg_env(winreg.HKEY_CURRENT_USER, r"Environment")

        # Supplement missing vars. User-level (HKCU) takes precedence over
        # system-level (HKLM) for same-named keys, matching Windows' resolution order.
        for name, value in {**machine_vars, **user_vars}.items():
            if not env.get(name):
                env[name] = value

        # PATH: inherited entries keep their priority; registry entries are
        # appended to fill in anything missing (e.g. stripped MCP host env).
        if machine_path or user_path:
            env["PATH"] = _dedup_path(env.get("PATH", ""), machine_path, user_path)

        # PATHEXT: use registry value if the inherited one looks incomplete
        effective_pathext = user_pathext or machine_pathext
        if effective_pathext and ".EXE" not in env.get("PATHEXT", "").upper():
            env["PATHEXT"] = effective_pathext

    except Exception:
        logger.debug("Failed to read environment from registry", exc_info=True)
        if ".EXE" not in env.get("PATHEXT", "").upper():
            env["PATHEXT"] = _FALLBACK_PATHEXT

    # Dynamic variables not stored in registry — only fill if missing
    if not env.get("COMPUTERNAME"):
        try:
            computer_name = _win32_name("kernel32", "GetComputerNameW")
            if computer_name:
                env["COMPUTERNAME"] = computer_name
        except Exception as e:
            logger.debug("Failed to get COMPUTERNAME via Win32 API: %s", e)

    if not env.get("USERNAME"):
        try:
            user_name = _win32_name("advapi32", "GetUserNameW")
            if user_name:
                env["USERNAME"] = user_name
        except Exception as e:
            logger.debug("Failed to get USERNAME via Win32 API: %s", e)

    user_profile = os.path.expanduser("~")
    env.setdefault("USERPROFILE", user_profile)
    drive, tail = os.path.splitdrive(user_profile)
    env.setdefault("HOMEDRIVE", drive)
    env.setdefault("HOMEPATH", tail)
    # On domain-joined machines USERDOMAIN is the NetBIOS domain name (e.g.
    # "CORP"), not the computer name. This fallback is only correct for workgroup
    # machines. USERDOMAIN is a session variable set at logon and is unlikely to
    # be missing on domain-joined hosts, so this is an acceptable last resort.
    env.setdefault("USERDOMAIN", env.get("COMPUTERNAME", ""))

    return env


class PowerShellExecutor:
    """Static utility class for executing PowerShell commands."""

    # Status for a command that timed out or could not start. Windows exit codes are
    # unsigned, so no real process returns it; code 1 was ambiguous with e.g. findstr.
    NOT_RUN = -1

    @staticmethod
    def execute_command(
        command: str,
        timeout: int = 10,
        shell: str | None = None,
        include_errors: bool = False,
    ) -> tuple[str, int]:
        """Run *command* and return (output, exit code).

        Output is stdout, or the decoded error stream when stdout is empty. With
        *include_errors*, errors are also appended when stdout is not empty:
        non-terminating errors leave the exit code at 0 and were otherwise lost.
        It is off by default because internal callers parse stdout exactly.
        """
        try:
            # $OutputEncoding: controls how PS5.1 encodes output written to its stdout pipe.
            # Without this set to UTF-8, PS5.1 uses the system codepage and native process
            # stdout is silently lost when Python reads the pipe.
            # [Console]::OutputEncoding: controls how PS decodes bytes from native exe stdout.
            utf8_command = (
                "$OutputEncoding = [System.Text.Encoding]::UTF8; "
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                f"{command}"
            )
            encoded = base64.b64encode(utf8_command.encode("utf-16le")).decode("ascii")
            env = _prepare_env()
            # NO_COLOR suppresses ANSI escape sequences in pwsh 7.2+ (and many other CLI tools).
            # PS5.1 has no ANSI output, so this is harmlessly ignored there.
            # https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_ansi_terminals#disabling-ansi-output
            env["NO_COLOR"] = "1"

            shell = shell or ("pwsh" if shutil.which("pwsh") else "powershell")

            # No one can answer a prompt: without -NonInteractive, Read-Host returned ""
            # and a confirmation prompt failed with a meaningless null-reference error.
            args = [shell, "-NoProfile", "-NonInteractive"]
            # Only older Windows PowerShell (5.1) uses -OutputFormat Text successfully here
            shell_name = os.path.basename(shell).lower().replace(".exe", "")
            if shell_name == "powershell":
                args.extend(["-OutputFormat", "Text"])
            args.extend(["-EncodedCommand", encoded])

            result = run_with_graceful_timeout(
                args,
                stdin=subprocess.DEVNULL,  # Prevent child processes from inheriting the MCP pipe stdin
                capture_output=True,  # No errors='ignore' - let subprocess return bytes
                timeout=timeout,
                cwd=os.path.expanduser(path="~"),
                env=env,
            )
            # Handle both bytes and str output (subprocess behavior varies by environment)
            stdout = _decode_output(result.stdout)
            stderr = decode_clixml(_decode_output(result.stderr))
            output = stdout or stderr
            if include_errors and stdout.strip() and stderr:
                # Not just "Errors": warning, verbose and debug lines land here too.
                output = f"{stdout.rstrip()}\n\nErrors and messages:\n{stderr}"
            returncode = result.returncode
            # ponytail: matches the English message only; a localized PowerShell keeps
            # its own wording and the raw exit code.
            if _PROMPT_BLOCKED in stderr:
                # A blocked confirmation prompt is a non-terminating error (exit 0).
                returncode = returncode or 1
                output = f"{output.rstrip()}\n\n{_PROMPT_HINT}"
            # If the command failed with "Access is denied" and we aren't elevated, add a helpful hint
            if returncode != 0 and "Access is denied" in output and not is_elevated():
                output += (
                    "\n\nHINT: This command may require an elevated (Administrator) terminal. "
                    "The Windows-MCP server is currently running at a lower integrity level."
                )
            return output, returncode
        except subprocess.TimeoutExpired as e:
            # What the command printed before it was stopped is often the clue to why.
            partial = "\n".join(
                text
                for text in (
                    _decode_output(e.stdout).rstrip(),
                    decode_clixml(_decode_output(e.stderr)),
                )
                if text
            )
            note = f"Command execution timed out after {timeout} s"
            return (f"{partial}\n\n{note}" if partial else note), PowerShellExecutor.NOT_RUN
        except Exception as e:
            return f"Command execution failed: {type(e).__name__}: {e}", PowerShellExecutor.NOT_RUN
