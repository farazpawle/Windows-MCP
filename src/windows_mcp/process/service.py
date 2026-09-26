import logging
import os
import subprocess
import time
from datetime import datetime
from typing import Literal

from windows_mcp.infrastructure.action_log import redact
from windows_mcp.process.snapshot import ProcCounters, read_counters


__all__ = ["list_processes", "kill_process"]

logger = logging.getLogger(__name__)

_CMDLINE_MAX = 200


def _strip_exe(name: str) -> str:
    name = name.strip().casefold()
    return name.removesuffix(".exe")


def _counters() -> dict[int, ProcCounters]:
    """Every process's counters: one system read, or psutil per process if that fails."""
    try:
        return read_counters()
    except OSError as err:
        import psutil

        logger.warning("Process snapshot failed, reading each process instead: %s", err)
        counters = {}
        for p in psutil.process_iter(["pid", "name", "memory_info", "cpu_times", "create_time"]):
            info = p.info
            times = info["cpu_times"]
            counters[info["pid"]] = ProcCounters(
                name=info["name"] or "",
                working_set=info["memory_info"].rss if info["memory_info"] else 0,
                cpu_time=int((times.user + times.system) * 1e7) if times else 0,
                create_time=info["create_time"],
            )
        return counters


def _cmdline(pid: int) -> list[str] | None:
    import psutil

    try:
        return psutil.Process(pid).cmdline()
    except psutil.Error, OSError:
        return None


def list_processes(
    name: str | None = None,
    sort_by: Literal["memory", "cpu", "name"] = "memory",
    limit: int = 20,
    details: bool = False,
) -> str:
    import psutil
    from tabulate import tabulate

    own_pid = os.getpid()
    # The CPU sample costs a 0.5 s wait, so only a CPU sort pays for it (round-3 R3-I3);
    # other sorts leave the column out rather than show made-up zeros.
    with_cpu = sort_by == "cpu"
    counters = _counters()
    cpu: dict[int, float] = {}
    if with_cpu:
        # CPU = CPU time used over a fresh half second, as a share of the whole machine
        # like Task Manager (per core, idle read ~1900% on a 20-thread PC).
        start = time.perf_counter()
        time.sleep(0.5)
        later = _counters()
        window = (time.perf_counter() - start) * 1e7 * (psutil.cpu_count() or 1)
        cpu = {
            pid: max(c.cpu_time - counters[pid].cpu_time, 0) / window * 100
            for pid, c in later.items()
            if pid in counters
        }
        counters = later
    procs = []
    for pid, c in counters.items():
        # Idle time is not a process (round-4 R4-I1): it topped the CPU list at ~96%.
        if with_cpu and pid == 0:
            continue
        is_self = pid == own_pid
        procs.append(
            {
                "pid": pid,
                "name": f"{c.name or 'Unknown'}{' (this server)' if is_self else ''}",
                # The server's own sample covers the moment it builds this list
                # (~96%), so it looked like a runaway process an agent might kill.
                "cpu": None if is_self else cpu.get(pid, 0.0),
                "mem_mb": round(c.working_set / (1024 * 1024), 1),
                "started": c.create_time,
            }
        )
    if name:
        # Plain substring match: the old fuzzy score let "pwsh" match ShellExperienceHost.
        needle = name.casefold()
        procs = [p for p in procs if needle in p["name"].casefold()]
    sort_key = {
        "memory": lambda x: x["mem_mb"],
        "cpu": lambda x: x["cpu"] or 0,
        "name": lambda x: x["name"].lower(),
    }
    procs.sort(key=sort_key.get(sort_by, sort_key["memory"]), reverse=(sort_by != "name"))
    procs = procs[:limit]
    if not procs:
        return f"No processes found{f' matching {name}' if name else ''}."
    rows = [[p["pid"], p["name"], f"{p['mem_mb']:.1f} MB"] for p in procs]
    headers = ["PID", "Name", "Memory"]
    if with_cpu:
        for row, p in zip(rows, procs):
            row.insert(2, "-" if p["cpu"] is None else f"{p['cpu']:.1f}%")
        headers.insert(2, "CPU%")
    if details:
        # Which program is behind a process (round-3 R3-I10): a hidden powershell.exe's
        # command line named the script. Secrets are hidden as in the action log.
        for row, p in zip(rows, procs):
            started = p["started"]
            row.append(
                datetime.fromtimestamp(started).strftime("%Y-%m-%d %H:%M:%S") if started else "-"
            )
            cmdline = _cmdline(p["pid"])
            text = redact(subprocess.list2cmdline(cmdline)) if cmdline else "-"
            # Cut after redact, so a cut never splits a secret out of redact's reach.
            # A browser's ~2,000-character line made 5 rows ~10,000 characters (R4-I2).
            row.append(text if len(text) <= _CMDLINE_MAX else text[: _CMDLINE_MAX - 1] + "…")
        headers += ["Started", "Command line"]
    table = tabulate(rows, headers=headers, tablefmt="simple")
    # tabulate pads every row to the widest last cell; the padding is only spaces.
    table = "\n".join(line.rstrip() for line in table.splitlines())
    return f"Processes ({len(procs)} shown):\n{table}"


def kill_process(name: str | None = None, pid: int | None = None, force: bool = False) -> str:
    import psutil

    if pid is None and name is None:
        return "Error: Provide either pid or name parameter for kill mode."
    if pid is not None and name is not None:
        # The pid used to win silently, so a mismatched name went unnoticed.
        return "Error: Provide pid or name for kill mode, not both."
    killed = []
    if pid is not None:
        try:
            p = psutil.Process(pid)
            pname = p.name()
            if force:
                p.kill()
            else:
                p.terminate()
            killed.append(f"{pname} (PID {pid})")
        except psutil.NoSuchProcess:
            return f"Error: No process with PID {pid} found."
        except psutil.AccessDenied:
            return f"Error: Access denied to kill PID {pid}. Try running as administrator."
    else:
        # Exact name only; ".exe" is optional so "pwsh" and "pwsh.exe" both work.
        wanted = _strip_exe(name)
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if p.info["name"] and _strip_exe(p.info["name"]) == wanted:
                    if force:
                        p.kill()
                    else:
                        p.terminate()
                    killed.append(f"{p.info['name']} (PID {p.info['pid']})")
            except psutil.NoSuchProcess, psutil.AccessDenied:
                continue
    if not killed:
        return f'Error: No process matching "{name}" found or access denied.'
    return f"{'Force killed' if force else 'Terminated'}: {', '.join(killed)}"
