import os
from typing import Literal


__all__ = ["list_processes", "kill_process"]


def _strip_exe(name: str) -> str:
    name = name.strip().casefold()
    return name.removesuffix(".exe")


def list_processes(
    name: str | None = None,
    sort_by: Literal["memory", "cpu", "name"] = "memory",
    limit: int = 20,
) -> str:
    import psutil
    from tabulate import tabulate

    own_pid = os.getpid()
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            info = p.info
            mem_mb = info["memory_info"].rss / (1024 * 1024) if info["memory_info"] else 0
            is_self = info["pid"] == own_pid
            procs.append(
                {
                    "pid": info["pid"],
                    "name": f"{info['name'] or 'Unknown'}{' (this server)' if is_self else ''}",
                    # The server's own sample covers the moment it builds this list
                    # (~96%), so it looked like a runaway process an agent might kill.
                    "cpu": None if is_self else info["cpu_percent"] or 0,
                    "mem_mb": round(mem_mb, 1),
                }
            )
        except psutil.NoSuchProcess, psutil.AccessDenied:
            continue
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
    table = tabulate(
        [
            [
                p["pid"],
                p["name"],
                "-" if p["cpu"] is None else f"{p['cpu']:.1f}%",
                f"{p['mem_mb']:.1f} MB",
            ]
            for p in procs
        ],
        headers=["PID", "Name", "CPU%", "Memory"],
        tablefmt="simple",
    )
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
