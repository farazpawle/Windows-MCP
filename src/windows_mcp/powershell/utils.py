import logging
import subprocess
from xml.sax.saxutils import escape as xml_escape

import psutil

__all__ = [
    "run_with_graceful_timeout",
    "ps_quote",
    "ps_quote_for_xml",
]

logger = logging.getLogger(__name__)


def ps_quote(value: str) -> str:
    """Wrap value in PowerShell single-quoted string literal (escapes ' as '')."""
    return "'" + value.replace("'", "''") + "'"


def ps_quote_for_xml(value: str) -> str:
    """XML-escape then ps_quote. Use for values in XML passed to PowerShell."""
    escaped = xml_escape(value, {'"': "&quot;", "'": "&apos;"})
    return ps_quote(escaped)


def check_pid_exists(pid: int) -> bool:
    """Check whether a process with the given PID is actively running."""
    try:
        proc = psutil.Process(pid)
        return proc.status() not in (psutil.STATUS_DEAD, psutil.STATUS_ZOMBIE)
    except psutil.NoSuchProcess, psutil.AccessDenied:
        return False


def run_with_graceful_timeout(
    *popenargs,
    input=None,
    capture_output=False,
    timeout=None,
    check=False,
    grace_period: float = 2.0,
    **kwargs,
):
    """A Windows-oriented variant migrated from ``subprocess.run``.

    This helper keeps the overall calling style and behavior of
    ``subprocess.run``, but adapts the timeout-handling path for some
    Windows-specific edge cases as described below.

    Args:
        *popenargs: Positional arguments to pass to ``subprocess.Popen``.
        input: Data to send to stdin (if not None).
        capture_output: If True, capture stdout and stderr into the returned CompletedProcess.
        timeout: Seconds to wait for process to complete before triggering shutdown.
        check: If True, raise CalledProcessError if the process exits with a non-zero code.
        grace_period: Seconds to wait for the killed process's last output. Defaults to 2.0.

    Notes:
        In some Windows scenarios, especially when launching a console host
        such as PowerShell and letting it start another interactive console
        process or a process stuck in an infinite loop that continuously outputs data
        (for example ``pwsh -> python``, like ``pwsh -NoProfile -Command python``
        or ``pwsh -NoProfile -Command "python -c 'while True: print(1)'"``),
        the standard timeout flow of ``subprocess.run`` may not be sufficient.
        After a timeout occurs, simply terminating the top-level child process
        may still leave descendant processes alive, or leave inherited pipe handles open.
        As a result, the parent process can remain blocked while trying to
        finish the final ``communicate()`` cleanup, and memory usage may continue to grow if
        stdout/stderr are being captured.

        So on timeout the whole process tree is terminated via ``taskkill /T /F``.
        A graceful ``CTRL_BREAK_EVENT`` first never arrived (the child runs in its
        own hidden console) and only delayed the reply by ``grace_period``.

        Related issues: #124, #146
    """

    if input is not None:
        if kwargs.get("stdin") is not None:
            raise ValueError("stdin and input arguments may not both be used.")
        kwargs["stdin"] = subprocess.PIPE

    if capture_output:
        if kwargs.get("stdout") is not None or kwargs.get("stderr") is not None:
            raise ValueError("stdout and stderr arguments may not be used with capture_output.")
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE

    # CREATE_NEW_PROCESS_GROUP keeps a Ctrl+C or Ctrl+Break sent to the server's
    # console from reaching the child, and one aimed at the child from reaching
    # the server.
    #
    # CREATE_NO_WINDOW suppresses the console the child would otherwise get.
    # When the server has no console of its own — the usual case when it runs
    # as an MCP extension host — Windows allocates a *new* console for a
    # console child, which flashes on screen and steals keyboard focus from
    # whatever the user is typing in. Redirecting the streams does not prevent
    # the allocation; only this flag does. It composes with the process-group
    # flag.
    creationflags = kwargs.get("creationflags", 0)
    creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    kwargs["creationflags"] = creationflags

    with subprocess.Popen(*popenargs, **kwargs) as process:
        stdout = stderr = None
        try:
            stdout, stderr = process.communicate(input=input, timeout=timeout)

        except subprocess.TimeoutExpired as exc:
            # Kill the whole tree at once. A CTRL_BREAK_EVENT cannot reach it: the child
            # has its own hidden console (CREATE_NO_WINDOW), and waiting for it made every
            # timeout reply 2 s late (round-4 R4-10).
            logger.debug(
                f"Process {process.pid} (exist: {check_pid_exists(process.pid)}) did not exit "
                "within the timeout, killing it and all child processes..."
            )
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            try:
                # What it printed before the kill; pipes a grandchild still holds may
                # never close, hence the bound.
                exc.stdout, exc.stderr = process.communicate(timeout=grace_period)
            except subprocess.TimeoutExpired:
                pass  # keep the original timeout exception
            exc.add_note("Process tree killed after the timeout.")
            raise exc

        except BaseException:
            # Keep cleanup strategy consistent with timeout path
            logger.debug("Other exception occurred, attempting to kill process...")
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            raise

        retcode = process.poll()
        if check and retcode:
            raise subprocess.CalledProcessError(retcode, process.args, output=stdout, stderr=stderr)

        return subprocess.CompletedProcess(process.args, retcode, stdout, stderr)
