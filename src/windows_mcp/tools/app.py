"""App tool — launch applications and manage their windows."""

import ctypes
import json
import os
import shutil
import subprocess
import winreg
from pathlib import Path
from typing import Literal

from mcp.types import ToolAnnotations
from windows_mcp.infrastructure import with_analytics
from windows_mcp.tools._args import as_whole_number
from fastmcp import Context

_NEW_WINDOW_MODES = {"minimize", "maximize", "restore", "close", "list", "move"}
_WINDOW_MODES = (_NEW_WINDOW_MODES - {"list"}) | {"resize", "switch"}


def _split_command_line(text: str) -> list[str]:
    """Split *text* exactly as a Windows program splits its own command line."""
    if not text.strip():
        return []
    shell32 = ctypes.windll.shell32
    shell32.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    count = ctypes.c_int()
    # The first token follows program-name rules (no \" escapes), so give it a dummy one.
    argv = shell32.CommandLineToArgvW(f"x {text}", ctypes.byref(count))
    if not argv:
        raise ValueError(f"args could not be split: {text!r}")
    try:
        return [argv[i] for i in range(1, count.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv)


def _as_args(value: list[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        args = value
    elif value.lstrip().startswith(("[", "{")):
        args = json.loads(value)
    else:
        # Plain text such as "-n 30 127.0.0.1", which the schema allows.
        args = _split_command_line(value)
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError("args must be a list of strings")
    return args


_APP_PATHS = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\"


def _from_app_paths(name: str) -> str | None:
    """Path registered for *name* under App Paths (what Win+R uses), user before machine."""
    key = name if name.lower().endswith(".exe") else f"{name}.exe"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            value = winreg.QueryValue(hive, _APP_PATHS + key)
        except OSError:
            continue
        if value:
            return os.path.expandvars(value.strip().strip('"'))
    return None


def _resolve_executable(executable: str) -> Path:
    # A bare name ("notepad.exe") was looked up in the server's own folder; search
    # PATH like a shell does, then App Paths (msedge.exe is only there, round-3 R3-I5).
    # Anything with a folder or drive part stays a path.
    if os.path.basename(executable) == executable:
        found = shutil.which(executable) or _from_app_paths(executable)
        if found is None:
            raise ValueError(f"Executable not found on PATH or in App Paths: {executable}")
        executable = found
    path = Path(executable).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Executable does not exist: {path}")
    return path


def _resolve_cwd(cwd: str | None) -> Path | None:
    if cwd is None:
        return None
    path = Path(cwd).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"Working directory does not exist: {path}")
    return path


def _launch_executable(
    executable: str,
    args: list[str] | str | None,
    cwd: str | None,
) -> str:
    resolved_executable = _resolve_executable(executable)
    resolved_cwd = _resolve_cwd(cwd)
    resolved_args = _as_args(args)

    command = [str(resolved_executable), *resolved_args]
    run_with = None
    if resolved_executable.suffix.lower() == ".ps1":
        # Windows can't start a .ps1 directly; hand it to PowerShell. Bypass only
        # affects this one process, and the PowerShell tool can already run any script.
        run_with = "pwsh" if shutil.which("pwsh") else "powershell"
        command = [run_with, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", *command]

    try:
        process = subprocess.Popen(
            command,
            cwd=str(resolved_cwd) if resolved_cwd is not None else None,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        if getattr(exc, "winerror", None) != 193:  # ERROR_BAD_EXE_FORMAT
            raise
        raise ValueError(
            f"{resolved_executable} is not a program or a PowerShell script, so it cannot be "
            'launched; to open a document, use mode="launch" or the PowerShell tool'
        ) from exc
    result = {
        "pid": process.pid,
        "executable": str(resolved_executable),
        "args": resolved_args,
        "cwd": str(resolved_cwd) if resolved_cwd is not None else None,
    }
    if run_with:
        result["run_with"] = run_with
    return json.dumps(result, indent=2)


def register(mcp, *, get_desktop, get_analytics):
    @mcp.tool(
        name="App",
        description=(
            "Open/start/launch applications and manage windows. Keywords: open, start, launch, program, "
            "application, window, foreground, focus, resize. Four modes: 'launch' (opens an application "
            "by Start Menu name), 'launch_executable' (strictly launches one executable - a path, or a "
            "bare name found on PATH - with args as a list or plain command-line text and optional "
            "cwd; a .ps1 script is run through PowerShell), 'resize' (adjusts a named "
            "or active window; window_loc and window_size are real screen pixels, not screenshot pixels), 'switch' (brings a specific window into focus), "
            "'minimize' / 'maximize' / 'restore' (named or active window), 'close' (asks a named "
            "window to close, like its X button; name or handle required), 'list' (every window "
            "with its handle, process id, program and state) and 'move' (to display N, numbered "
            "as in DisplayInventory; named or active window). Every window mode also takes "
            "handle=<number from 'list'> instead of name, to pick one of several same-named windows."
        ),
        annotations=ToolAnnotations(
            title="App",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @with_analytics(get_analytics(), "App-Tool")
    def app_tool(
        mode: Literal[
            "launch",
            "launch_executable",
            "resize",
            "switch",
            "minimize",
            "maximize",
            "restore",
            "close",
            "list",
            "move",
        ] = "launch",
        name: str | None = None,
        window_loc: list[int] | None = None,
        window_size: list[int] | None = None,
        executable: str | None = None,
        args: list[str] | str | None = None,
        cwd: str | None = None,
        handle: int | str | None = None,
        display: int | str | None = None,
        ctx: Context = None,
    ):
        handle = as_whole_number(handle, "handle")
        display = as_whole_number(display, "display")
        if handle is not None and mode not in _WINDOW_MODES:
            raise ValueError(f"handle only applies to window modes, not mode={mode!r}")
        if (display is None) != (mode != "move"):
            raise ValueError("display is required for mode='move' and only applies to it")
        if mode in _NEW_WINDOW_MODES:
            if window_loc is not None or window_size is not None:
                raise ValueError("window_loc and window_size only apply to mode='resize'")
            if mode == "list" and name is not None:
                raise ValueError("mode='list' takes no name; it lists every window")

        exact_launch_inputs = (executable, args, cwd)
        if mode != "launch_executable" and any(value is not None for value in exact_launch_inputs):
            raise ValueError('executable, args, and cwd require mode="launch_executable"')

        if mode == "launch_executable":
            if executable is None:
                raise ValueError('executable is required for mode="launch_executable"')
            if name is not None or window_loc is not None or window_size is not None:
                raise ValueError(
                    "name, window_loc, and window_size are not supported for "
                    'mode="launch_executable"'
                )
            return _launch_executable(executable, args, cwd)

        return get_desktop().app(
            mode, name, window_loc, window_size, handle=handle, display=display
        )
